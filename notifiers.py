"""
Notification channels. Console is on by default. Email and WhatsApp are
fully implemented but off until you flip "enabled": True in config.py and
fill in the credentials.
"""

import smtplib
import ssl
from email.message import EmailMessage

import requests


def _contact_line(listing: dict) -> str:
    """One-line 'name · phone (agency)' summary, tolerant of missing pieces."""
    name = listing.get("contact_name") or "?"
    phone = listing.get("phone") or "?"
    line = f"{name} · {phone}"
    agency = listing.get("agency_name")
    if agency:
        line += f" (agency: {agency})"
    return line


def notify_console(listing: dict) -> None:
    price = listing["price"] if listing["price"] is not None else "?"
    rooms = listing["rooms"] if listing["rooms"] is not None else "?"
    print("=" * 60)
    print(f"NEW LISTING — ₪{price} · {rooms} rooms")
    print(listing["title"])
    print(f"contact: {_contact_line(listing)}")
    print(listing["url"])
    print("=" * 60)


def notify_email(listing: dict, cfg: dict) -> None:
    if not cfg.get("enabled"):
        return
    msg = EmailMessage()
    msg["Subject"] = f"New apartment: ₪{listing['price']} · {listing['rooms']} rooms"
    msg["From"] = cfg["sender_address"]
    msg["To"] = cfg["recipient_address"]
    msg.set_content(
        f"{listing['title']}\n\n"
        f"Contact: {_contact_line(listing)}\n"
        f"{listing['url']}"
    )

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(cfg["smtp_host"], cfg["smtp_port"], context=context) as server:
        server.login(cfg["sender_address"], cfg["app_password"])
        server.send_message(msg)


def notify_whatsapp(listing: dict, cfg: dict) -> None:
    if not cfg.get("enabled"):
        return
    text = (
        f"New apartment: ₪{listing['price']} · {listing['rooms']} rooms\n"
        f"Contact: {_contact_line(listing)}\n"
        f"{listing['url']}"
    )
    # CallMeBot — free WhatsApp API for personal use. See README for 1-time setup.
    requests.get(
        "https://api.callmebot.com/whatsapp.php",
        params={"phone": cfg["phone"], "text": text, "apikey": cfg["apikey"]},
        timeout=10,
    )


def notify_all(listing: dict, notifications_cfg: dict) -> None:
    if notifications_cfg.get("console"):
        notify_console(listing)

    try:
        notify_email(listing, notifications_cfg.get("email", {}))
    except Exception as e:
        print(f"  (email notification failed: {e!r})")

    try:
        notify_whatsapp(listing, notifications_cfg.get("whatsapp", {}))
    except Exception as e:
        print(f"  (whatsapp notification failed: {e!r})")
