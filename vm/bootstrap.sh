#!/bin/bash
# ============================================================
# VM BOOTSTRAP — Threads Bot (MIRROR PERSIS VPS)
# Jalan OTOMATIS tiap VM boot (cloud-init / startup script).
# Hasil: layout /home/ubuntu identik dengan VPS — bot, watchdog,
# cron, Chrome profiles, semua di path yang sama.
#
# ── ISI SEKALI DI BAWAH INI (token disimpan di cloud console,
#    bukan di VM, jadi selamat tiap reset) ──────────────────
GH_TOKEN="GH_TOKEN_DI_SINI"
# ============================================================
set -e

REPO="https://x-access-token:${GH_TOKEN}@github.com/alwialhuda11/affiliathre4ds.git"
VPS_HOME="/home/ubuntu"          # path identik dengan VPS
LOG="/var/log/threads-bot-bootstrap.log"
exec > >(tee -a "$LOG") 2>&1

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
log "=== VM BOOTSTRAP START ==="

export DEBIAN_FRONTEND=noninteractive

# ── 0. User + home identik VPS ──
id ubuntu >/dev/null 2>&1 || useradd -m -s /bin/bash ubuntu
mkdir -p "$VPS_HOME"

# ── 1. Dependencies (sama seperti VPS) ──
apt-get update -qq
apt-get install -y -qq python3 python3-pip git curl wget gnupg procps cron psmisc >/dev/null
if ! command -v google-chrome >/dev/null 2>&1; then
    log "Installing Google Chrome..."
    wget -qO /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
    apt-get install -y -qq /tmp/chrome.deb >/dev/null
    rm -f /tmp/chrome.deb
fi
pip3 install -q requests websocket-client 2>/dev/null || \
    pip3 install -q --break-system-packages requests websocket-client

# ── 2. Git credentials (token dari startup script) ──
cat > "$VPS_HOME/.git-credentials" <<EOF
https://x-access-token:${GH_TOKEN}@github.com
EOF
chmod 600 "$VPS_HOME/.git-credentials"
sudo -u ubuntu git config --global credential.helper store 2>/dev/null || \
    git config --global credential.helper store

# ── 3. Clone / update repo → /home/ubuntu (layout persis VPS) ──
if [ -d "$VPS_HOME/.git" ]; then
    log "Updating repo..."
    sudo -u ubuntu git -C "$VPS_HOME" pull --rebase --autostash origin master --quiet || true
else
    log "Cloning repo to $VPS_HOME..."
    rm -rf "$VPS_HOME.new"
    sudo -u ubuntu git clone --quiet "$REPO" "$VPS_HOME.new"
    # pindahkan isi ke /home/ubuntu (kalau home sudah ada file lain, merge)
    cp -a "$VPS_HOME.new/." "$VPS_HOME/"
    rm -rf "$VPS_HOME.new"
fi
chown -R ubuntu:ubuntu "$VPS_HOME"
cd "$VPS_HOME"

# ── 4. State restore (replied_posts + posted_links — dedup history VPS) ──
for f in replied_posts.json posted_links.json recent_comments.json recent_categories.json; do
    [ -f "state/$f" ] && cp "state/$f" "./$f" && log "Restored $f"
done
chown ubuntu:ubuntu ./*.json 2>/dev/null || true

# ── 5. Chrome profiles (path identik VPS, dibuat watchdog) ──
# watchdog_threads.py CHROME_CMDS sudah hardcode /home/ubuntu/chrome-profile-*
# jadi clone ke /home/ubuntu = otomatis persis.

# ── 6. Start watchdog (jaga Chrome, port 9222-9228) ──
log "Starting watchdog..."
sudo -u ubuntu bash -c "cd $VPS_HOME && setsid /usr/bin/python3 -u watchdog_threads.py >> watchdog-log.txt 2>&1 < /dev/null &"

# ── 7. Tunggu Chrome siap, lalu inject cookies per akun ──
# (VPS: cookies baked ke profile sekali; VM: profile reset tiap boot → inject tiap boot)
log "Waiting for Chrome CDP ports..."
for port in 9222 9223 9225 9226 9227 9228; do
    for i in $(seq 1 30); do
        curl -sf "http://localhost:$port/json" >/dev/null 2>&1 && break
        sleep 2
    done
done

declare -A COOKIE_MAP=(
    [9222]=oliviapicks
    [9223]=lanadealsrey
    [9225]=selenasupply
    [9226]=renaisher2
    [9227]=kailaaak72
    [9228]=avelinefinds
)
for port in "${!COOKIE_MAP[@]}"; do
    acct="${COOKIE_MAP[$port]}"
    cookie_file="$VPS_HOME/cookies/${acct}.json"
    if [ -f "$cookie_file" ]; then
        log "Injecting cookies: $acct → port $port"
        sudo -u ubuntu /usr/bin/python3 "$VPS_HOME/inject_cookies.py" "$port" "$cookie_file" \
            >> "$VPS_HOME/bot-${acct}.log" 2>&1 || log "inject $acct returned non-zero (cek log)"
    else
        log "⚠️ cookies/$acct.json tidak ada — skip inject"
    fi
done

# ── 8. Launch semua bot (sama seperti keep_bot_alive di VPS) ──
log "Starting bots..."
sudo -u ubuntu bash -c "cd $VPS_HOME && bash keep_bot_alive.sh >> keep_alive.log 2>&1"

# ── 9. Crontab identik VPS (watchdog guard + keep_alive) + state sync ──
log "Installing crontab..."
CRON_FILE="/tmp/threads-cron"
cat > "$CRON_FILE" <<EOF
# ===== THREADS BOT — VM (mirror VPS) =====
*/5 * * * * pgrep -f "watchdog_thread[s].py" >/dev/null || setsid /usr/bin/python3 -u $VPS_HOME/watchdog_threads.py >> $VPS_HOME/watchdog-log.txt 2>&1 < /dev/null
*/5 * * * * $VPS_HOME/keep_bot_alive.sh >> $VPS_HOME/keep_alive.log 2>&1
*/5 * * * * bash $VPS_HOME/vm/state-sync.sh >> $VPS_HOME/state-sync.log 2>&1
EOF
crontab -u ubuntu "$CRON_FILE"
rm -f "$CRON_FILE"

# ── 10. State sync pertama (push current state ke GitHub) ──
sudo -u ubuntu bash "$VPS_HOME/vm/state-sync.sh" >> "$VPS_HOME/state-sync.log" 2>&1 || true

log "=== VM BOOTSTRAP COMPLETE ==="
log "Bot jalan: $(pgrep -cf 'python3 -u threads_bot_' || echo 0) proses"
log "Chrome jalan: $(pgrep -cf 'chrome.*remote-debugging-port' || echo 0) instances"
