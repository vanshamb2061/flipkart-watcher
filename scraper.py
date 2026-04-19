"""
Flipkart Stock Watcher - scraper.py
Checks product stock status and fires notifications on change.
"""

import json
import os
import random
import time
import logging
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from notify import send_all

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/watcher.log"),
    ],
)
log = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
PRODUCTS = json.loads(os.environ.get("PRODUCTS", "[]"))
# PRODUCTS format (set as env var or edit directly):
# [
#   {"name": "OnePlus Buds Pro", "url": "https://www.flipkart.com/..."},
#   {"name": "Sony WH-1000XM5",  "url": "https://www.flipkart.com/..."}
# ]

STATE_FILE = Path("state.json")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]


# ── State helpers ───────────────────────────────────────────────────────────────
def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


# ── Stock check ─────────────────────────────────────────────────────────────────
def check_stock(url: str) -> dict:
    """
    Returns dict with keys:
        in_stock (bool), price (str|None), title (str|None)
    """
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-IN,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.google.com/",
    }

    # Polite delay — avoid hammering Flipkart
    time.sleep(random.uniform(2.0, 4.5))

    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # ── Title ──────────────────────────────────────────────────────────────────
    title_tag = (
        soup.find("span", class_="VU-ZEz")          # newer layout
        or soup.find("h1", {"class": lambda c: c and "G6XhRU" in c})
        or soup.find("span", {"class": lambda c: c and "B_NuCI" in c})
    )
    title = title_tag.get_text(strip=True) if title_tag else None

    # ── Price ──────────────────────────────────────────────────────────────────
    price_tag = (
        soup.find("div", class_="Nx9bqj")           # primary price div
        or soup.find("div", class_="_30jeq3")
    )
    price = price_tag.get_text(strip=True) if price_tag else None

    # ── Out of stock signals ───────────────────────────────────────────────────
    oos_phrases = [
        "currently unavailable",
        "sold out",
        "out of stock",
        "notify me",
    ]
    page_text = soup.get_text(separator=" ").lower()
    out_of_stock_text = any(p in page_text for p in oos_phrases)

    # "Add to Cart" button presence is the strongest in-stock signal
    add_to_cart = (
        soup.find("button", string=lambda t: t and "add to cart" in t.lower())
        or soup.find("button", string=lambda t: t and "buy now" in t.lower())
        or soup.find("a", string=lambda t: t and "add to cart" in t.lower())
    )

    in_stock = bool(add_to_cart) and not out_of_stock_text

    return {"in_stock": in_stock, "price": price, "title": title}


# ── Main loop ───────────────────────────────────────────────────────────────────
def run():
    if not PRODUCTS:
        log.error(
            "No products configured. Set the PRODUCTS environment variable.\n"
            'Example: \'[{"name":"Item","url":"https://www.flipkart.com/..."}]\''
        )
        return

    state = load_state()

    for product in PRODUCTS:
        name = product["name"]
        url  = product["url"]
        log.info(f"Checking: {name}")

        try:
            result = check_stock(url)
        except Exception as e:
            log.error(f"Failed to fetch {name}: {e}")
            continue

        in_stock  = result["in_stock"]
        price     = result.get("price", "N/A")
        title     = result.get("title") or name
        prev      = state.get(url, {}).get("in_stock")

        log.info(f"  → {'IN STOCK' if in_stock else 'out of stock'}  |  price: {price}")

        # Fire notification only when status changes TO in-stock
        if in_stock and prev is False:
            log.info(f"  🎉 RESTOCK DETECTED for {name} — sending notifications")
            send_all(
                product_name=title,
                price=price,
                url=url,
            )
        elif prev is None:
            log.info(f"  First run — baseline recorded (in_stock={in_stock})")

        state[url] = {
            "name": name,
            "in_stock": in_stock,
            "price": price,
            "last_checked": datetime.utcnow().isoformat(),
        }

    save_state(state)
    log.info("Run complete.\n")


if __name__ == "__main__":
    run()
