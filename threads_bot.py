#!/usr/bin/env python3
"""
Threads Affiliate Bot - Universal Version
Usage: python threads_bot.py --cookies cookies/my_account.json --port 9222

Args:
  --cookies: Path to cookies JSON file
  --port: Chrome debugging port (default: 9222)
  --interval-min: Min interval between posts in minutes (default: 45)
  --interval-max: Max interval between posts in minutes (default: 90)
  --account-name: Account name for logging (default: from cookies filename)
"""

import argparse
import json
import os
import random
import sys
import time
import urllib.request
import websocket

# ========================
# CONFIG (CLI args)
# ========================
CDP_HOST = "localhost"
AFFILIATE_LINKS_FILE = "config/affiliate-links.json"
POSTED_LINKS_FILE = "posted_links.json"
LOG_FILE = "logs/bot.log"

# Default values
CHROME_PORT = 9222
POST_INTERVAL_MIN = 45
POST_INTERVAL_MAX = 90
ACCOUNT_NAME = "threads"
TELEGRAM_BOT_TOKEN = None  # Set via env var if needed
TELEGRAM_CHAT_ID = None


def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    os.makedirs(os.path.dirname(LOG_FILE) or "logs", exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def send_telegram(msg: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        log(f"Telegram error: {e}")


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_cookies(path: str) -> list:
    """Load cookies from JSON file."""
    return load_json(path)


def load_affiliate_links() -> list:
    """Load affiliate links from config file."""
    try:
        data = load_json(AFFILIATE_LINKS_FILE)
        return data.get("links", [])
    except FileNotFoundError:
        log(f"ERROR: {AFFILIATE_LINKS_FILE} not found!")
        return []


def get_posted_links() -> set:
    """Get set of already posted links."""
    try:
        return set(load_json(POSTED_LINKS_FILE).get("links", []))
    except FileNotFoundError:
        return set()


def save_posted_link(link: str) -> None:
    """Save a posted link to avoid duplicates."""
    posted = get_posted_links()
    posted.add(link)
    save_json(POSTED_LINKS_FILE, {"links": list(posted)})


# ========================
# CDP FUNCTIONS
# ========================
def get_cdp_ws(port: int) -> str:
    """Get WebSocket URL for CDP."""
    try:
        with urllib.request.urlopen(f"http://localhost:{port}/json", timeout=5) as r:
            pages = json.loads(r.read())
            return pages[0]["webSocketDebuggerUrl"]
    except Exception as e:
        log(f"ERROR: Cannot connect to CDP port {port}: {e}")
        sys.exit(1)


def cdp_send(ws, method: str, params: dict = None) -> dict:
    """Send CDP command and return result."""
    params = params or {}
    ws.send(json.dumps({"id": random.randint(1, 999999), "method": method, "params": params}))
    while True:
        msg = json.loads(ws.recv())
        if "result" in msg:
            return msg.get("result", {})
        elif "exceptionDetails" in msg:
            return {"error": msg.get("exceptionDetails", {})}


def cdp_navigate(ws, url: str) -> bool:
    """Navigate to URL."""
    try:
        cdp_send(ws, "Page.navigate", {"url": url})
        time.sleep(3)
        return True
    except Exception as e:
        log(f"Navigation error: {e}")
        return False


def cdp_click(ws, x: int, y: int) -> bool:
    """Click at x,y coordinates."""
    try:
        cdp_send(ws, "Input.dispatchMouseEvent", {
            "type": "mousePressed",
            "x": x, "y": y,
            "button": "left",
            "clickCount": 1
        })
        cdp_send(ws, "Input.dispatchMouseEvent", {
            "type": "mouseReleased",
            "x": x, "y": y,
            "button": "left",
            "clickCount": 1
        })
        return True
    except Exception as e:
        log(f"Click error: {e}")
        return False


def cdp_type(ws, text: str) -> bool:
    """Type text."""
    try:
        cdp_send(ws, "Input.insertText", {"text": text})
        return True
    except Exception as e:
        log(f"Type error: {e}")
        return False


def cdp_press(ws, key: str) -> bool:
    """Press a key."""
    try:
        cdp_send(ws, "Input.dispatchKeyEvent", {"type": "keyDown", "key": key})
        cdp_send(ws, "Input.dispatchKeyEvent", {"type": "keyUp", "key": key})
        return True
    except Exception as e:
        log(f"Press error: {e}")
        return False


# ========================
# BOT LOGIC
# ========================
def do_one_post(ws, affiliate_links: list, posted_links: set, attempt: int = 1) -> bool:
    """Execute one post attempt."""
    log(f"[Attempt {attempt}] Starting post...")

    # Filter out already posted links
    available_links = [l for l in affiliate_links if l not in posted_links]
    if not available_links:
        available_links = affiliate_links  # Reset if all posted
        log("All links posted, resetting...")

    affiliate_link = random.choice(available_links)
    log(f"Selected link: {affiliate_link}")

    # Step 1: Open main Threads page
    log("Step 1: Opening Threads...")
    cdp_navigate(ws, "https://www.threads.net/")
    time.sleep(4)

    # Step 2: Find a post (scroll or click on "For You")
    log("Step 2: Finding post...")
    # Click at Reply counter position (788, 301) - typical for first post
    if not cdp_click(ws, 788, 301):
        log("Clicking alternative position...")
        cdp_click(ws, 600, 400)

    time.sleep(2)

    # Step 3: Click comment field
    log("Step 3: Opening comment field...")
    cdp_click(ws, 604, 321)
    time.sleep(2)

    # Step 4: Type affiliate link
    log("Step 4: Typing comment...")
    cdp_type(ws, affiliate_link)
    time.sleep(1)

    # Step 5: Press Enter to post
    log("Step 5: Posting...")
    cdp_press(ws, "Enter")
    time.sleep(3)

    # Save posted link
    save_posted_link(affiliate_link)
    log(f"✅ Posted: {affiliate_link}")

    # Send notification
    send_telegram(f"✅ Threads Bot - {ACCOUNT_NAME}\nPost berhasil!\nLink: {affiliate_link}\n\nDone, Posted!")

    return True


def main():
    global CHROME_PORT, POST_INTERVAL_MIN, POST_INTERVAL_MAX, ACCOUNT_NAME
    global TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, LOG_FILE, AFFILIATE_LINKS_FILE

    parser = argparse.ArgumentParser(description="Threads Affiliate Bot")
    parser.add_argument("--cookies", required=True, help="Path to cookies JSON file")
    parser.add_argument("--port", type=int, default=9222, help="Chrome debugging port")
    parser.add_argument("--interval-min", type=int, default=45, help="Min interval (minutes)")
    parser.add_argument("--interval-max", type=int, default=90, help="Max interval (minutes)")
    parser.add_argument("--account-name", help="Account name for logging")
    parser.add_argument("--telegram-token", help="Telegram bot token")
    parser.add_argument("--telegram-chat-id", help="Telegram chat ID")
    parser.add_argument("--config", default="config/affiliate-links.json", help="Affiliate links config")
    parser.add_argument("--log", default="logs/bot.log", help="Log file path")

    args = parser.parse_args()

    # Apply args
    CHROME_PORT = args.port
    POST_INTERVAL_MIN = args.interval_min
    POST_INTERVAL_MAX = args.interval_max
    ACCOUNT_NAME = args.account_name or os.path.splitext(os.path.basename(args.cookies))[0]
    TELEGRAM_BOT_TOKEN = args.telegram_token or os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = args.telegram_chat_id or os.getenv("TELEGRAM_CHAT_ID")
    AFFILIATE_LINKS_FILE = args.config
    LOG_FILE = args.log

    log(f"=" * 50)
    log(f"🤖 Threads Bot - Universal")
    log(f"   Account: {ACCOUNT_NAME}")
    log(f"   Port: {CHROME_PORT}")
    log(f"   Interval: {POST_INTERVAL_MIN}-{POST_INTERVAL_MAX} min")
    log(f"   Cookies: {args.cookies}")
    log(f"=" * 50)

    # Verify cookies file exists
    if not os.path.exists(args.cookies):
        log(f"ERROR: Cookies file not found: {args.cookies}")
        sys.exit(1)

    # Load affiliate links
    affiliate_links = load_affiliate_links()
    if not affiliate_links:
        log("ERROR: No affiliate links found!")
        sys.exit(1)
    log(f"Loaded {len(affiliate_links)} affiliate links")

    # Get posted links
    posted_links = get_posted_links()
    log(f"Already posted: {len(posted_links)} links")

    # Connect to CDP
    ws_url = get_cdp_ws(CHROME_PORT)
    log(f"Connecting to CDP: {ws_url}")
    ws = websocket.create_connection(ws_url, timeout=10)
    log("Connected to Chrome!")

    consecutive_failures = 0
    attempt = 0

    try:
        while True:
            attempt += 1
            success = do_one_post(ws, affiliate_links, posted_links, attempt)

            if success:
                interval = random.randint(POST_INTERVAL_MIN, POST_INTERVAL_MAX)
                consecutive_failures = 0
                log(f"✅ Next post in {interval} minutes...")
            else:
                interval = random.randint(5, 10)
                consecutive_failures += 1
                log(f"⚠️ Failed, retry in {interval} min (consecutive: {consecutive_failures})")

                if consecutive_failures >= 3:
                    send_telegram(f"⚠️ Threads Bot - {ACCOUNT_NAME}\n{consecutive_failures}x failed consecutively!\nCheck cookies/suspension.")

            time.sleep(interval * 60)

    except KeyboardInterrupt:
        log("Bot stopped by user")
    finally:
        ws.close()


if __name__ == "__main__":
    main()
