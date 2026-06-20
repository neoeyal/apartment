import json
import sys
import time
from datetime import datetime

import config
from yad2_client import fetch_contacts, fetch_listings
from notifiers import notify_all


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
    notified = 0
    for listing in new_matches:
        listing.update(contacts.get(listing["id"], {}))
        # Skip broker/agency (תיווך) listings if configured. is_agency is None
        # when the contact lookup failed — treat that as "unknown, don't drop".
        if config.SKIP_AGENCY and listing.get("is_agency"):
            continue
        notify_all(listing, config.NOTIFICATIONS)
        notified += 1

    return notified


def main() -> None:
    print(f"Watching: {config.PROMPT}")
    print(f"Polling every {config.POLL_INTERVAL_SECONDS}s. Ctrl+C to stop.\n")

    if config.RESET_SEEN_LISTINGS:
        seen_ids = set()
        save_seen(seen_ids)
        print("Reset seen listings — starting fresh.\n")
    else:
        seen_ids = load_seen()
        print(f"Loaded {len(seen_ids)} previously-seen listing IDs.\n")

    while True:
        ts = datetime.now().strftime("%H:%M:%S")
        try:
            new_count = run_once(seen_ids)
            save_seen(seen_ids)
            print(f"[{ts}] checked — {new_count} new match(es)")
        except Exception as e:
            print(f"[{ts}] error during check: {e!r} (will retry next cycle)")
        time.sleep(config.POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(0)
