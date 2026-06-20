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


def _listing_block(listing: dict) -> str:
    """Multi-line text summary of one listing, used inside a batch email."""
    price = listing["price"] if listing["price"] is not None else "?"
    rooms = listing["rooms"] if listing["rooms"] is not None else "?"
    return (
        f"₪{price} · {rooms} rooms\n"
        f"{listing['title']}\n"
        f"Contact: {_contact_line(listing)}\n"
        f"{listing['url']}"
    )


def notify_email_batch(listings: list, cfg: dict) -> None:
    """Send a single email containing all listings from one poll iteration."""
    if not cfg.get("enabled") or not listings:
        return
    n = len(listings)
    msg = EmailMessage()
    msg["Subject"] = f"{n} new apartment{'s' if n != 1 else ''}"
    msg["From"] = cfg["sender_address"]
    msg["To"] = cfg["recipient_address"]
    msg.set_content(
        f"{n} new matching listing{'s' if n != 1 else ''}:\n\n"
        + ("\n\n" + "-" * 40 + "\n\n").join(_listing_block(l) for l in listings)
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
    resp = requests.get(
        "https://api.callmebot.com/whatsapp.php",
        params={"phone": cfg["phone"], "text": text, "apikey": cfg["apikey"]},
        timeout=10,
    )
    # CallMeBot returns HTTP 200 even for some errors (e.g. bad apikey), so check
    # the body too — its error replies contain "APIKey" / "ERROR" / "not".
    body = resp.text.strip()
    if resp.status_code != 200 or any(
        s in body for s in ("ERROR", "APIKey is not valid", "not authorized", "not allowed")
    ):
        raise RuntimeError(f"CallMeBot rejected the message (HTTP {resp.status_code}): {body[:200]}")


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
