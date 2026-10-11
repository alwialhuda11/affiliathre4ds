#!/bin/bash
# keep_bot_alive.sh — jaga 5 bot Threads tetap jalan (bukan Chrome).
# Chrome dijaga oleh watchdog_threads.py. Script ini jaga proses python bot-nya.
# Dipanggil cron tiap 5 menit.

cd /home/ubuntu || exit 1

PY=/usr/bin/python3

# account : script
BOTS="
threads_bot_oliviapicks.py
threads_bot_lanadealsrey.py

threads_bot_renaisher2.py
threads_bot_kailaaak72.py
threads_bot_avelinefinds.py
"

for script in $BOTS; do
    if pgrep -f "python3 -u $script" > /dev/null 2>&1; then
        continue
    fi
    name="${script#threads_bot_}"
    name="${name%.py}"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $script mati -> restart"
    setsid $PY -u "$script" >> "bot-${name}.log" 2>&1 < /dev/null &
    sleep 2
done
