#!/bin/bash
# ============================================================
# STATE SYNC — VM → GitHub
# Dipanggil cron tiap 5 menit di VM.
# Copy state files dari /home/ubuntu (runtime) ke repo state/,
# commit, push. VM reset tiap 2 jam = state selamat di GitHub.
# ============================================================
VPS_HOME="/home/ubuntu"
cd "$VPS_HOME" || exit 0

mkdir -p state
for f in replied_posts.json posted_links.json recent_comments.json recent_categories.json; do
    [ -f "$f" ] && cp "$f" "state/$f"
done

git add state/ 2>/dev/null
git commit -m "sync $(date +%H:%M)" --allow-empty-message --quiet 2>/dev/null
# Rebase dulu biar gak konflik; kalau gagal, skip (VM tetap jalan dgn state lokal)
git pull --rebase --autostash origin master --quiet 2>/dev/null || { git rebase --abort 2>/dev/null; }
git push -f origin master --quiet 2>/dev/null
