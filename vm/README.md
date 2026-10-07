# VM Setup — Threads Bot

## Arsitektur

```
VM boot (otomatis tiap 2 jam ke-reset)
  │
  ├─ 1. git pull code + state dari GitHub (affiliathre4ds)
  ├─ 2. Install Chrome + Python deps (sekali)
  ├─ 3. Restore replied_posts.json + posted_links.json dari state/
  ├─ 4. Launch watchdog (jaga Chrome)
  ├─ 5. Launch 6 bot threads
  └─ 6. State sync loop (push state ke GitHub tiap 5 menit)
```

## Setup di VM

### Step 1: Set GitHub Token (sekali)

```bash
# Di VM, buat file credentials
mkdir -p ~/.config/gh
cat > ~/.git-credentials << 'EOF'
https://<TOKEN>@github.com
EOF
chmod 600 ~/.git-credentials
git config --global credential.helper store
```

Token butuh scope: `repo` (private repo access)

### Step 2: Set Startup Script (per platform)

**Oracle Cloud:**
1. Cloud Console → Instances → Create → Advanced Details
2. Paste isi `vm/bootstrap.sh` ke field "Startup Script"
3. Create instance

**GCP:**
1. Compute Engine → VM instances → Create
2. Advanced options → Management → Automation
3. Paste isi `vm/bootstrap.sh`
4. Create

**AWS:**
1. EC2 → Launch Instance
2. Advanced Details → User Data
3. Paste isi `vm/bootstrap.sh`
4. Launch

**Manual (kalau gak ada startup script):**
```bash
# SSH ke VM, jalankan:
bash -c 'curl -sL https://raw.githubusercontent.com/alwialhuda11/affiliathre4ds/main/vm/bootstrap.sh | bash'
```

### Step 3: Verify

```bash
# Tunggu 2-3 menit setelah boot, lalu:
tail -f /var/log/threads-bot-bootstrap.log
# Harus lihat: "=== BOOTSTRAP COMPLETE ==="
# Dan: "Started oliviapicks (PID ...)" dst

# Cek bot jalan:
ps aux | grep threads_bot

# Cek Chrome jalan:
ps aux | grep chrome
```

## State Management

| File | Fungsi | Sync |
|------|--------|------|
| `replied_posts.json` | Anti-duplicate comment | Push tiap 5 menit |
| `posted_links.json` | Anti-duplicate affiliate link | Push tiap 5 menit |
| `recent_comments.json` | Anti-copy-paste comment | Push tiap 5 menit |
| `recent_categories.json` | Category rotation | Push tiap 5 menit |

State di-commit ke GitHub tiap 5 menit oleh sync loop. Tiap VM boot, state terbaru di-pull dari GitHub.

**Max data loss:** 5 menit (kalau VM reset tepat sebelum sync)

## Cookies

Cookies tersimpan di `cookies/<account>.json` (private repo).

Untuk update cookies:
```bash
# Di VPS / local:
cp cookies_baru.json cookies/oliviapicks.json
git add cookies/
git commit -m "update cookies oliviapicks"
git push
```

VM otomatis pull cookies terbaru tiap boot.

## Troubleshooting

**Bot gak jalan setelah boot:**
```bash
cat /var/log/threads-bot-bootstrap.log
# Cari error, biasanya: Chrome belum install / cookies expired
```

**Cookies expired:**
```bash
# Cek log bot:
tail -f bot-oliviapicks.log
# Kalau "Reply counter NOT found" → cookies perlu update
# Update cookies di GitHub, VM pull di boot berikutnya
```

**Chrome crash:**
```bash
# Watchdog otomatis restart, tapi kalau mati total:
bash keep_bot_alive.sh
```
