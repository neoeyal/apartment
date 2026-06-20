"""
Edit the settings below, then run: python main.py

STEP 1 — get your Yad2 search URL (one-time, ~30 seconds):
  1. Go to https://www.yad2.co.il/realestate/rent
  2. In the location box, type your neighborhood (e.g. "רמת אביב") and pick
     it from the autocomplete dropdown. This is the only reliable way to set
     Yad2's neighborhood filter — it's not a guessable URL parameter.
  3. Set room count and price range using the filter panel.
  4. Click "חיפוש" (Search), then copy the full URL from your browser's
     address bar and paste it below as SEARCH_URL.
  5. Tip: there's also a "מי המפרסם" (advertiser type) filter — leave
     "תיווך" (agency) unchecked if you only want private/no-broker listings.

STEP 2 — restate your rooms/price here too. This is used as a safety-net
filter on top of Yad2's own filtering, in case anything slightly outside
your range slips through.
"""

# Just for your own reference / shown in logs — doesn't drive the search.
PROMPT = "where: ramat aviv | rooms: 2-3 | price: 5k-8k"

SEARCH_URL = "https://www.yad2.co.il/realestate/rent/tel-aviv-area?area=1&city=5000&neighborhood=197"

ROOMS_MIN = 2
ROOMS_MAX = 3
PRICE_MIN = 5000
PRICE_MAX = 8000

POLL_INTERVAL_SECONDS = 60

# Skip broker/agency (תיווך) listings — i.e. only notify about private
# advertisers. A listing counts as agency if Yad2's contact API returns an
# agencyName for it. Set False to include broker listings too.
SKIP_AGENCY = True

NOTIFICATIONS = {
    "console": True,  # always-on for now; print() is the v1 notification channel

    "email": {
        "enabled": False,
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 465,
        "sender_address": "",       # e.g. "[email protected]"
        "app_password": "",         # Gmail "App Password" (NOT your normal password) — see README
        "recipient_address": "",    # where to send alerts (can be the same address)
    },

    "whatsapp": {
        "enabled": False,
        "phone": "",   # your number, international format, digits only (e.g. "9725XXXXXXXX")
        "apikey": "",  # from CallMeBot — see README for the 1-time signup
    },
}

SEEN_STORE_PATH = "seen_listings.json"

# Set True to wipe the remembered listing IDs before the first poll, so every
# currently-listed apartment is treated as new again (you'll get re-notified
# about everything). Useful for testing or starting fresh. Leave False for
# normal use.
RESET_SEEN_LISTINGS = True
