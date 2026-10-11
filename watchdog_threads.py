#!/usr/bin/env python3
"""Watchdog untuk bot Threads — cek kesehatan websocket CDP tiap 5 menit,
restart Chrome otomatis kalau mati, kirim notifikasi Telegram."""

import json
import os
import subprocess
import sys
import time
import urllib.request
import datetime

# Konfigurasi
CHECK_INTERVAL = 300  # 5 menit
WS_TIMEOUT = 8
LOG_FILE = "/home/ubuntu/watchdog-log.txt"
TELEGRAM_BOT_TOKEN = "8766202285:AAFtzI3wpxrua9sYgO3K7YPwbxr8av7B1eo"
TELEGRAM_CHAT_ID = "1074643318"

# Chrome command per port (sama persis dengan yang jalan sekarang)
CHROME_CMDS = {
    9222: [
        "google-chrome", "--remote-debugging-port=9222",
        "--user-data-dir=/home/ubuntu/chrome-profile-bot",
        "--no-first-run", "--no-default-browser-check",
        "--remote-allow-origins=*", "--headless=new", "--noerrdialogs",
        "--ozone-platform=headless", "--disable-gpu", "--disable-dev-shm-usage",
        "--window-size=1280,900",
        # ── VERSI HEMAT RAM (+oliviapicks) ──
        "--renderer-process-limit=2",
        "--process-per-site",
        "--js-flags=--max-old-space-size=96",
        "--disable-features=BackForwardCache,MediaRouter,Translate,OptimizationHints,InterestFeedContentSuggestions,CalculateNativeWinOcclusion",
        "--disk-cache-size=10485760",
        "--disable-background-networking",
        "--metrics-recording-only",
        "--disable-component-update",
        "--disable-domain-reliability",
        "--no-pings",
        "--num-raster-threads=1",
    ],
    9223: [
        "google-chrome", "--remote-debugging-port=9223",
        "--user-data-dir=/home/ubuntu/chrome-profile-lanadealsrey2",
        "--no-first-run", "--no-default-browser-check",
        "--remote-allow-origins=*", "--headless=new", "--noerrdialogs",
        "--ozone-platform=headless", "--ozone-override-screen-size=1280,800",
        # ── VERSI HEMAT RAM (+lanadealsrey) ──
        "--renderer-process-limit=2",
        "--process-per-site",
        "--js-flags=--max-old-space-size=96",
        "--disable-features=BackForwardCache,MediaRouter,Translate,OptimizationHints,InterestFeedContentSuggestions,CalculateNativeWinOcclusion",
        "--disk-cache-size=10485760",
        "--disable-background-networking",
        "--metrics-recording-only",
        "--disable-component-update",
        "--disable-domain-reliability",
        "--no-pings",
        "--num-raster-threads=1",
    ],
    9226: [
        "google-chrome", "--remote-debugging-port=9226",
        "--user-data-dir=/home/ubuntu/chrome-profile-renaisher",
        "--no-first-run", "--no-default-browser-check",
        "--remote-allow-origins=*", "--headless=new", "--noerrdialogs",
        "--ozone-platform=headless", "--ozone-override-screen-size=1280,800",
        # ── VERSI HEMAT RAM (bertahap: +renaisher) ──
        "--renderer-process-limit=2",
        "--process-per-site",
        "--js-flags=--max-old-space-size=96",
        "--disable-features=BackForwardCache,MediaRouter,Translate,OptimizationHints,InterestFeedContentSuggestions,CalculateNativeWinOcclusion",
        "--disk-cache-size=10485760",
        "--disable-background-networking",
        "--metrics-recording-only",
        "--disable-component-update",
        "--disable-domain-reliability",
        "--no-pings",
        "--num-raster-threads=1",
    ],
    9227: [
        "google-chrome", "--remote-debugging-port=9227",
        "--user-data-dir=/home/ubuntu/chrome-profile-kailaaak7",
        "--no-first-run", "--no-default-browser-check",
        "--remote-allow-origins=*", "--headless=new", "--noerrdialogs",
        "--ozone-platform=headless", "--disable-gpu", "--disable-dev-shm-usage",
        "--window-size=1280,900",
        # ── VERSI HEMAT RAM (bertahap: +kailaaak7) ──
        "--renderer-process-limit=2",
        "--process-per-site",
        "--js-flags=--max-old-space-size=96",
        "--disable-features=BackForwardCache,MediaRouter,Translate,OptimizationHints,InterestFeedContentSuggestions,CalculateNativeWinOcclusion",
        "--disk-cache-size=10485760",
        "--disable-background-networking",
        "--metrics-recording-only",
        "--disable-component-update",
        "--disable-domain-reliability",
        "--no-pings",
        "--num-raster-threads=1",
    ],
    9228: [
        "google-chrome", "--remote-debugging-port=9228",
        "--user-data-dir=/home/ubuntu/chrome-profile-avelinefinds",
        "--no-first-run", "--no-default-browser-check",
        "--remote-allow-origins=*", "--headless=new", "--noerrdialogs",
        "--ozone-platform=headless", "--disable-gpu", "--disable-dev-shm-usage",
        "--window-size=1280,900",
        # ── VERSI HEMAT RAM (test selesai: menang 19% phase fresh, tidak merugikan steady-state) ──
        "--renderer-process-limit=2",
        "--process-per-site",
        "--js-flags=--max-old-space-size=96",
        "--disable-features=BackForwardCache,MediaRouter,Translate,OptimizationHints,InterestFeedContentSuggestions,CalculateNativeWinOcclusion",
        "--disk-cache-size=10485760",
        "--disable-background-networking",
        "--metrics-recording-only",
        "--disable-component-update",
        "--disable-domain-reliability",
        "--no-pings",
        "--num-raster-threads=1",
    ],
}


def log(msg: str) -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def send_telegram(msg: str) -> None:
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        log(f"Telegram error: {e}")


def ws_healthy(port: int) -> bool:
    """Cek apakah websocket CDP di port merespons."""
    try:
        with urllib.request.urlopen(f"http://localhost:{port}/json", timeout=5) as r:
            pages = json.loads(r.read())
        if not pages:
            return False
        ws_url = pages[0]["webSocketDebuggerUrl"]
        # Import di sini biar error jelas
        import websocket
        ws = websocket.create_connection(ws_url, timeout=WS_TIMEOUT)
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                            "params": {"expression": "1", "returnByValue": True}}))
        msg = json.loads(ws.recv())
        ws.close()
        return msg.get("id") == 1
    except Exception:
        return False


def chrome_running(port: int) -> bool:
    """Cek apakah ada proses Chrome dengan port tersebut."""
    try:
        out = subprocess.run(
            ["pgrep", "-f", f"remote-debugging-port={port} "],
            capture_output=True, text=True, timeout=5)
        return out.returncode == 0
    except Exception:
        return False


def restart_chrome(port: int) -> bool:
    """Kill lama, start baru via background start_new_session (cepat, tidak block, selamat dari gateway jika Chrome di app.slice)."""
    log(f"Restart Chrome {port}...")
    subprocess.run(["pkill", "-f", f"remote-debugging-port={port} "],
                   capture_output=True, timeout=10)
    time.sleep(3)
    import pathlib as _pl
    profile_map = {9222:"chrome-profile-bot",9223:"chrome-profile-lanadealsrey2",9226:"chrome-profile-renaisher",9227:"chrome-profile-kailaaak7",9228:"chrome-profile-avelinefinds"}
    prof = profile_map.get(port)
    if prof:
        for name in ("SingletonLock","SingletonCookie","SingletonSocket"):
            try:
                _pl.Path(f"/home/ubuntu/{prof}/{name}").unlink(missing_ok=True)
            except Exception:
                pass
    cmd = CHROME_CMDS.get(port)
    if not cmd:
        log(f"Tidak ada command untuk port {port}")
        return False
    try:
        devnull = open(os.devnull, "w")
        proc = subprocess.Popen(cmd, stdout=devnull, stderr=devnull, start_new_session=True)
        # tunggu WS hingga 12s tanpa block lama per port (cycle akan lanjut)
        for _ in range(12):
            time.sleep(1)
            if ws_healthy(port):
                log(f"Chrome {port} di-start ulang (PID {proc.pid}) — WS OK")
                return True
        if chrome_running(port):
            log(f"Chrome {port} di-start ulang (PID {proc.pid}) — proses hidup, WS pending")
            return True
        log(f"Chrome {port} PID {proc.pid} tidak hidup")
        return False
    except Exception as e:
        log(f"Gagal start Chrome {port}: {e}")
        return False


def clean_old_singletons():
    import pathlib as _pl
    for port in (9222,9223,9226,9227,9228):
        if not chrome_running(port):
            prof = {9222:"chrome-profile-bot",9223:"chrome-profile-lanadealsrey2",9226:"chrome-profile-renaisher",9227:"chrome-profile-kailaaak7",9228:"chrome-profile-avelinefinds"}.get(port)
            if prof:
                for name in ("SingletonLock","SingletonCookie","SingletonSocket"):
                    try:
                        _pl.Path(f"/home/ubuntu/{prof}/{name}").unlink(missing_ok=True)
                    except Exception:
                        pass


def main() -> None:
    log("Watchdog Threads v2 dimulai — cek port 9222,9223,9226,9227,9228 tiap 5 menit (service mode)")
    clean_old_singletons()

    while True:
        for port in (9222, 9223, 9226, 9227, 9228):
            if ws_healthy(port):
                continue
            log(f"⚠️ Port {port}: websocket mati")
            running = chrome_running(port)
            if running:
                log(f"Port {port}: Chrome masih jalan tapi WS mati → restart")
                ok = restart_chrome(port)
            else:
                log(f"Port {port}: Chrome tidak jalan → start")
                ok = restart_chrome(port)
            if ok:
                send_telegram(f"🛡️ Watchdog: Chrome port {port} di-restart (websocket mati). Bot akan pulih otomatis.")
            else:
                send_telegram(f"❌ Watchdog GAGAL restart Chrome port {port} — perlu cek manual!")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Watchdog dihentikan")
        sys.exit(0)
