# Threads Affiliate Bot

Bot otomatis untuk posting affiliate link di Threads.

## ⚠️ Prerequisites

- Python 3.8+
- Google Chrome
- Chrome debugging enabled

## 🚀 Quick Start

```bash
# 1. Clone repo
git clone https://github.com/username/threads-bot.git
cd threads-bot

# 2. Install dependencies
pip install -r requirements.txt

# 3. Setup config
cp config/affiliate-links.json.example config/affiliate-links.json
nano config/affiliate-links.json  # Isi affiliate links lo

# 4. Buat cookies file
cp cookies/.gitkeep cookies/my_account.json
# Edit cookies/my_account.json - paste cookies dari browser dalam format JSON

# 5. Jalankan Chrome
google-chrome --remote-debugging-port=9222 \
  --user-data-dir=~/chrome-profile \
  --headless=new --no-sandbox &

# 6. Inject cookies
python inject_cookies.py 9222 cookies/my_account.json

# 7. Run bot
python threads_bot.py --cookies cookies/my_account.json --port 9222
```

## 📖 Usage

### Basic
```bash
python threads_bot.py --cookies cookies/my_account.json --port 9222
```

### Custom interval (more safe)
```bash
python threads_bot.py \
  --cookies cookies/my_account.json \
  --port 9222 \
  --interval-min 45 \
  --interval-max 90
```

### With Telegram notification
```bash
python threads_bot.py \
  --cookies cookies/my_account.json \
  --port 9222 \
  --telegram-token "YOUR_BOT_TOKEN" \
  --telegram-chat-id "YOUR_CHAT_ID"
```

### Watchdog (auto-restart Chrome)
```bash
python watchdog.py --ports 9222,9223,9225
```

## 📁 Struktur

```
threads-bot/
├── threads_bot.py      # Bot utama
├── inject_cookies.py  # Inject cookies ke Chrome
├── watchdog.py         # Monitor Chrome
├── requirements.txt
├── config/
│   └── affiliate-links.json.example  # Template
└── cookies/
    └── .gitkeep       # Simpan cookies di sini
```

## 🔐 Getting Cookies

1. Buka threads.net di Chrome (login dulu)
2. Install ekstensi "EditThisCookie" atau "Cookie-Editor"
3. Klik ekstensi → Export → JSON
4. Paste ke cookies/akun.json

## ⚙️ Args

| Arg | Default | Description |
|-----|---------|-------------|
| `--cookies` | Required | Path ke cookies file |
| `--port` | 9222 | Chrome debugging port |
| `--interval-min` | 45 | Interval min (menit) |
| `--interval-max` | 90 | Interval max (menit) |
| `--account-name` | (filename) | Nama akun untuk logging |
| `--telegram-token` | - | Bot token untuk notif |
| `--telegram-chat-id` | - | Chat ID untuk notif |

## ⚠️ Warning

- Gunakan interval yang aman (45-90 menit) untuk menghindari suspend
- Jangan terlalu banyak akun dari IP yang sama
- Randomize interval untuk behavior yang lebih natural

## 📝 Lisensi

Private - All rights reserved
