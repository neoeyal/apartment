"""
Fetches and parses listing cards from a Yad2 rental search results page.

Uses Playwright (headless Chromium) rather than plain `requests` because
Yad2 employs bot-detection that often blocks simple HTTP clients, and its
results can also be client-rendered. A real (headless) browser sidesteps
both problems.

Parsing is regex/text-based off the actual rendered listing cards rather
than specific CSS class names, since Yad2 changes its front-end markup
fairly often — class names break easily, but "₪ 7,500" and "3 חדרים"
patterns are far more stable.

If Yad2 changes their markup enough that this stops finding listings,
save a copy of the rendered HTML (see DEBUG_DUMP_PATH below) and look at
how listing cards are structured now — the regexes below will need updating.
"""

import re

from bs4 import BeautifulSoup
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

ITEM_HREF_RE = re.compile(r"/realestate/item/[^/?]+/([a-zA-Z0-9]+)")
PRICE_RE = re.compile(r"₪\s*([\d,]+)")
ROOMS_RE = re.compile(r"([\d.]+)\s*חדרים")
SIZE_RE = re.compile(r"(\d+)\s*מ[\"\u05f4]ר")

DEBUG_DUMP_PATH = "last_page_debug.html"

# Yad2's per-listing contact endpoint. Returns JSON with the advertiser's
# name, phone, and (for brokers) agencyName — the same data the site fetches
# when you click "הצגת מספר טלפון". One cheap GET per listing, no page render.
CUSTOMER_API = "https://gw.yad2.co.il/realestate-item/{id}/customer"

# Stealth config shared by every browser we open. See _new_stealth_context for
# why each piece matters — these are what get us past Yad2's bot detection.
_LAUNCH_ARGS = ["--disable-blink-features=AutomationControlled"]
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)


def _new_stealth_context(browser):
    """Build a browser context that looks like a real user.

    Yad2 is fronted by ShieldSquare/Imperva bot detection. A vanilla headless
    browser gets served a CAPTCHA page instead of content. Hiding the
    automation flag (launch arg), removing navigator.webdriver, and presenting
    a consistent real-browser context (locale/timezone/viewport/headers) are
    what get us past it. Don't strip these without re-testing."""
    context = browser.new_context(
        user_agent=_USER_AGENT,
        locale="he-IL",
        timezone_id="Asia/Jerusalem",
        viewport={"width": 1366, "height": 900},
        extra_http_headers={"Accept-Language": "he-IL,he;q=0.9,en;q=0.8"},
    )
    context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
    )
    return context


class BrowserNotInstalledError(RuntimeError):
    pass


def ensure_browser_installed() -> None:
    """Quick check that Playwright's Chromium build is actually downloaded.
    `pip install playwright` only installs the Python package — the browser
    binary itself is a separate download. Without this check, a missing
    browser just fails silently on every poll cycle forever."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
    except Exception as e:
        if "Executable doesn't exist" in str(e):
            raise BrowserNotInstalledError(
                "Playwright's browser isn't downloaded yet. Run this once, "
                "then start the script again:\n\n    playwright install chromium\n"
            ) from e
        raise


def _get_rendered_html(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=_LAUNCH_ARGS)
        context = _new_stealth_context(browser)
        page = context.new_page()
        # NOTE: do NOT wait_until="networkidle" here. Yad2 keeps background
        # requests (analytics + bot-detection beacons) running continuously,
        # so the "no network for 500ms" condition often never happens within
        # the timeout and goto() raises TimeoutError — reliably on the 2nd+
        # poll once bot-detection has warmed up. Wait for the DOM, then for the
        # listing anchors to actually render.
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_selector(
                "a[href*='/realestate/item/']", timeout=15000
            )
        except PlaywrightTimeoutError:
            # No cards showed up (empty search, slow load, or a block page).
            # Return whatever rendered so the parser/debug dump can inspect it
            # rather than hard-failing the whole poll cycle.
            pass
        page.wait_for_timeout(1500)  # let any lazy-loaded cards settle
        html = page.content()
        browser.close()
        return html


def _parse_listing_card(anchor) -> dict | None:
    href = anchor.get("href", "")
    match = ITEM_HREF_RE.search(href)
    if not match:
        return None

    text = anchor.get_text(separator=" ", strip=True)
    if not text:
        return None

    price_match = PRICE_RE.search(text)
    price = int(price_match.group(1).replace(",", "")) if price_match else None

    rooms_match = ROOMS_RE.search(text)
    rooms = float(rooms_match.group(1)) if rooms_match else None

    size_match = SIZE_RE.search(text)
    size_sqm = int(size_match.group(1)) if size_match else None

    full_url = href if href.startswith("http") else f"https://www.yad2.co.il{href}"

    return {
        "id": match.group(1),
        "price": price,
        "rooms": rooms,
        "size_sqm": size_sqm,
        "title": text[:200],
        "url": full_url.split("?")[0],
    }


def fetch_listings(search_url: str, debug_dump: bool = False) -> list[dict]:
    html = _get_rendered_html(search_url)

    if debug_dump:
        with open(DEBUG_DUMP_PATH, "w", encoding="utf-8") as f:
            f.write(html)

    soup = BeautifulSoup(html, "html.parser")

    seen_ids = set()
    listings = []
    for anchor in soup.find_all("a", href=True):
        parsed = _parse_listing_card(anchor)
        if parsed and parsed["id"] not in seen_ids:
            seen_ids.add(parsed["id"])
            listings.append(parsed)

    return listings


def _empty_contact() -> dict:
    return {
        "contact_name": None,
        "phone": None,
        "agency_name": None,
        "is_agency": None,
    }


def _parse_customer(data: dict) -> dict:
    """Map Yad2's /customer JSON onto our contact fields. The advertiser may be
    a private person or a broker; brokers carry an agencyName (and is_agency
    lets the caller filter out תיווך listings if it wants)."""
    agency = data.get("agencyName")
    return {
        "contact_name": data.get("name"),
        "phone": data.get("phone"),
        "agency_name": agency,
        "is_agency": bool(agency),
    }


def fetch_contacts(listing_ids: list[str]) -> dict[str, dict]:
    """Fetch advertiser name + phone for each listing ID via Yad2's customer
    API. Returns {id: {contact_name, phone, agency_name, is_agency}}; an ID
    that fails maps to all-None values so callers can rely on the keys.

    Intended for NEW matches only, not every listing every cycle — that keeps
    it fast (usually 0 calls) and avoids hammering the API / tripping bot
    detection. One JSON GET per ID; no page render."""
    results: dict[str, dict] = {}
    if not listing_ids:
        return results

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=_LAUNCH_ARGS)
        context = _new_stealth_context(browser)
        try:
            for lid in listing_ids:
                try:
                    resp = context.request.get(
                        CUSTOMER_API.format(id=lid),
                        # Referer makes the gateway treat this like the site's
                        # own click on "show phone" rather than a bare hit.
                        headers={
                            "Referer": f"https://www.yad2.co.il/realestate/item/{lid}"
                        },
                    )
                    data = resp.json().get("data", {}) if resp.ok else {}
                    results[lid] = _parse_customer(data) if data else _empty_contact()
                except Exception:
                    results[lid] = _empty_contact()
        finally:
            browser.close()

    return results