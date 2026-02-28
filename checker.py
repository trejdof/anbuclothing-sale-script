import os
import time
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# --- Configuration (set via environment variables) ---
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

PRODUCT_URLS = [
    "https://anbu-clothing.rs/product/yu-gi-oh-duks-332",
    # Add more product URLs here
]

CHECK_INTERVAL_SECONDS = 30 * 60  # 30 minutes

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def is_on_sale(url: str) -> tuple[bool, dict]:
    """
    Fetch the product page and check if the item is on sale.
    Returns (on_sale: bool, info: dict with price details).
    """
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Method 1: Check JSON-LD structured data for compareAtPrice vs current price
    import json
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                data = data[0] if data else {}
            offers = data.get("offers", {})
            if isinstance(offers, list):
                offers = offers[0] if offers else {}

            compare_at = offers.get("compareAtPrice", {})
            if isinstance(compare_at, dict):
                compare_amount = float(compare_at.get("amount", 0))
            else:
                compare_amount = 0

            low_price = float(offers.get("lowPrice", offers.get("price", 0)))

            if compare_amount > 0 and compare_amount > low_price:
                return True, {
                    "current_price": low_price,
                    "original_price": compare_amount,
                    "currency": offers.get("priceCurrency", "RSD"),
                    "url": url,
                }
        except (json.JSONDecodeError, TypeError, ValueError):
            continue

    # Method 2: Fallback — look for sale/discount text on the page
    page_text = soup.get_text()
    sale_keywords = ["nedeljno sniženje", "ušteda", "sniženje", "rasprodaja"]
    for keyword in sale_keywords:
        if keyword.lower() in page_text.lower():
            return True, {"url": url, "reason": f"Found keyword: '{keyword}'"}

    return False, {"url": url}


def send_telegram_notification(product_url: str, info: dict) -> None:
    """Send a Telegram notification via the Bot API."""
    current = info.get("current_price", "N/A")
    original = info.get("original_price", "N/A")
    currency = info.get("currency", "RSD")
    reason = info.get("reason", "")

    if current != "N/A" and original != "N/A":
        text = (
            f"🛍 Item on sale!\n"
            f"Price: {current} {currency} (was {original} {currency})\n"
            f"{product_url}"
        )
    elif reason:
        text = f"🛍 Item on sale! ({reason})\n{product_url}"
    else:
        text = f"🛍 Item on sale!\n{product_url}"

    response = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
        timeout=10,
    )

    if response.ok:
        print(f"[OK] Notification sent for {product_url}")
    else:
        print(f"[ERROR] Failed to send notification: {response.status_code} {response.text}")


def check_all_products() -> None:
    print(f"Checking {len(PRODUCT_URLS)} product(s)...")
    for url in PRODUCT_URLS:
        try:
            on_sale, info = is_on_sale(url)
            if on_sale:
                print(f"[SALE] {url} — {info}")
                send_telegram_notification(url, info)
            else:
                print(f"[no sale] {url}")
        except Exception as e:
            print(f"[ERROR] Could not check {url}: {e}")


def main() -> None:
    print("Anbu Clothing sale checker started.")
    print(f"Checking every {CHECK_INTERVAL_SECONDS // 60} minutes.\n")

    while True:
        check_all_products()
        print(f"Next check in {CHECK_INTERVAL_SECONDS // 60} minutes...\n")
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
