#!/usr/bin/env python3
"""
Watchdog - Auto-restart Chrome if WebSocket dies.
Usage: python watchdog.py 9222,9223,9225

Args:
  --ports: Comma-separated list of Chrome debugging ports to monitor
  --interval: Check interval in seconds (default: 300 = 5 minutes)
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
import datetime


LOG_FILE = "logs/watchdog.log"


def log(msg: str) -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    os.makedirs(os.path.dirname(LOG_FILE) or "logs", exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def ws_healthy(port: int) -> bool:
    """Check if CDP WebSocket responds."""
    try:
        with urllib.request.urlopen(f"http://localhost:{port}/json", timeout=5) as r:
            pages = json.loads(r.read())
        if not pages:
            return False
        ws_url = pages[0]["webSocketDebuggerUrl"]
        
        import websocket
        ws = websocket.create_connection(ws_url, timeout=8)
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                            "params": {"expression": "1", "returnByValue": True}}))
        msg = json.loads(ws.recv())
        ws.close()
        return msg.get("id") == 1
    except Exception:
        return False


def chrome_running(port: int) -> bool:
    """Check if Chrome process is running."""
    try:
        out = subprocess.run(
            ["pgrep", "-f", f"remote-debugging-port={port} "],
            capture_output=True, text=True, timeout=5)
        return out.returncode == 0
    except Exception:
        return False


def restart_chrome(port: int, user_data_dir: str = None) -> bool:
    """Restart Chrome on given port."""
    if user_data_dir is None:
        user_data_dir = f"~/chrome-profile-{port}"
    
    log(f"Restarting Chrome {port}...")
    subprocess.run(["pkill", "-f", f"remote-debugging-port={port} "],
                   capture_output=True, timeout=10)
    time.sleep(3)
    
    cmd = [
        "google-chrome",
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--remote-allow-origins=*",
        "--headless=new",
        "--noerrdialogs",
        "--disable-gpu",
    ]
    
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        start_new_session=True)
        log(f"Chrome {port} restarted (PID will be assigned)")
        return True
    except Exception as e:
        log(f"Failed to restart Chrome {port}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Threads Bot Watchdog")
    parser.add_argument("--ports", default="9222", help="Comma-separated ports to monitor")
    parser.add_argument("--interval", type=int, default=300, help="Check interval in seconds")
    parser.add_argument("--auto-restart", action="store_true", default=True,
                       help="Auto-restart Chrome if WebSocket dies")
    
    args = parser.parse_args()
    
    ports = [int(p.strip()) for p in args.ports.split(",")]
    
    log(f"Watchdog started - monitoring ports: {ports} (every {args.interval}s)")
    
    while True:
        for port in ports:
            if ws_healthy(port):
                continue
            
            log(f"⚠️ Port {port}: WebSocket dead")
            running = chrome_running(port)
            
            if args.auto_restart:
                if running:
                    log(f"Chrome still running but WS dead → restart")
                    ok = restart_chrome(port)
                else:
                    log(f"Chrome not running → start")
                    ok = restart_chrome(port)
                
                if ok:
                    log(f"✅ Chrome {port} restarted")
                else:
                    log(f"❌ Failed to restart Chrome {port}")
            
        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Watchdog stopped")
        sys.exit(0)
