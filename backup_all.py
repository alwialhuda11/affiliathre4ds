#!/usr/bin/env python3
"""Backup script — package everything critical so the VPS can be rebuilt.

Extracts:
- Threads cookies from each running Chrome profile (via CDP)
- Bot scripts, config, tracker files, watchdog
- Technocore identities (identity.pem + passphrase) for ALL accounts
- Notes/plans

Outputs a single timestamped .tar.gz under /home/ubuntu/backups/
"""

import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request

BACKUP_ROOT = "/home/ubuntu/backups"
STAGING = tempfile.mkdtemp(prefix="backup-staging-")
TS = time.strftime("%Y%m%d_%H%M%S")

CHROME_PORTS = {9222: "oliviapicks", 9223: "lanadealsrey"}


def log(msg: str) -> None:
    print(f"[backup] {msg}", flush=True)


def extract_cookies(port: int, account: str) -> None:
    """Pull cookies from a live Chrome via CDP and save as JSON."""
    try:
        import websocket  # may not be installed; handled below
        with urllib.request.urlopen(f"http://localhost:{port}/json", timeout=5) as r:
            pages = json.loads(r.read())
        if not pages:
            log(f"  {account}: no pages, skip")
            return
        ws = websocket.create_connection(pages[0]["webSocketDebuggerUrl"], timeout=10)
        ws.send(json.dumps({"id": 1, "method": "Network.getAllCookies", "params": {}}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == 1:
                break
        ws.close()
        cookies = msg.get("result", {}).get("cookies", [])
        path = os.path.join(STAGING, "cookies")
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, f"{account}.cookies.json"), "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2)
        log(f"  {account}: {len(cookies)} cookies saved")
    except Exception as e:
        log(f"  {account}: cookie extract failed ({e})")


def main() -> int:
    log(f"staging: {STAGING}")
    os.makedirs(BACKUP_ROOT, exist_ok=True)

    # 1. Cookies from live Chrome profiles
    log("extracting cookies from live Chrome...")
    for port, account in CHROME_PORTS.items():
        extract_cookies(port, account)

    # 2. Bot scripts + config + trackers
    log("copying bot files...")
    for f in os.listdir("/home/ubuntu"):
        if f.startswith("threads_bot_") and f.endswith(".py"):
            shutil.copy2(os.path.join("/home/ubuntu", f), STAGING)
    shutil.copy2("/home/ubuntu/watchdog_threads.py", STAGING)
    for f in ["replied_posts.json", "posted_links.json",
              "recent_comments.json", "recent_categories.json"]:
        p = os.path.join("/home/ubuntu", f)
        if os.path.exists(p):
            shutil.copy2(p, STAGING)
    cfg = os.path.join("/home/ubuntu", "config", "affiliate-links.json")
    if os.path.exists(cfg):
        os.makedirs(os.path.join(STAGING, "config"), exist_ok=True)
        shutil.copy2(cfg, os.path.join(STAGING, "config"))

    # 3. Technocore identities (ALL accounts)
    log("copying Technocore identities...")
    identity_src = os.path.join(STAGING, "technocore-identities")
    os.makedirs(identity_src, exist_ok=True)

    # Central backup folder (accounts 1-5)
    if os.path.exists("/home/ubuntu/technocore-backup"):
        for f in sorted(os.listdir("/home/ubuntu/technocore-backup")):
            shutil.copy2(os.path.join("/home/ubuntu/technocore-backup", f), identity_src)

    # Original DID starter identity (account 1 primary)
    for f in ["identity.pem", ".did_passphrase"]:
        p = os.path.join("/home/ubuntu/technocore-did-starter", f)
        if os.path.exists(p):
            shutil.copy2(p, identity_src)

    # Per-project identity dirs (accounts 2-5)
    projects = [
        "technocore-telegram-monitor", "technocore-docs-id",
        "technocore-proof-verifier", "technocore-room-analyzer",
        "technocore-harmonia", "technocore-mcp-server",
        "technocore-client-ts", "technocore-client",
        "technocore-contribution-action", "technocore-explorer",
    ]
    for proj in projects:
        idir = os.path.join("/home/ubuntu", proj, "identity")
        if os.path.isdir(idir):
            dst = os.path.join(identity_src, proj)
            os.makedirs(dst, exist_ok=True)
            for f in os.listdir(idir):
                shutil.copy2(os.path.join(idir, f), dst)

    # 4. Notes / plans
    for f in ["flop-orchestrator-plan.md"]:
        p = os.path.join("/home/ubuntu/plans", f)
        if os.path.exists(p):
            shutil.copy2(p, STAGING)

    # 5. README with restore instructions
    with open(os.path.join(STAGING, "RESTORE.md"), "w", encoding="utf-8") as f:
        f.write(RESTORE_MD)

    # 6. Archive
    archive = os.path.join(BACKUP_ROOT, f"full-backup-{TS}.tar.gz")
    log(f"archiving to {archive} ...")
    with tarfile.open(archive, "w:gz") as tar:
        for name in os.listdir(STAGING):
            tar.add(os.path.join(STAGING, name), arcname=name)
    shutil.rmtree(STAGING)
    size = os.path.getsize(archive) / 1024
    log(f"DONE: {archive} ({size:.0f} KB)")
    print(archive)
    return 0


RESTORE_MD = """# Restore Instructions

## What this backup contains
- `cookies/<account>.cookies.json` — Threads session cookies for each account
  (oliviapicks, lanadealsrey). Import into a fresh Chrome profile
  via CDP `Network.setCookies` after relaunching Chrome.
- `threads_bot_*.py` — the bot scripts.
- `watchdog_threads.py` — the auto-restart watchdog.
- `replied_posts.json`, `posted_links.json`, etc. — posting trackers.
- `config/affiliate-links.json` — affiliate links.
- `technocore-identities/` — ALL Technocore identity.pem + passphrases.
  Keep these safe: losing them means losing the DIDs forever.

## On a fresh VPS
1. Reinstall Google Chrome (headless) and start it on the same ports.
2. Import cookies via CDP.
3. Run `python3 threads_bot_<account>.py` for each account.
4. Run `python3 -u watchdog_threads.py`.
5. Technocore identities go back into `/home/ubuntu/technocore-*` projects.
6. Source code is already on GitHub (re-clone from there).
"""

if __name__ == "__main__":
    sys.exit(main())
