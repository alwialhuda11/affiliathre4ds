# VM Setup — Threads Bot (MIRROR PERSIS VPS)

## Apa yang berubah vs versi sebelumnya

Repo sekarang **flat layout** — identik dengan `/home/ubuntu` di VPS:

```
/home/ubuntu (di VM, hasil clone)
├── threads_bot_oliviapicks.py        ← bot (sama persis VPS)
├── threads_bot_lanadealsrey.py
├── threads_bot_selenasupply.py
├── threads_bot_avelinefinds.py
├── threads_bot_kailaaak72.py
├── threads_bot_renaisher2.py
├── threads_bot_kailaaak7.py          ← cadangan
├── threads_bot_new_account.py        ← cadangan
├── threads_bot_renaisher.py          ← cadangan
├── watchdog_threads.py               ← jaga Chrome (port 9222-9228)
├── keep_bot_alive.sh                 ← restart bot mati
├── inject_cookies.py                 ← inject cookies via CDP
├── config/affiliate-links.json       ← link affiliate asli
├── cookies/*.json                    ← 6 akun cookies
├── state/*.json                      ← replied_posts, posted_links (sync)
└── vm/
    ├── bootstrap.sh                  ← jalan tiap VM boot
    └── state-sync.sh                 ← cron tiap 5 menit
```

## Kenapa path /home/ubuntu dipertahankan

`watchdog_threads.py` hardcode `--user-data-dir=/home/ubuntu/chrome-profile-*`
dan `keep_bot_alive.sh` hardcode `cd /home/ubuntu`. Clone ke path yang sama =
**nol perubahan code**, Chrome profiles, cron, semuanya identik.

## Setup di VM (sekali)

### 1. Buat GitHub Token

GitHub → Settings → Developer settings → Personal access tokens → Fine-grained:
- Repo: `alwialhuda11/affiliathre4ds` (Only select repositories)
- Permissions: **Contents: Read and write** (untuk state sync push)

### 2. Paste bootstrap.sh ke startup script VM

Ganti `GH_TOKEN_DI_SINI` dengan token lo, lalu paste isi `vm/bootstrap.sh` ke:

| Platform | Lokasi |
|----------|--------|
| Oracle Cloud | Instances → Create → Advanced Details → Startup Script |
| GCP | Compute Engine → Create VM → Advanced → Management → Automation |
| AWS | EC2 → Launch → Advanced Details → User Data |
| DigitalOcean | Create Droplet → Advanced Options → User Data |

Token disimpan di **cloud console** (bukan di disk VM) → selamat tiap reset.

### 3. Boot pertama

Tunggu 3-4 menit (install Chrome + clone + inject cookies + launch bot).
Cek: `/var/log/threads-bot-bootstrap.log`

## Apa yang terjadi tiap boot (otomatis)

```
VM reset (tiap 2 jam)
  ↓ cloud-init jalankan bootstrap.sh
1. apt install python3, git, Chrome, cron
2. git clone → /home/ubuntu (layout identik VPS)
3. Restore state: replied_posts.json + posted_links.json
   (dedup history — gak dobel comment ke post yang sama)
4. Start watchdog → Chrome launch port 9222-9228
5. Tunggu CDP siap → inject cookies per akun
   (VPS: cookies baked sekali; VM: profile reset → inject tiap boot)
6. keep_bot_alive.sh → launch 6 bot
7. Crontab: watchdog guard + keep_alive + state-sync (tiap 5 menit)
```

## State Management

| File | Fungsi | Arah sync |
|------|--------|-----------|
| `replied_posts.json` | Anti-duplicate comment | VM → GitHub tiap 5 menit |
| `posted_links.json` | Anti-duplicate affiliate link | VM → GitHub tiap 5 menit |
| `recent_comments.json` | Anti-copy-paste comment | VM → GitHub |
| `recent_categories.json` | Category rotation | VM → GitHub |

Tiap boot: GitHub → VM (restore). Tiap 5 menit: VM → GitHub (push).
**Max data loss: 5 menit** (kalau VM reset tepat sebelum sync).

## Update cookies / link affiliate

```bash
# Dari mana aja (VPS / local):
cp cookies_baru.json cookies/oliviapicks.json   # atau edit config/affiliate-links.json
git add cookies/ config/affiliate-links.json
git commit -m "update cookies oliviapicks"
git push

# VM otomatis pull di boot berikutnya (maks 2 jam lagi)
```

## Catatan penting

- **RAM:** 6 Chrome + 6 bot ≈ 1.5-2 GB. VM minimal 2 GB RAM.
- **Daily reset 03:00 gak dipasang** — VM udah reset tiap 2 jam, lebih sering.
- **Jangan jalankan akun yang sama di VPS + VM barengan** — session conflict.
  Kalau VPS masih hidup, matikan bot VPS dulu (`pkill -f threads_bot`).
- **IP berubah tiap reset** — normal untuk free tier, Threads gak masalah
  selama cookies valid.


## RAM Mitigation (v2 — buat VM RAM-capped)

VM lo: 7.7GB RAM tapi 7.2GB udah kepake service lain (sisa 567Mi available).
Bootstrap v2 punya 4 lapis pertahanan:

### 1. Swap 4GB otomatis
- Dibuat tiap boot (`/swapfile`) — VM reset tiap 2 jam gak masalah
- `swappiness=60` — Chrome boleh page out agresif
- Total virtual RAM: 7.7GB + 4GB swap = ~11.7GB

### 2. Chrome di-tune hemat RAM
- `--renderer-process-limit=1` (bukan 2) — hemat ~80MB/akun
- `--js-flags=--max-old-space-size=48` (bukan 96) — heap JS Chrome dipotong
- `--disk-cache-size=1MB` (bukan 10MB)
- Perkiraan: ~170MB/Chrome (bukan ~300MB)

### 3. RAM gate + accounts.txt
Bootstrap cek `free -m` saat boot:
- **available ≥ 1.2GB** → semua 6 akun jalan
- **available < 1.2GB** → cuma 3 akun (avelinefinds + oliviapicks + selenasupply)

3 akun inactive: Chrome port-nya gak di-launch sama sekali (watchdog di-patch
via regex hapus entry CHROME_CMDS), bot-nya juga gak start.
~3 Chrome × 170MB + 3 bot × 25MB = **~580MB** — muat di RAM yang tersisa.

Mau ganti akun mana yang jalan di VM? Edit `accounts.txt` di home VM,
atau ubah THREE_ACCOUNTS di bootstrap.sh.

### 4. earlyoom (best-effort)
Kalau install berhasil: throttle/kill proses paling boros RAM sebelum
kernel OOM killer berantakan semua.

### Estimasi beban total VM (3 akun mode)
| Komponen | RAM |
|----------|-----|
| 3 Chrome headless (tuned) | ~510 MB |
| 3 bot Python | ~75 MB |
| watchdog + cron | ~15 MB |
| **Total bot** | **~600 MB** |
| Sisa RAM available + swap | buffer OOM |

### Kalau masih OOM di VM
1. Cek `/var/log/threads-bot-bootstrap.log` bagian "Top RAM consumers"
2. Service apa yang makan 7.2GB itu kemungkinan besar service VM provider
   — coba `systemctl list-units --type=service --state=running`
3. Kalau perlu, kurangi lagi ke 2 akun (edit THREE_ACCOUNTS jadi 2 baris)
