"""
Edit the settings below, then run: python main.py

Secrets (Gmail app password) are read from environment variables, NOT stored
in this file — so config.py is safe to commit. For local runs, put them in a
gitignored `.env` file next to this one (see `.env.example`); on GitHub
Actions they come from repository Secrets.

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

import os

# --- load .env for local dev (gitignored). CI provides real env vars, so this
# is a no-op there. Values already in the environment win over the file. ---
_envfile = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_envfile):
    with open(_envfile, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())


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
    "console": True,  # always-on; print() is the v1 notification channel

    "email": {
        "enabled": True,
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 465,
        "sender_address": "neoedan@gmail.com",
        # Gmail "App Password" (NOT your normal password). Comes from the
        # GMAIL_APP_PASSWORD env var (local .env file, or GitHub Secret).
        "app_password": os.environ.get("GMAIL_APP_PASSWORD", ""),
        "recipient_address": "neoedan@gmail.com",
    },

    "whatsapp": {
        "enabled": False,
        "phone": os.environ.get("CALLMEBOT_PHONE", ""),
        "apikey": os.environ.get("CALLMEBOT_APIKEY", ""),
    },
}

SEEN_STORE_PATH = "seen_listings.json"

# Set True to wipe the remembered listing IDs before a run, so every currently-
# listed apartment is treated as new again (you'll get re-notified about
# everything). Useful for a one-time test. Keep False for normal use — and
# especially on the hourly cron, or every run re-emails everything.
RESET_SEEN_LISTINGS = False
