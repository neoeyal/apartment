import json
import sys
import time
from datetime import datetime

import config
from yad2_client import fetch_contacts, fetch_listings
from notifiers import notify_console, notify_email_batch, notify_whatsapp


def load_seen() -> set:
    try:
        with open(config.SEEN_STORE_PATH, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_seen(seen_ids: set) -> None:
    with open(config.SEEN_STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(seen_ids), f, ensure_ascii=False, indent=2)


def in_range(value, lo, hi) -> bool:
    if value is None:
        return True  # don't silently drop listings we failed to parse a number for
    return lo <= value <= hi


def run_once(seen_ids: set) -> int:
    listings = fetch_listings(config.SEARCH_URL)

    new_matches = []
    for listing in listings:
        if listing["id"] in seen_ids:
            continue
        seen_ids.add(listing["id"])

        if not in_range(listing["price"], config.PRICE_MIN, config.PRICE_MAX):
            continue
        if not in_range(listing["rooms"], config.ROOMS_MIN, config.ROOMS_MAX):
            continue

        new_matches.append(listing)

    # Contact name/phone live behind a per-listing API call, so we fetch them
    # only for the new matches (usually none) rather than every listing.
    contacts = fetch_contacts([listing["id"] for listing in new_matches])

    # Apply the agency filter first, so the "printed"/"sent" counts below
    # reflect what's actually being notified.
    to_notify = []
    for listing in new_matches:
        listing.update(contacts.get(listing["id"], {}))
        # Skip broker/agency (תיווך) listings if configured. is_agency is None
        # when the contact lookup failed — treat that as "unknown, don't drop".
        if config.SKIP_AGENCY and listing.get("is_agency"):
            continue
        to_notify.append(listing)

    if not to_notify:
        return 0

    n = len(to_notify)

    # --- console / log phase ---
    if config.NOTIFICATIONS.get("console"):
        print(f"printing to log.. ({n} listing(s))")
        for listing in to_notify:
            notify_console(listing)
        print(f"finished printing to log.. {n} printed")

    # --- email phase --- one email per iteration, listing all matches
    email_cfg = config.NOTIFICATIONS.get("email", {})
    if email_cfg.get("enabled"):
        print(f"sending in mail.. ({n} listing(s) in one email)")
        try:
            notify_email_batch(to_notify, email_cfg)
            print(f"sent mail.. {n} listing(s) sent")
        except Exception as e:
            print(f"  (email notification failed: {e!r})")

    # --- whatsapp phase (still off unless enabled in config) ---
    for listing in to_notify:
        try:
            notify_whatsapp(listing, config.NOTIFICATIONS.get("whatsapp", {}))
        except Exception as e:
            print(f"  (whatsapp notification failed: {e!r})")

    return n


def _setup_seen() -> set:
    if config.RESET_SEEN_LISTINGS:
        seen_ids = set()
        save_seen(seen_ids)
        print("Reset seen listings — starting fresh.\n")
    else:
        seen_ids = load_seen()
        print(f"Loaded {len(seen_ids)} previously-seen listing IDs.\n")
    return seen_ids


def run_forever() -> None:
    seen_ids = _setup_seen()
    while True:
        ts = datetime.now().strftime("%H:%M:%S")
        try:
            new_count = run_once(seen_ids)
            save_seen(seen_ids)
            print(f"[{ts}] checked — {new_count} new match(es)")
        except Exception as e:
            print(f"[{ts}] error during check: {e!r} (will retry next cycle)")
        time.sleep(config.POLL_INTERVAL_SECONDS)


def run_single() -> int:
    """One check, then exit — used by the hourly GitHub Actions cron so the
    job runs once and the runner shuts down (no forever-loop on CI)."""
    seen_ids = _setup_seen()
    ts = datetime.now().strftime("%H:%M:%S")
    new_count = run_once(seen_ids)
    save_seen(seen_ids)
    print(f"[{ts}] checked — {new_count} new match(es)")
    return new_count


def main() -> None:
    once = "--once" in sys.argv
    print(f"Watching: {config.PROMPT}")
    if once:
        print("Running a single check (--once), then exiting.\n")
        run_single()
    else:
        print(f"Polling every {config.POLL_INTERVAL_SECONDS}s. Ctrl+C to stop.\n")
        run_forever()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(0)
