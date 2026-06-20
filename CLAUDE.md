# CLAUDE.md

Guidance for working in this repo.

## What this is

A personal apartment-watcher bot. It polls a [Yad2](https://www.yad2.co.il)
rental search on a fixed interval, parses the listing cards, filters by
rooms/price, and notifies you about *new* matches it hasn't shown before.
Single-user, run-from-the-terminal tool — no server, no DB, no tests.

## Run it

```bash
pip install -r requirements.txt
playwright install chromium   # one-time; installs the Chromium binary, separate from the pip package
python main.py                # polls forever; Ctrl+C to stop
```

There is a `.venv/` in the repo (Python 3.14). Activate it or use its
interpreter rather than system Python.

## Architecture (4 files, plus state)

- **`config.py`** — all user settings. The only file an end user edits.
  `SEARCH_URL` (copied from a real Yad2 browser search — the neighborhood
  filter isn't URL-guessable), `ROOMS_MIN/MAX` + `PRICE_MIN/MAX` (a
  safety-net filter restated on top of Yad2's own), `POLL_INTERVAL_SECONDS`,
  and the `NOTIFICATIONS` dict.
- **`yad2_client.py`** — two fetchers, both using the shared
  `_new_stealth_context` browser setup:
  - `fetch_listings(url)` renders the search page with Playwright and parses
    cards. Returns `list[dict]` with keys `id, price, rooms, size_sqm, title,
    url`. (Search cards carry no contact info — that's a separate call.)
  - `fetch_contacts(ids)` resolves the advertiser per listing via Yad2's
    `gw.yad2.co.il/realestate-item/{id}/customer` JSON API (one cheap GET
    each, no page render). Returns `{id: {contact_name, phone, agency_name,
    is_agency}}`; failures map to all-None so the keys are always present.
- **`notifiers.py`** — `notify_all(listing, cfg)` fans out to console
  (always on), email (SMTP/Gmail app-password), and WhatsApp (CallMeBot).
  All three include `_contact_line()` (name · phone (agency)). Email/WhatsApp
  are no-ops unless `enabled: True` in config; failures in one channel are
  caught and printed, never crash the loop.
- **`main.py`** — the poll loop. `run_once()` fetches listings, skips
  already-seen IDs, applies the range filters to collect new matches, calls
  `fetch_contacts()` for just those matches (usually none), drops broker
  listings when `SKIP_AGENCY` is set, then notifies. Returns the count
  actually notified. The loop saves state and swallows per-cycle exceptions
  so a transient failure just retries next cycle.
- **`seen_listings.json`** — persisted set of listing IDs already seen, so
  there are no repeat alerts across restarts. Written every cycle. Not
  config; it's runtime state.

## Conventions / things to know

- **Yad2 is behind ShieldSquare/Imperva bot detection — the stealth setup in
  `_get_rendered_html` is load-bearing.** A vanilla headless browser gets
  served a CAPTCHA page (`<title>ShieldSquare Captcha</title>` / `אבטחת אתר`)
  instead of results; the parser then finds 0 listings and every cycle reports
  "0 new match(es)" even when matches exist online. What gets past it:
  `--disable-blink-features=AutomationControlled`, removing
  `navigator.webdriver` via an init script, and a consistent real-browser
  context (UA + `he-IL` locale + `Asia/Jerusalem` timezone + viewport +
  `Accept-Language`). Don't strip these without re-testing. To confirm a block
  vs. a genuinely-empty search, run with `debug_dump=True` and grep the dump
  for `ShieldSquare`/`captcha`.
- **Never use `wait_until="networkidle"` in `_get_rendered_html`.** Yad2
  runs continuous background traffic (analytics + bot-detection beacons), so
  the "no network for 500ms" condition often never occurs and `goto()` raises
  `TimeoutError` — reliably on the 2nd+ poll once bot-detection has warmed
  up. The page load instead waits on `domcontentloaded` + a bounded
  `wait_for_selector` for the listing anchors, degrading gracefully if no
  cards appear. Don't reintroduce `networkidle`.
- **Parsing is text/regex-based, not CSS-class-based** — deliberately. Yad2
  changes its markup often; the regexes match patterns like `₪ 7,500` and
  `3 חדרים` (Hebrew). If listings stop being found, that's the first
  suspect. Debug with `fetch_listings(config.SEARCH_URL, debug_dump=True)`,
  which dumps rendered HTML to `last_page_debug.html`.
- **A listing is "new" the first time its ID is seen** — it's added to the
  seen-set *before* the range filters, so a filtered-out listing won't
  re-notify later if its price/rooms change. Keep that ordering in mind in
  `run_once()`.
- **`in_range(None, ...)` returns True** — listings whose price/rooms failed
  to parse are kept, not dropped, on purpose.
- **Agency filtering uses `is_agency`, not a text match on תיווך.** A listing
  is treated as broker/agency when Yad2's contact API returns an `agencyName`
  (many agency names don't literally contain the word תיווך). When the
  contact lookup fails, `is_agency` is `None` and the listing is kept rather
  than silently dropped. Toggle with `SKIP_AGENCY` in config.
- **Hebrew strings and RTL** appear throughout config and parsing. Files are
  read/written with `encoding="utf-8"` and JSON with `ensure_ascii=False` —
  preserve that.
- **Polite scraping matters.** `POLL_INTERVAL_SECONDS` is `60`. Sub-minute
  polling is what really risks getting the IP flagged / soft-blocked; 5–10
  min is gentler for long-running use. Don't lower it below 60.
- **Secrets** (Gmail app password, CallMeBot apikey) live in `config.py`.
  Keep them out of commits.

## Known TODO

None outstanding — contact name/phone capture and broker (תיווך) filtering
are both done.
