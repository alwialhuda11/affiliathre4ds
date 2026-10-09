#!/bin/bash
# ============================================================
# VM BOOTSTRAP v2 — Threads Bot (MIRROR VPS + RAM MITIGATION)
# Jalan OTOMATIS tiap VM boot. Dirancang buat VM RAM-capped:
# - Swap 4GB (VM reset tiap 2 jam -> swap dibuat ulang tiap boot)
# - Chrome di-tune hemat RAM (renderer=1, js-heap=48M, cache=1M)
# - RAM gate: available < 1.2GB -> cuma 3 akun (watchdog di-patch,
#   Chrome akun inactive gak di-launch sama sekali = hemat RAM)
# - Stagger launch 8s/bot (gak burst 6 Chrome sekaligus)
#
# ── ISI SEKALI (token disimpan di cloud console, selamat tiap reset) ──
GH_TOKEN="GH_TOKEN_DI_SINI"
# ============================================================
set -e

REPO="https://x-access-token:${GH_TOKEN}@github.com/alwialhuda11/affiliathre4ds.git"
VPS_HOME="/home/ubuntu"
LOG="/var/log/threads-bot-bootstrap.log"
exec > >(tee -a "$LOG") 2>&1

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
log "=== VM BOOTSTRAP v2 START ==="

export DEBIAN_FRONTEND=noninteractive

# ── 0. User + home identik VPS ──
id ubuntu >/dev/null 2>&1 || useradd -m -s /bin/bash ubuntu
mkdir -p "$VPS_HOME"

# ── 0b. RAM DIAGNOSTIC — log siapa yang makan RAM ──
log "--- RAM sebelum mitigasi ---"
free -h
log "Top RAM consumers:"
ps aux --sort=-rss | head -11 | awk 'NR>1{printf "  %.0fMB %s %s\n", $6/1024, $1, $11}'

# ── 0c. SWAP 4GB (wajib — VM RAM-capped) ──
if ! swapon --show | grep -q .; then
    log "Buat swap 4GB..."
    fallocate -l 4G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=4096 status=none
    chmod 600 /swapfile
    mkswap /swapfile >/dev/null
    swapon /swapfile
    grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
    sysctl -w vm.swappiness=60 >/dev/null
    log "Swap aktif:"
    swapon --show
fi

# ── 0d. earlyoom — throttle proses boros sebelum kernel OOM (best-effort) ──
if ! command -v earlyoom >/dev/null 2>&1; then
    apt-get install -y -qq earlyoom >/dev/null 2>&1 && \
    systemctl enable --now earlyoom 2>/dev/null && \
    log "earlyoom aktif (proteksi OOM)" || log "earlyoom skip (gak fatal)"
fi

# ── 1. Dependencies ──
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

# ── 2. Git credentials ──
cat > "$VPS_HOME/.git-credentials" <<EOF
https://x-access-token:${GH_TOKEN}@github.com
EOF
chmod 600 "$VPS_HOME/.git-credentials"
sudo -u ubuntu git config --global credential.helper store 2>/dev/null || \
    git config --global credential.helper store

# ── 3. Clone / update repo → /home/ubuntu ──
if [ -d "$VPS_HOME/.git" ]; then
    log "Updating repo..."
    sudo -u ubuntu git -C "$VPS_HOME" pull --rebase --autostash origin master --quiet || true
else
    log "Cloning repo to $VPS_HOME..."
    rm -rf "$VPS_HOME.new"
    sudo -u ubuntu git clone --quiet "$REPO" "$VPS_HOME.new"
    cp -a "$VPS_HOME.new/." "$VPS_HOME/"
    rm -rf "$VPS_HOME.new"
fi
chown -R ubuntu:ubuntu "$VPS_HOME"
cd "$VPS_HOME"

# ── 4. Chrome TUNE hemat RAM (VM aja; VPS copy gak disentuh) ──
# JANGAN ubah --window-size / ozone-override: bot klik koordinat tetap (788,301)!
sed -i 's/--renderer-process-limit=2/--renderer-process-limit=1/g;
        s/--max-old-space-size=96/--max-old-space-size=48/g;
        s/--disk-cache-size=10485760/--disk-cache-size=1048576/g' watchdog_threads.py
log "Chrome di-tune: renderer=1, js-heap=48M, disk-cache=1M"

# ── 5. State restore ──
for f in replied_posts.json posted_links.json recent_comments.json recent_categories.json; do
    [ -f "state/$f" ] && cp "state/$f" "./$f" && log "Restored $f"
done
chown ubuntu:ubuntu ./*.json 2>/dev/null || true

# ── 6. RAM GATE — tentuin akun aktif dari available RAM ──
# Chrome hemat ~170MB/akun + bot ~25MB. Swap udah aktif di 0c.
AVAIL_MB=$(free -m | awk '/^Mem:/{print $7}')
ALL_ACCOUNTS="threads_bot_oliviapicks.py
threads_bot_lanadealsrey.py
threads_bot_selenasupply.py
threads_bot_renaisher2.py
threads_bot_kailaaak72.py
threads_bot_avelinefinds.py"
THREE_ACCOUNTS="threads_bot_avelinefinds.py
threads_bot_oliviapicks.py
threads_bot_selenasupply.py"

if [ "$AVAIL_MB" -lt 1200 ]; then
    log "RAM available ${AVAIL_MB}MB -> jalanin 3 akun aja (accounts.txt)"
    printf '%s\n' "$THREE_ACCOUNTS" > accounts.txt
else
    log "RAM available ${AVAIL_MB}MB -> jalanin semua 6 akun"
    printf '%s\n' "$ALL_ACCOUNTS" > accounts.txt
fi
chown ubuntu:ubuntu accounts.txt
log "accounts.txt:"
cat accounts.txt

# ── 6b. Patch watchdog: Chrome akun inactive GAK di-launch ──
# Port mapping: oliviapicks=9222 lanadealsrey=9223 selenasupply=9225
#               renaisher2=9226 kailaaak72=9227 avelinefinds=9228
sudo -u ubuntu /usr/bin/python3 - "$VPS_HOME" <<'PYEOF'
import sys, re
home = sys.argv[1]
with open(f"{home}/accounts.txt") as f:
    active = f.read()
acct_port = {
    "oliviapicks": 9222, "lanadealsrey": 9223, "selenasupply": 9225,
    "renaisher2": 9226, "kailaaak72": 9227, "avelinefinds": 9228,
}
active_ports = [p for a, p in acct_port.items() if a in active]
wd_path = f"{home}/watchdog_threads.py"
with open(wd_path) as f:
    wd = f.read()
# CHROME_CMDS dict entries: "    PORT: [ ... ]," -> hapus entry port inactive
inactive = [p for p in acct_port.values() if p not in active_ports]
removed = 0
for port in inactive:
    pat = re.compile(rf"    {port}: \[.*?\n    \],\n", re.DOTALL)
    wd, n = pat.subn("", wd)
    removed += n
with open(wd_path, "w") as f:
    f.write(wd)
print(f"watchdog patched: {removed} chrome entries dihapus (port inactive {inactive})")
print(f"active ports: {active_ports}")
PYEOF

# ── 7. Start watchdog (jaga Chrome — cuma port aktif) ──
log "Starting watchdog (hanya Chrome port aktif)..."
sudo -u ubuntu bash -c "cd $VPS_HOME && setsid /usr/bin/python3 -u watchdog_threads.py >> watchdog-log.txt 2>&1 < /dev/null &"

# ── 8. Tunggu Chrome siap -> inject cookies HANYA akun aktif ──
log "Waiting for Chrome CDP ports..."
sleep 15
declare -A COOKIE_MAP=(
    [9222]=oliviapicks
    [9223]=lanadealsrey
    [9225]=selenasupply
    [9226]=renaisher2
    [9227]=kailaaak72
    [9228]=avelinefinds
)
ACTIVE_LIST=$(cat accounts.txt)
for port in 9222 9223 9225 9226 9227 9228; do
    acct="${COOKIE_MAP[$port]}"
    if ! echo "$ACTIVE_LIST" | grep -q "$acct"; then
        continue
    fi
    for i in $(seq 1 30); do
        curl -sf "http://localhost:$port/json" >/dev/null 2>&1 && break
        sleep 2
    done
    cookie_file="$VPS_HOME/cookies/${acct}.json"
    if [ -f "$cookie_file" ]; then
        log "Injecting cookies: $acct -> port $port"
        sudo -u ubuntu /usr/bin/python3 "$VPS_HOME/inject_cookies.py" "$port" "$cookie_file" \
            >> "$VPS_HOME/bot-${acct}.log" 2>&1 || log "inject $acct non-zero (cek log)"
    fi
done

# ── 9. Launch bot (keep_bot_alive baca accounts.txt) ──
log "Starting bots (stagger 8s per bot)..."
sudo -u ubuntu bash -c "cd $VPS_HOME && bash keep_bot_alive.sh >> keep_alive.log 2>&1"

# ── 10. Crontab ──
log "Installing crontab..."
CRON_FILE="/tmp/threads-cron"
cat > "$CRON_FILE" <<EOF
# ===== THREADS BOT — VM v2 (RAM-mitigated) =====
*/5 * * * * pgrep -f "watchdog_thread[s].py" >/dev/null || setsid /usr/bin/python3 -u $VPS_HOME/watchdog_threads.py >> $VPS_HOME/watchdog-log.txt 2>&1 < /dev/null
*/5 * * * * $VPS_HOME/keep_bot_alive.sh >> $VPS_HOME/keep_alive.log 2>&1
*/5 * * * * bash $VPS_HOME/vm/state-sync.sh >> $VPS_HOME/state-sync.log 2>&1
EOF
crontab -u ubuntu "$CRON_FILE"
rm -f "$CRON_FILE"

# ── 11. State sync pertama ──
sudo -u ubuntu bash "$VPS_HOME/vm/state-sync.sh" >> "$VPS_HOME/state-sync.log" 2>&1 || true

# ── 12. RAM VERDICT akhir ──
log "--- RAM setelah bootstrap ---"
free -h
log "Bot jalan: $(pgrep -cf 'python3 -u threads_bot_' || echo 0) proses"
log "Chrome jalan: $(pgrep -cf 'chrome.*remote-debugging-port' || echo 0) instances"
log "=== VM BOOTSTRAP v2 COMPLETE ==="
