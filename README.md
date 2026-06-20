# Apartment Watcher (Yad2)

Polls a Yad2 rental search every N seconds and notifies you when a new
listing appears that matches your rooms/price range. Console output for
now; email and WhatsApp are built in and ready to switch on.

## Why Yad2 and not Facebook groups?

Facebook's Terms of Service prohibit automated scraping/login, their Groups
API doesn't expose post content to third-party apps anymore, and bots get
flagged fast (CAPTCHAs, checkpoints, account bans) — at a 1-minute polling
interval especially. That risk isn't worth it for a personal tool.

Yad2 is the dominant Israeli rental platform and already has native,
structured filters for neighborhood, rooms, and price — so there's no need
to fuzzy-match anything. If you specifically want private/no-broker
listings (the usual reason people prefer Facebook groups), use Yad2's "מי
המפרסם" (advertiser type) filter and leave "תיווך" (agency) unchecked.

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
```

1. Open `config.py`.
2. Go to https://www.yad2.co.il/realestate/rent in your browser, type your
   neighborhood into the location box and pick it from the dropdown, set
   your room and price range in the filter panel, hit search, then copy
   the resulting URL into `SEARCH_URL`.
3. Set `ROOMS_MIN/MAX` and `PRICE_MIN/MAX` to match (used as a backup
   filter on top of Yad2's own).
   - By default, broker/agency (תיווך) listings are filtered out so you only
     get private advertisers. Set `SKIP_AGENCY = False` in `config.py` to
     include brokers too.
4. Run it:

```bash
python main.py
```

It checks every 1 minute by default (`POLL_INTERVAL_SECONDS` in
config.py), prints new matches, and remembers what it's already shown you
in `seen_listings.json` so you won't get repeats — even across restarts.

### Starting fresh

If you want to be re-notified about every currently-listed apartment (e.g.
when testing, or after changing your search), set `RESET_SEEN_LISTINGS =
True` in `config.py`. On the next run it wipes the remembered IDs before the
first poll, so everything counts as new again. Flip it back to `False`
afterwards, otherwise every restart will re-spam you with all current
listings.

## Turning on email

1. Go to your Google Account → Security → 2-Step Verification → App
   Passwords, and generate one for "Mail".
2. In `config.py`, under `NOTIFICATIONS["email"]`, set `"enabled": True`
   and fill in `sender_address`, `app_password` (the one you just
   generated, not your real password), and `recipient_address`.

## Turning on WhatsApp

Uses [CallMeBot](https://www.callmebot.com/) — a free third-party API for
personal use (not official WhatsApp/Meta, and it can hit capacity limits).

1. Add the CallMeBot phone number shown on their WhatsApp page to your
   contacts, send it the activation message they specify, and they'll
   message you back an `apikey`.
2. In `config.py`, under `NOTIFICATIONS["whatsapp"]`, set `"enabled": True`
   and fill in your `phone` and the `apikey`.

If reliability matters more than cost, Twilio's official WhatsApp Business
API is the alternative — more setup, but no third-party dependency.

## If it stops finding listings

First, dump what the page actually returned:

```python
import config
from yad2_client import fetch_listings
fetch_listings(config.SEARCH_URL, debug_dump=True)
```

This saves the rendered page to `last_page_debug.html`. Open it (or grep it)
and check which of these you're hitting:

- **A CAPTCHA / "אבטחת אתר" (ShieldSquare) page** instead of results — Yad2's
  bot detection flagged the browser. `yad2_client.py` already includes
  stealth measures (hiding the automation flag, realistic browser context)
  that normally get past it; if it's blocking again, slow the poll interval
  down and try a fresh run a few minutes later. This is also the usual cause
  of "0 new match(es)" every cycle when there are clearly matches online.
- **Normal results, but no matches parsed** — Yad2 likely changed their
  markup. The parser looks for text patterns (`₪ 7,500`, `3 חדרים`) rather
  than CSS class names, which is more stable but not bulletproof; check
  whether the price/room patterns in the dump still look the same and update
  the regexes in `yad2_client.py` if not.

## Be a polite scraper

The default is 1-minute polling. That's fine for personal use, but it's
close to the line — sub-minute polling is what really risks getting your
IP flagged or soft-blocked by Yad2's bot detection. If you plan to leave
it running for long stretches, 5–10 minutes is gentler and still plenty
fast for catching new listings.
