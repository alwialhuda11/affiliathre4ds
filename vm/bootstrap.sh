#!/bin/bash
# ============================================================
# VM BOOTSTRAP — Threads Bot
# Jalan OTOMATIS tiap VM boot (via cloud-init / startup script)
# Sumber: GitHub affiliathre4ds (private)
# ============================================================
set -e

REPO_URL="https://github.com/alwialhuda11/affiliathre4ds.git"
WORK_DIR="/opt/threads-bot"
LOG_FILE="/var/log/threads-bot-bootstrap.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }

log "=== BOOTSTRAP START ==="

# ── 1. Install dependencies (sekali tiap boot) ──
if ! command -v python3 &>/dev/null; then
    apt-get update -qq && apt-get install -y -qq python3 python3-pip git curl
fi

if ! command -v google-chrome &>/dev/null && ! command -v chromium-browser &>/dev/null; then
    log "Installing Chrome..."
    wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb -O /tmp/chrome.deb
    apt-get install -y -qq /tmp/chrome.deb || apt-get install -y -qq chromium-browser
    rm -f /tmp/chrome.deb
fi

pip3 install -q requests websocket-client 2>/dev/null || pip3 install -q --break-system-packages requests websocket-client

# ── 2. Clone / update repo ──
if [ -d "$WORK_DIR/.git" ]; then
    log "Updating repo..."
    cd "$WORK_DIR" && git pull --rebase origin main 2>/dev/null || git pull --rebase origin master
else
    log "Cloning repo..."
    git clone "$REPO_URL" "$WORK_DIR"
    cd "$WORK_DIR"
fi

# ── 3. Pull latest state dari GitHub (replied_posts, posted_links) ──
# State files sudah di-commit ke repo oleh sync loop sebelumnya
if [ -f "state/replied_posts.json" ]; then
    cp state/replied_posts.json ./
    log "Restored replied_posts.json ($(wc -c < replied_posts.json) bytes)"
fi
if [ -f "state/posted_links.json" ]; then
    cp state/posted_links.json ./
    log "Restored posted_links.json"
fi
if [ -f "state/recent_comments.json" ]; then
    cp state/recent_comments.json ./
fi
if [ -f "state/recent_categories.json" ]; then
    cp state/recent_categories.json ./
fi

# ── 4. Setup config ──
mkdir -p config
if [ ! -f "config/affiliate-links.json" ] && [ -f "config/affiliate-links.json.example" ]; then
    cp config/affiliate-links.json.example config/affiliate-links.json
fi

# ── 5. Launch watchdog (jaga Chrome tetap hidup) ──
log "Starting watchdog..."
setsid python3 -u watchdog_threads.py >> watchdog-log.txt 2>&1 < /dev/null &

# ── 6. Launch semua bot ──
log "Starting bots..."
for bot in threads_bot_oliviapicks.py threads_bot_lanadealsrey.py threads_bot_selenasupply.py threads_bot_avelinefinds.py threads_bot_kailaaak72.py threads_bot_renaisher2.py; do
    if [ -f "$bot" ]; then
        name=$(echo "$bot" | sed 's/threads_bot_//;s/.py//')
        setsid python3 -u "$bot" >> "bot-${name}.log" 2>&1 < /dev/null &
        log "Started $name (PID $!)"
        sleep 2
    fi
done

# ── 7. Start state sync loop (push state ke GitHub tiap 5 menit) ──
log "Starting state sync loop..."
setsid bash -c '
    cd /opt/threads-bot
    while true; do
        sleep 300
        mkdir -p state
        cp replied_posts.json state/ 2>/dev/null || true
        cp posted_links.json state/ 2>/dev/null || true
        cp recent_comments.json state/ 2>/dev/null || true
        cp recent_categories.json state/ 2>/dev/null || true
        git add state/ 2>/dev/null || true
        git commit -m "state sync $(date +%H:%M)" --allow-empty-message 2>/dev/null || true
        git push origin main 2>/dev/null || git push origin master 2>/dev/null || true
    done
' >> sync-loop.log 2>&1 < /dev/null &

log "=== BOOTSTRAP COMPLETE ==="
log "Bots running. State sync every 5 min."
