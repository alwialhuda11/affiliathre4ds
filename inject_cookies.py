#!/usr/bin/env python3
"""
Inject cookies into Chrome via CDP.
Usage: python inject_cookies.py 9222 cookies/my_account.json
"""

import json
import sys
import urllib.request
import websocket


def get_cdp_ws(port: int) -> str:
    """Get WebSocket URL for CDP."""
    with urllib.request.urlopen(f"http://localhost:{port}/json", timeout=5) as r:
        pages = json.loads(r.read())
        return pages[0]["webSocketDebuggerUrl"]


def inject_cookies(port: int, cookies_file: str) -> bool:
    """Inject cookies from JSON file into Chrome."""
    # Load cookies
    with open(cookies_file, "r", encoding="utf-8") as f:
        cookies = json.load(f)

    if isinstance(cookies, dict):
        # Format: {"cookies": [...]} or single cookie object
        cookies = cookies.get("cookies", [cookies])
    elif isinstance(cookies, list):
        pass  # Already a list
    else:
        print(f"ERROR: Invalid cookies format in {cookies_file}")
        return False

    print(f"Loading {len(cookies)} cookies from {cookies_file}...")

    # Connect to CDP
    ws_url = get_cdp_ws(port)
    print(f"Connecting to Chrome CDP on port {port}...")
    ws = websocket.create_connection(ws_url, timeout=10)

    # Navigate to threads.net first
    print("Navigating to threads.net...")
    ws.send(json.dumps({
        "id": 1,
        "method": "Page.navigate",
        "params": {"url": "https://www.threads.net/"}
    }))
    ws.recv()  # Wait for response
    import time
    time.sleep(3)

    # Inject cookies
    success = 0
    for cookie in cookies:
        try:
            # Map cookie fields to CDP format
            cdp_cookie = {
                "name": cookie.get("name"),
                "value": cookie.get("value"),
                "domain": cookie.get("domain", ".threads.net"),
                "path": cookie.get("path", "/"),
                "secure": cookie.get("secure", True),
                "httpOnly": cookie.get("httpOnly", False),
                "sameSite": cookie.get("sameSite", "None"),
            }

            # Remove None values
            cdp_cookie = {k: v for k, v in cdp_cookie.items() if v is not None}

            # Set expiration if present
            if "expirationDate" in cookie:
                cdp_cookie["expires"] = cookie["expirationDate"]

            ws.send(json.dumps({
                "id": success + 2,
                "method": "Network.setCookie",
                "params": cdp_cookie
            }))
            resp = json.loads(ws.recv())
            if resp.get("result", {}).get("success"):
                success += 1
                print(f"  ✅ {cdp_cookie['name']}")
            else:
                print(f"  ❌ {cdp_cookie['name']}: {resp}")
        except Exception as e:
            print(f"  ❌ Error setting cookie: {e}")

    ws.close()
    print(f"\n✅ Injected {success}/{len(cookies)} cookies")

    # Verify by navigating
    print("Verifying login...")
    ws_url = get_cdp_ws(port)
    ws = websocket.create_connection(ws_url, timeout=10)
    ws.send(json.dumps({
        "id": 1,
        "method": "Page.navigate",
        "params": {"url": "https://www.threads.net/"}
    }))
    ws.recv()
    time.sleep(3)

    # Check if logged in by looking for username in page
    ws.send(json.dumps({
        "id": 2,
        "method": "Runtime.evaluate",
        "params": {"expression": "document.body.innerText.includes('@') || document.body.innerText.includes('For You')"}
    }))
    resp = json.loads(ws.recv())
    result = resp.get("result", {}).get("result", {}).get("value", False)

    ws.close()

    if result:
        print("✅ Login verified!")
        return True
    else:
        print("⚠️ Could not verify login. Please check cookies manually.")
        return False


def main():
    if len(sys.argv) < 3:
        print("Usage: python inject_cookies.py <port> <cookies_file>")
        print("Example: python inject_cookies.py 9222 cookies/my_account.json")
        sys.exit(1)

    port = int(sys.argv[1])
    cookies_file = sys.argv[2]

    inject_cookies(port, cookies_file)


if __name__ == "__main__":
    main()
