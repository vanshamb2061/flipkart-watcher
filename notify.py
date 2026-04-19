"""
notify.py — sends to Discord webhook, email (Resend), and push (ntfy.sh)
All credentials are read from environment variables — never hardcode secrets.
"""

import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import requests

log = logging.getLogger(__name__)

# ── Env vars ────────────────────────────────────────────────────────────────────
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

NTFY_TOPIC          = os.environ.get("NTFY_TOPIC", "")          # e.g. vansh-flipkart-alerts
NTFY_SERVER         = os.environ.get("NTFY_SERVER", "https://ntfy.sh")

# Option A — Resend (recommended, free 3k/mo)
RESEND_API_KEY      = os.environ.get("RESEND_API_KEY", "")
EMAIL_FROM          = os.environ.get("EMAIL_FROM", "")          # e.g. alerts@yourdomain.com
EMAIL_TO            = os.environ.get("EMAIL_TO", "")            # your personal email

# Option B — Gmail SMTP (fallback, needs App Password)
GMAIL_USER          = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD  = os.environ.get("GMAIL_APP_PASSWORD", "")


# ── Discord ─────────────────────────────────────────────────────────────────────
def send_discord(product_name: str, price: str, url: str):
    if not DISCORD_WEBHOOK_URL:
        log.warning("DISCORD_WEBHOOK_URL not set — skipping Discord")
        return

    embed = {
        "title": "🛒 Back in stock!",
        "description": f"**{product_name}** is now available on Flipkart.",
        "color": 0x00B386,   # Flipkart-ish teal
        "fields": [
            {"name": "Price", "value": price or "Check link", "inline": True},
            {"name": "Link",  "value": f"[Buy now]({url})",   "inline": True},
        ],
        "footer": {"text": "flipkart-watcher"},
    }

    payload = {"embeds": [embed]}
    resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)

    if resp.status_code in (200, 204):
        log.info("  ✓ Discord notification sent")
    else:
        log.error(f"  Discord failed: {resp.status_code} {resp.text}")


# ── Ntfy push notification ───────────────────────────────────────────────────────
def send_ntfy(product_name: str, price: str, url: str):
    if not NTFY_TOPIC:
        log.warning("NTFY_TOPIC not set — skipping push notification")
        return

    resp = requests.post(
        f"{NTFY_SERVER}/{NTFY_TOPIC}",
        data=f"{product_name} is back in stock! {price}".encode("utf-8"),
        headers={
            "Title":    "Flipkart restock alert",
            "Priority": "high",
            "Tags":     "shopping_cart,tada",
            "Click":    url,
            "Actions":  f"view, Buy now, {url}, clear=true",
        },
        timeout=10,
    )

    if resp.status_code == 200:
        log.info("  ✓ Push notification sent (ntfy)")
    else:
        log.error(f"  ntfy failed: {resp.status_code} {resp.text}")


# ── Email via Resend ─────────────────────────────────────────────────────────────
def send_email_resend(product_name: str, price: str, url: str):
    if not RESEND_API_KEY or not EMAIL_TO or not EMAIL_FROM:
        log.warning("Resend env vars not set — skipping Resend email")
        return

    html = f"""
    <div style="font-family:sans-serif;max-width:520px;margin:0 auto">
      <h2 style="color:#00B386">🛒 Back in stock!</h2>
      <p><strong>{product_name}</strong> is now available on Flipkart.</p>
      <table style="margin:16px 0;border-collapse:collapse">
        <tr><td style="padding:4px 16px 4px 0;color:#666">Price</td><td><strong>{price}</strong></td></tr>
      </table>
      <a href="{url}" style="display:inline-block;padding:12px 24px;background:#00B386;color:#fff;border-radius:6px;text-decoration:none;font-weight:bold">
        Buy now on Flipkart →
      </a>
      <p style="margin-top:24px;color:#999;font-size:12px">Sent by flipkart-watcher</p>
    </div>
    """

    resp = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
        json={
            "from":    EMAIL_FROM,
            "to":      [EMAIL_TO],
            "subject": f"🛒 {product_name} is back in stock!",
            "html":    html,
        },
        timeout=15,
    )

    if resp.status_code in (200, 201):
        log.info("  ✓ Email sent (Resend)")
    else:
        log.error(f"  Resend failed: {resp.status_code} {resp.text}")


# ── Email via Gmail SMTP (fallback) ──────────────────────────────────────────────
def send_email_gmail(product_name: str, price: str, url: str):
    if not GMAIL_USER or not GMAIL_APP_PASSWORD or not EMAIL_TO:
        log.warning("Gmail SMTP env vars not set — skipping Gmail")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🛒 {product_name} is back in stock!"
    msg["From"]    = GMAIL_USER
    msg["To"]      = EMAIL_TO

    body = (
        f"{product_name} is back in stock on Flipkart!\n"
        f"Price: {price}\n"
        f"Link: {url}"
    )
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, EMAIL_TO, msg.as_string())
        log.info("  ✓ Email sent (Gmail SMTP)")
    except Exception as e:
        log.error(f"  Gmail SMTP failed: {e}")


# ── Dispatcher ──────────────────────────────────────────────────────────────────
def send_all(product_name: str, price: str, url: str):
    """Fire all configured notification channels."""
    send_discord(product_name, price, url)
    send_ntfy(product_name, price, url)

    # Use Resend if configured, otherwise fall back to Gmail
    if RESEND_API_KEY:
        send_email_resend(product_name, price, url)
    elif GMAIL_USER:
        send_email_gmail(product_name, price, url)
    else:
        log.warning("No email credentials configured — skipping email")
