# flipkart-watcher

Monitors Flipkart product pages and fires notifications the moment something comes back in stock — via Discord, email, and a push notification on your phone.

---

## What you get

| Channel | Tool | Cost |
|---|---|---|
| Push notification | ntfy.sh (Android/iOS app) | Free |
| Email | Resend or Gmail SMTP | Free |
| Discord DM / channel | Discord webhook | Free |

---

## Setup (15 minutes total)

### 1. Clone & install

```bash
git clone https://github.com/YOU/flipkart-watcher
cd flipkart-watcher
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure products

Copy `.env.example` to `.env` and edit:

```bash
cp .env.example .env
```

Set `PRODUCTS` to the items you want to watch:

```
PRODUCTS=[{"name":"OnePlus Buds Pro 2","url":"https://www.flipkart.com/..."}]
```

**How to get a good Flipkart URL:**
- Go to the product page
- Copy the URL from the address bar
- Remove everything after `?` (query params aren't needed)
- Make sure the URL contains `/p/itm` — that's the canonical product URL

### 3. Set up notification channels

#### Push (ntfy.sh) — easiest, do this first
1. Install the **ntfy** app ([Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy) / [iOS](https://apps.apple.com/app/ntfy/id1625396347))
2. In the app, tap **+** and subscribe to a topic — invent a random name like `vansh-alerts-9z3k` (make it obscure)
3. Set `NTFY_TOPIC=vansh-alerts-9z3k` in your `.env`

#### Discord webhook
1. Open your Discord server → any channel → Edit Channel → Integrations → Webhooks → New Webhook
2. Copy the webhook URL
3. Set `DISCORD_WEBHOOK_URL=` in your `.env`

#### Email (Resend — recommended)
1. Sign up at [resend.com](https://resend.com) — free, no credit card
2. Create an API key
3. Set `RESEND_API_KEY`, `EMAIL_FROM`, `EMAIL_TO` in your `.env`

> **No domain?** Use Gmail SMTP instead. Generate an App Password at myaccount.google.com → Security → App Passwords. Uncomment the `GMAIL_*` lines in `.env`.

### 4. Test locally

```bash
# Load env and run once
export $(cat .env | xargs) && python scraper.py
```

Check `logs/watcher.log` — you should see the stock status for each product. You won't get a notification on the first run (it's setting the baseline). To force-test notifications, edit `state.json` and set `"in_stock": false` for a product you know is in stock, then run again.

### 5. Deploy to Railway (free, permanent)

1. Push to a **private** GitHub repo (keeps your `.env` secret — never commit it)
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub repo
3. Under **Variables**, add all your env vars from `.env`
4. Railway reads `railway.toml` and runs the scraper every 10 minutes automatically

That's it. No server to manage.

---

## Tuning the check interval

Edit `railway.toml`:

```toml
cronSchedule = "*/5 * * * *"    # every 5 minutes
cronSchedule = "*/10 * * * *"   # every 10 minutes (default)
cronSchedule = "0 * * * *"      # once per hour
```

Don't go below 5 minutes — Flipkart may start returning 429s.

---

## If scraping breaks

Flipkart occasionally ships CSS class name changes. If the scraper stops detecting stock correctly:

1. Open the product page in Chrome → right-click "Add to Cart" → Inspect
2. Note the button's class names
3. Update the `add_to_cart` selector in `scraper.py`

Alternatively, swap to `playwright` for a more robust headless approach:

```bash
pip install playwright && playwright install chromium
```

Then replace the `requests.get` block in `scraper.py` with:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto(url, wait_until="networkidle")
    html = page.content()
    browser.close()

soup = BeautifulSoup(html, "html.parser")
```

---

## State file

`state.json` tracks the last known status per URL so notifications only fire on *changes*. Safe to delete — the next run rebuilds it.
