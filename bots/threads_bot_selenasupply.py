#!/usr/bin/env python3
"""Bot Threads - Using v18 SUCCESS method
Method: Click Reply counter -> Type -> Click (788,301) -> Enter
Loop: Every 30 minutes with real affiliate links
"""

import json
import requests
import websocket
import time
import random
import datetime
import os
import sys

# Telegram config
TELEGRAM_BOT_TOKEN = "8766202285:AAFtzI3wpxrua9sYgO3K7YPwbxr8av7B1eo"
TELEGRAM_CHAT_ID = "1074643318"

CHROME_HOST = "localhost"
CHROME_PORT = 9225

# Config
AFFILIATE_LINKS_FILE = os.path.join(os.path.dirname(__file__), "config", "affiliate-links.json")
TARGET_KEYWORDS = ['jerawat', 'acne', 'skincare', 'wajah', 'glow', 'beauty', 'makeup', 'parfum']
SOUTHSEA_INDICATORS = [
    # Indonesian
    'yang', 'dan', 'ini', 'aku', 'kamu', 'dia', 'gua', 'lu', 'gak', 'nggak',
    'udah', 'belum', 'buat', 'dengan', 'ke', 'di', 'dari', 'nya', 'sih', 'banget',
    'bgt', 'dong', 'deh', 'tuh', 'gue', 'lo', 'kan', 'pun', 'kalau', 'kalo',
    # Malay
    'yang', 'dan', 'ini', 'aku', 'kamu', 'dia', 'tak', 'nak', 'buat', 'dengan',
    'ke', 'di', 'dari', 'nya', 'lah', 'pun', 'je', 'la', 'ada', 'tiada',
    'sini', 'situ', 'sana', 'macam', 'bila', 'mana', 'apa', 'siapa',
    'sebab', 'tapi', 'atau', 'supaya', 'sangat', 'oke', 'okay', 'best',
    'cantik', 'comel', 'tu', 'la', 'ya', 'okeh',
    # Shared/ambiguous
    'the', 'and', 'this', 'is', 'it', 'for', 'to', 'my', 'me', 'you',
    'with', 'have', 'was', 'but', 'they', 'not', 'on', 'all', 'can', 'been',
]

# VIRAL POST FILTER (engagement thresholds)
MIN_LIKES = 50            # Minimal likes biar dianggap viral
MIN_REPLIES = 20          # Minimal replies biar dianggap rame
MAX_POST_AGE_HOURS = 12   # Post maksimal umur 12 jam (masih fresh)

# Track replied posts to avoid duplicates
REPLIED_POSTS_FILE = os.path.join(os.path.dirname(__file__), "replied_posts.json")
MAX_REPLIED_TRACK = 50  # Keep last 50 replied posts

# Track posted links to avoid duplicates (Link Dedup)
POSTED_LINKS_FILE = os.path.join(os.path.dirname(__file__), "posted_links.json")
MAX_POSTED_LINKS_TRACK = 100  # Keep last 100 posted links

# Track recent categories for rotation
RECENT_CATEGORIES_FILE = os.path.join(os.path.dirname(__file__), "recent_categories.json")
MAX_RECENT_CATEGORIES = 2  # Don't repeat same category in last 2 posts

# Loop config
POST_INTERVAL_MIN = 25
POST_INTERVAL_MAX = 35
ACTIVE_HOUR_START = 0
ACTIVE_HOUR_END = 24

LOG_FILE = os.path.join(os.path.dirname(__file__), "loop-log.txt")

def log(msg):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def send_telegram(msg):
    """Send notification to Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def get_ws_url():
    resp = requests.get(f"http://{CHROME_HOST}:{CHROME_PORT}/json").json()
    return resp[0]['webSocketDebuggerUrl']

def cdp_eval(expr, timeout=30):
    ws = websocket.create_connection(get_ws_url(), timeout=timeout)
    ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 
                        'params': {'expression': expr, 'returnByValue': True, 'awaitPromise': True}}))
    msg = json.loads(ws.recv())
    ws.close()
    return msg.get('result', {}).get('result', {}).get('value')

def cdp_navigate(url, timeout=30):
    ws = websocket.create_connection(get_ws_url(), timeout=timeout)
    ws.send(json.dumps({'id': 1, 'method': 'Page.navigate', 'params': {'url': url}}))
    json.loads(ws.recv())
    ws.close()

def click_at(x, y):
    ws = websocket.create_connection(get_ws_url(), timeout=30)
    ws.send(json.dumps({"id": 1, "method": "Input.dispatchMouseEvent",
                        "params": {"type": "mouseMoved", "x": x, "y": y}}))
    json.loads(ws.recv())
    time.sleep(0.2)
    ws.send(json.dumps({"id": 2, "method": "Input.dispatchMouseEvent",
                        "params": {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1}}))
    json.loads(ws.recv())
    time.sleep(0.1)
    ws.send(json.dumps({"id": 3, "method": "Input.dispatchMouseEvent",
                        "params": {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1}}))
    json.loads(ws.recv())
    ws.close()

def insert_text(text):
    ws = websocket.create_connection(get_ws_url(), timeout=30)
    # Human typing pattern: delay per character (30ms)
    for char in text:
        ws.send(json.dumps({"id": 1, "method": "Input.insertText", "params": {"text": char}}))
        json.loads(ws.recv())
        time.sleep(0.03)  # 30ms delay per character
    ws.close()

def load_affiliate_links():
    with open(AFFILIATE_LINKS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_replied_posts():
    """Load list of already replied post URLs"""
    if os.path.exists(REPLIED_POSTS_FILE):
        with open(REPLIED_POSTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_replied_post(post_url):
    """Save a post URL to replied list, keep only last MAX_REPLIED_TRACK"""
    replied = load_replied_posts()
    if post_url not in replied:
        replied.append(post_url)
        # Keep only last N posts
        if len(replied) > MAX_REPLIED_TRACK:
            replied = replied[-MAX_REPLIED_TRACK:]
        with open(REPLIED_POSTS_FILE, "w", encoding="utf-8") as f:
            json.dump(replied, f, indent=2)

def load_posted_links():
    """Load list of already posted affiliate links"""
    if os.path.exists(POSTED_LINKS_FILE):
        with open(POSTED_LINKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def load_recent_comments():
    """Load list of recent comments for similarity check"""
    RECENT_COMMENTS_FILE = os.path.join(os.path.dirname(__file__), "recent_comments.json")
    if os.path.exists(RECENT_COMMENTS_FILE):
        with open(RECENT_COMMENTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_recent_comment(comment):
    """Save a comment to recent list, keep only last 5"""
    RECENT_COMMENTS_FILE = os.path.join(os.path.dirname(__file__), "recent_comments.json")
    recent = load_recent_comments()
    recent.append(comment)
    # Keep only last 5 comments
    if len(recent) > 5:
        recent = recent[-5:]
    with open(RECENT_COMMENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(recent, f, indent=2)

def is_similar_comment(new_comment, recent_comments):
    """Check if new comment is >60% similar to any recent comment"""
    if not recent_comments:
        return False
    
    # Simple word overlap check
    new_words = set(new_comment.lower().split())
    
    for recent in recent_comments:
        recent_words = set(recent.lower().split())
        if not recent_words:
            continue
        
        # Calculate overlap ratio
        overlap = len(new_words.intersection(recent_words))
        similarity = overlap / len(recent_words)
        
        if similarity > 0.6:  # >60% similar
            return True
    
    return False

def save_posted_link(link):
    """Save a link to posted list, keep only last MAX_POSTED_LINKS_TRACK"""
    posted = load_posted_links()
    if link not in posted:
        posted.append(link)
        # Keep only last N links
        if len(posted) > MAX_POSTED_LINKS_TRACK:
            posted = posted[-MAX_POSTED_LINKS_TRACK:]
        with open(POSTED_LINKS_FILE, "w", encoding="utf-8") as f:
            json.dump(posted, f, indent=2)

def load_recent_categories():
    """Load list of recent categories used"""
    if os.path.exists(RECENT_CATEGORIES_FILE):
        with open(RECENT_CATEGORIES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_recent_category(category):
    """Save a category to recent list, keep only last MAX_RECENT_CATEGORIES"""
    recent = load_recent_categories()
    if category not in recent:
        recent.append(category)
        # Keep only last N categories
        if len(recent) > MAX_RECENT_CATEGORIES:
            recent = recent[-MAX_RECENT_CATEGORIES:]
        with open(RECENT_CATEGORIES_FILE, "w", encoding="utf-8") as f:
            json.dump(recent, f, indent=2)

def get_random_affiliate_link():
    links_data = load_affiliate_links()
    all_links = []
    posted_links = load_posted_links()  # Load already posted links
    recent_categories = load_recent_categories()  # Load recent categories for rotation
    
    # Collect links from all categories
    available_categories = []
    for category in links_data:
        for subcategory in links_data[category]:
            available_categories.append((category, subcategory))
    
    # Filter categories not in recent 2 posts (Category Rotation)
    if len(recent_categories) >= MAX_RECENT_CATEGORIES:
        filtered_categories = [cat for cat in available_categories if cat[0] not in recent_categories]
        if filtered_categories:  # Use filtered if available
            available_categories = filtered_categories
    
    # Pick a random category/subcategory
    if not available_categories:
        return "https://s.shopee.co.id/XXXXX16"
    
    chosen_category, chosen_subcategory = random.choice(available_categories)
    links = links_data[chosen_category][chosen_subcategory]
    
    # Filter out already posted links
    available_links = [link for link in links if link not in posted_links]
    
    # If all links in this category have been posted, reset and use all links
    if not available_links:
        log(f"    ⚠️ All links in {chosen_category}/{chosen_subcategory} posted, using all links")
        available_links = links
    
    chosen_link = random.choice(available_links)
    
    # Save this category for rotation tracking
    save_recent_category(chosen_category)
    
    return chosen_link

def is_active_hour():
    now = datetime.datetime.now()
    return ACTIVE_HOUR_START <= now.hour < ACTIVE_HOUR_END

def do_one_post(attempt_num):
    log(f"📝 Post attempt #{attempt_num} starting...")
    
    try:
        # Step 1: Open Threads home feed
        log("[1/7] Opening Threads home feed...")
        cdp_navigate("https://www.threads.net")
        time.sleep(8)
        
        # Step 2: Find and click relevant post (skip already replied)
        log("[2/7] Finding relevant post on feed...")
        replied_posts = load_replied_posts()
        current_post_url = None
        
        # Try to find post up to 3 times (with scroll)
        for attempt in range(3):
            if attempt > 0:
                log(f"    📜 Scrolling down to load more posts (attempt {attempt+1})...")
                cdp_eval("window.scrollBy(0, 800)", 5)
                time.sleep(3)
            
            post_found = cdp_eval(f"""
                (() => {{
                    const repliedUrls = {json.dumps(replied_posts)};
                    const links = Array.from(document.querySelectorAll('a[href*="/post/"]'));
                    for (const link of links) {{
                        const postUrl = link.href;
                        // Skip already replied posts
                        if (repliedUrls.includes(postUrl)) {{
                            continue;
                        }}
                        
                        // Walk up DOM to find post text
                        let container = link.closest('article');
                        if (!container) {{
                            let node = link;
                            for (let i = 0; i < 10; i++) {{
                                node = node.parentElement;
                                if (!node) break;
                                if ((node.innerText || '').length > 60) {{
                                    container = node;
                                    break;
                                }}
                            }}
                        }}
                        const text = container ? container.innerText.toLowerCase() : '';
                        const isRelevant = {json.dumps(TARGET_KEYWORDS)}.some(kw => text.includes(kw));
                        const isIndonesian = {json.dumps(SOUTHSEA_INDICATORS)}.filter(kw => text.includes(kw)).length >= 1;
                            // BLOCK CJK/Hanzi/Kana/Korean — skip non-Southeast Asia posts
                            const isNotCJK = !/[一-鿿぀-ヿ가-힯ࠀ-䷿]/.test(text);
                        
                        if (isRelevant && isIndonesian && isNotCJK) {{
                            // EXTRACT ENGAGEMENT: Find likes & replies
                            let likes = 0;
                            let replies = 0;
                            
                            // Find likes (format: "123 likes" or "123 ❤️")
                            const likesMatch = text.match(/(\\d+)\\s*(?:likes?|❤️)/i);
                            if (likesMatch) {{
                                likes = parseInt(likesMatch[1]);
                            }}
                            
                            // Find replies (format: "45 replies" or "45 reply")
                            const repliesMatch = text.match(/(\\d+)\\s*(?:replies?|reply)/i);
                            if (repliesMatch) {{
                                replies = parseInt(repliesMatch[1]);
                            }}
                            
                            // FILTER: Skip post sepi (likes < 50 && replies < 20)
                            if (likes < 50 && replies < 20) {{
                                continue;  // Skip post sepi, lanjut cari post lain
                            }}
                            
                            link.scrollIntoView({{ block: 'center' }});
                            return {{
                                url: link.href,
                                text: text.substring(0, 100),
                                likes: likes,
                                replies: replies
                            }};
                        }}
                    }}
                    return null;
                }})()
            """, 30)
            
            if post_found:
                break
        
        if not post_found:
            log("    ⚠️ No relevant post found after scrolling, cari post non-replied berbahasa ID/MY...")
            # Try to find ANY non-replied post that passes ID/MY filter + CJK check
            southsea_fallback = cdp_eval(f"""
                (() => {{
                    const repliedUrls = {json.dumps(replied_posts)};
                    const southseaIndicators = {json.dumps(SOUTHSEA_INDICATORS)};
                    const links = Array.from(document.querySelectorAll('a[href*="/post/"]'));
                    for (const link of links) {{
                        if (repliedUrls.includes(link.href)) continue;
                        // Walk up DOM to find post text
                        let container = link.closest('article');
                        if (!container) {{
                            let node = link;
                            for (let i = 0; i < 10; i++) {{
                                node = node.parentElement;
                                if (!node) break;
                                if ((node.innerText || '').length > 60) {{
                                    container = node;
                                    break;
                                }}
                            }}
                        }}
                        const text = container ? container.innerText.toLowerCase() : '';
                        // CJK blocking
                        if (/[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af\u0800-\u4dff]/.test(text)) continue;
                        // At least 1 southsea indicator word
                        if (southseaIndicators.filter(kw => text.includes(kw)).length < 1) continue;
                        link.scrollIntoView({{ block: 'center' }});
                        return link.href;
                    }}
                    return null;
                }})()
            """, 15)

            if southsea_fallback:
                log(f"    ✅ Ketemu post ID/MY via fallback: {southsea_fallback[:50]}...")
                current_post_url = southsea_fallback
                cdp_eval(f"""
                    (() => {{
                        const links = Array.from(document.querySelectorAll('a[href*="/post/"]'));
                        const target = links.find(l => l.href === '{southsea_fallback}');
                        if (target) {{ target.click(); }}
                        return true;
                    }})()
                """, 15)
                time.sleep(5)
            else:
                log("    ⚠️ Feed kosong ID/MY — coba cari via Threads Search...")
                # Threads Search fallback — search with relevant keywords
                from urllib.parse import quote as _quote
                _kws = ['skincare Indonesia', 'beauty Jakarta', 'jerawat solusi', 'skin care Malay', 'parfum Indonesia']
                random.shuffle(_kws)
                search_post = None
                for _skw in _kws[:3]:
                    log(f"    \U0001f50d Search Threads: '{_skw}'...")
                    cdp_navigate(f"https://www.threads.com/search?q={_quote(_skw)}&serp_type=recent")
                    time.sleep(8)
                    cdp_eval("window.scrollBy(0, 600)", 5)
                    time.sleep(3)
                    search_post = cdp_eval(f"""
                    (() => {{
                        const repliedUrls = {json.dumps(replied_posts)};
                        const southseaIndicators = {json.dumps(SOUTHSEA_INDICATORS)};
                        const links = Array.from(document.querySelectorAll('a[href*="/post/"]'));
                        for (const link of links) {{
                            if (repliedUrls.includes(link.href)) continue;
                            // Walk up DOM to find post text
                            let container = link.closest('article');
                            if (!container) {{
                                let node = link;
                                for (let i = 0; i < 10; i++) {{
                                    node = node.parentElement;
                                    if (!node) break;
                                    if ((node.innerText || '').length > 60) {{
                                        container = node;
                                        break;
                                    }}
                                }}
                            }}
                            const text = container ? container.innerText.toLowerCase() : '';
                            if (/[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af\u0800-\u4dff]/.test(text)) continue;
                            if (southseaIndicators.filter(kw => text.includes(kw)).length < 1) continue;
                            link.scrollIntoView({{ block: 'center' }});
                            return link.href;
                        }}
                        return null;
                    }})()
                    """, 15)
                    if search_post:
                        break
                if search_post:
                    log(f"    \u2705 Ketemu post ID/MY via search: {search_post[:50]}...")
                    current_post_url = search_post
                    cdp_eval(f"""
                        (() => {{
                            const links = Array.from(document.querySelectorAll('a[href*="/post/"]'));
                            const target = links.find(l => l.href === '{search_post}');
                            if (target) {{ target.click(); }}
                            return true;
                        }})()
                    """, 15)
                    time.sleep(5)
                else:
                    log("    \u274c Tidak ada post ID/MY ditemukan \u2014 skip siklus ini.")
                    return True  # Skip this cycle gracefully
        log("    Post opened!")
        
        # Step 3: Click Reply COUNTER (v18 method)
        log("[3/7] Clicking Reply counter...")
        reply_counter_info = cdp_eval("""
            (() => {
                const candidates = Array.from(document.querySelectorAll('[role="button"]'))
                    .filter(btn => {
                        const text = (btn.textContent || '').trim();
                        return (text.startsWith('Reply') || text.startsWith('Comment')) && text.length > 4;
                    })
                    .map(btn => ({btn, rect: btn.getBoundingClientRect()}))
                    .filter(item => item.rect.width > 0 && item.rect.height > 0);
                const visible = candidates.find(item => item.rect.y >= 0 && item.rect.y < window.innerHeight);
                const chosen = visible || candidates.filter(item => item.rect.y >= 0)
                    .sort((a, b) => a.rect.y - b.rect.y)[0];
                if (!chosen) return null;
                if (!visible) chosen.btn.scrollIntoView({block: 'center'});
                const rect = chosen.btn.getBoundingClientRect();
                return JSON.stringify({x: rect.x + rect.width/2, y: rect.y + rect.height/2});
            })()
        """, 15)
        
        if not reply_counter_info:
            log("    ❌ Reply counter NOT found!")
            return False
        
        reply_counter = json.loads(reply_counter_info)
        click_at(int(reply_counter['x']), int(reply_counter['y']))
        log(f"    Clicked Reply counter at ({reply_counter['x']}, {reply_counter['y']})!")
        time.sleep(4)
        
        # Step 4: Click comment field
        log("[4/7] Clicking comment field...")
        editor_info = cdp_eval("""
            (() => new Promise(resolve => {
                const started = Date.now();
                const check = () => {
                    const ce = document.querySelector('[contenteditable="true"]');
                    if (ce) {
                        const rect = ce.getBoundingClientRect();
                        resolve(JSON.stringify({x: rect.x + rect.width/2, y: rect.y + rect.height/2}));
                    } else if (Date.now() - started >= 12000) {
                        resolve(null);
                    } else {
                        setTimeout(check, 250);
                    }
                };
                check();
            }))()
        """, 15)
        
        if not editor_info:
            log("    ❌ Comment field NOT found!")
            return False
        
        editor = json.loads(editor_info)
        click_at(int(editor['x']), int(editor['y']))
        log(f"    Comment field clicked at ({editor['x']}, {editor['y']})!")
        time.sleep(2)
        
        # Ensure editor focus
        log("[4b] Ensuring editor focus...")
        cdp_eval("""
            (() => {
                const ce = document.querySelector('[contenteditable="true"]');
                if (ce) {
                    ce.focus();
                    ce.dispatchEvent(new FocusEvent('focus', { bubbles: true }));
                }
                return true;
            })()
        """, 10)
        time.sleep(1)
        
        # Step 5: Type comment with real affiliate link
        log("[5/7] Typing comment...")
        affiliate_link = get_random_affiliate_link()
        
        # Natural trust-based comment templates (Mix & Match Hook+Body+Closing)
        hooks = [
            "awalnya aku ga expect banyak sih",
            "aku coba ini karena penasaran aja",
            "jujur awalnya ragu",
            "ini aku pake beberapa hari dulu baru berani komen",
            "ga langsung wow tapi pelan pelan keliatan",
            "aku ga bilang ini perfect ya",
            "ini bukan yg langsung instan gitu",
            "aku udah coba dan lumayan oke",
            "ini hasilnya ga lebay tapi ada perubahan",
            "aku pake ini pas kulit lagi rewel",
            "ini aku cocok sih, tapi mungkin beda di orang lain",
            "aku coba tanpa ekspektasi tinggi",
            "awalnya biasa aja tapi lama lama suka",
            "ini bukan yg hype doang ternyata",
            "aku baru pake beberapa kali sih",
            "ini aku coba karena liat review juga",
            "jujur ini lebih enak dari yg aku kira",
            "aku ga langsung notice di hari pertama",
            "ini aku pake rutin baru kerasa",
            "aku termasuk picky soal skincare",
            "ini ga bikin kaget tapi nyaman dipake",
            "aku liat perubahan kecil tapi konsisten",
            "ini aku test dulu sebelum ngomong",
            "aku ga expect bakal kepake terus",
            "ini aku pake pelan pelan dulu"
        ]
        
        bodies = [
            "di kulitku dia cukup calming dan ga bikin perih",
            "teksturnya ringan jadi gampang dipake tiap hari",
            "ga bikin breakout di aku sejauh ini",
            "bikin kulit terasa lebih lembap dikit",
            "ga ada efek aneh sejauh aku pake",
            "keliatan lebih halus pelan pelan",
            "bantu banget pas lagi kering",
            "ga berat walaupun dipake layering",
            "nyerepnya juga cepet di kulitku",
            "ga bikin muka keliatan berminyak berlebihan",
            "ada efek glow tipis tapi natural",
            "nyaman dipake pagi atau malam",
            "ga bikin kulit makin sensitif",
            "cukup bantu buat nenangin kemerahan",
            "hasilnya pelan tapi keliatan",
            "ga bikin kulit ketarik",
            "cocok buat dipake rutin",
            "ga ganggu skincare lain yg aku pake",
            "bikin tampilan kulit lebih rapi dikit",
            "overall masih aman di aku"
        ]
        
        closings = [
            "mungkin bisa dicoba kalau lagi cari yg gentle",
            "siapa tau cocok juga di kamu",
            "aku lanjut pake dulu sih",
            "boleh diliat dulu detailnya",
            "aku simpen ini dulu buat repurchase",
            "worth dicoba kalau kulit lagi butuh yg ringan",
            "ga maksa ya, tapi ini oke di aku",
            "bisa jadi alternatif juga",
            "coba cek dulu sebelum mutusin",
            "aku sih masih lanjut pake ini",
            "pelan pelan aja nyobanya",
            "mungkin hasilnya beda beda ya",
            "ini cocok buat yg ga mau ribet",
            "aku sih cukup puas sejauh ini",
            "bisa masuk list buat dicoba",
            "aku keep ini di routine dulu",
            "siapa tau ini yg kamu cari",
            "aku bakal pake lagi sih",
            "ga expect banyak tapi ternyata oke",
            "ini aman aman aja di aku"
        ]
        
        # Hook Similarity Check (anti-copy paste)
        posted_links = load_posted_links()  # Reuse this file to also track recent comments
        recent_comments = load_recent_comments()  # Load recent comments for similarity check
        
        # Try to generate a unique comment (max 5 attempts)
        for attempt in range(5):
            hook = random.choice(hooks)
            body = random.choice(bodies)
            closing = random.choice(closings)
            comment = f"{hook}, {body}, {closing}\n\n{affiliate_link}"
            
            # Check similarity with recent comments
            if not is_similar_comment(comment, recent_comments):
                break
            log(f"    ⚠️ Comment too similar (attempt {attempt+1}/5), regenerating...")
        else:
            log("    ⚠️ Could not generate unique comment, using last attempt")
        
        # Random combo: Hook + Body + Closing
        hook = random.choice(hooks)
        body = random.choice(bodies)
        closing = random.choice(closings)
        
        comment = f"{hook}, {body}, {closing}\n\n{affiliate_link}"
        
        insert_text(comment)
        log(f"    Text inserted with link: {affiliate_link}")
        time.sleep(2)
        
        # Verify text entered
        editor_text = cdp_eval("""
            (() => {
                const ce = document.querySelector('[contenteditable="true"]');
                return ce ? ce.innerText : 'NOT FOUND';
            })()
        """, 10)
        log(f"    [DEBUG] Editor text: '{editor_text[:50]}'")
        
        if not editor_text or editor_text.strip() == '' or editor_text == 'NOT FOUND':
            log("    ⚠️ Text NOT detected! Trying alternative...")
            cdp_eval(f"""
                (() => {{
                    const ce = document.querySelector('[contenteditable="true"]');
                    if (ce) {{
                        ce.focus();
                        document.execCommand('insertText', false, {json.dumps(comment)});
                    }}
                    return true;
                }})()
            """, 15)
            time.sleep(1)
        
        time.sleep(3)
        
        # Step 6: Click Reply button at (788, 301) + Enter (v18 method)
        log("[6/7] Clicking Reply button at (788, 301) + Enter...")
        click_at(788, 301)
        log("    Clicked at (788, 301)!")
        time.sleep(2)
        
        # Press Enter
        log("    Pressing Enter key...")
        ws = websocket.create_connection(get_ws_url(), timeout=30)
        ws.send(json.dumps({"id": 1, "method": "Input.dispatchKeyEvent",
                            "params": {"type": "keyDown", "key": "Enter", "code": "Enter", "keyCode": 13, "windowsVirtualKeyCode": 13}}))
        json.loads(ws.recv())
        ws.send(json.dumps({"id": 2, "method": "Input.dispatchKeyEvent",
                            "params": {"type": "keyUp", "key": "Enter", "code": "Enter", "keyCode": 13, "windowsVirtualKeyCode": 13}}))
        json.loads(ws.recv())
        ws.close()
        log("    Enter key pressed!")
        
        log("\n⏳ Waiting 15s for post to submit...")
        time.sleep(15)
        
        # Step 7: Refresh feed for next post
        log("[7/7] Refreshing feed...")
        cdp_navigate("https://www.threads.net")
        time.sleep(5)
        
        # Save replied post to avoid duplicates
        if current_post_url:
            save_replied_post(current_post_url)
            log(f"    💾 Saved replied post: {current_post_url[:50]}...")
        
        log(f"✅ Post #{attempt_num} COMPLETED!")
        # Send Telegram notification
        send_telegram(f"✅ Threads Bot - selenasupply\nPost #{attempt_num} berhasil!\nLink: {affiliate_link}\n\nDone, Posted!")
        # Save posted link to avoid duplicates (Link Dedup)
        save_posted_link(affiliate_link)
        log(f"    💾 Saved posted link: {affiliate_link}")
        # Save comment for similarity check (anti-copy paste)
        save_recent_comment(comment)
        log(f"    💾 Saved comment for similarity check")
        return True
        
    except Exception as e:
        log(f"❌ Post #{attempt_num} FAILED: {str(e)}")
        return False

def main():
    log("=" * 60)
    log("🤖 THREADS BOT - v18 METHOD (SUCCESS)")
    log(f"   Interval: {POST_INTERVAL_MIN}-{POST_INTERVAL_MAX} min")
    log(f"   Active: {ACTIVE_HOUR_START:02d}:00-{ACTIVE_HOUR_END:02d}:00")
    log("   Method: Reply counter -> (788,301) -> Enter")
    log("=" * 60)
    
    attempt = 0
    consecutive_failures = 0
    
    try:
        while True:
            attempt += 1
            
            if not is_active_hour():
                now = datetime.datetime.now()
                next_start = now.replace(hour=ACTIVE_HOUR_START, minute=0, second=0)
                if now.hour >= ACTIVE_HOUR_END:
                    next_start += datetime.timedelta(days=1)
                wait_sec = (next_start - now).total_seconds()
                log(f"⏸️ Waiting {int(wait_sec/3600)}h until {ACTIVE_HOUR_START:02d}:00...")
                time.sleep(wait_sec)
                continue
            
            success = do_one_post(attempt)
            
            if success:
                interval = random.randint(POST_INTERVAL_MIN, POST_INTERVAL_MAX)
                consecutive_failures = 0  # Reset on success
                # Success notification already sent inside do_one_post()
            else:
                interval = random.randint(5, 10)
                consecutive_failures += 1
                log(f"⚠️ Retry in {interval} min... (Consecutive failures: {consecutive_failures})")
                
                # Send Telegram alert when reaching 3+ consecutive failures
                if consecutive_failures >= 3:
                    send_telegram(f"⚠️ Threads Bot - selenasupply\nERROR: {consecutive_failures}x gagal berturut-turut!\n\nKirim cookies baru sekarang.\n\nDone, Posted!")
                    log(f"📱 Telegram alert sent ({consecutive_failures} consecutive failures)")
            
            interval_sec = interval * 60
            log(f"\n⏳ Next post in {interval} min...")
            log("-" * 60)
            
            for remaining in range(interval_sec, 0, -60):
                if remaining % 300 == 0 or remaining <= 60:
                    log(f"   ... {remaining//60} min remaining")
                time.sleep(min(60, remaining))
    
    except KeyboardInterrupt:
        log("\n🛑 Bot stopped")
        log("=" * 60)

if __name__ == "__main__":
    main()