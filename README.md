# ✦ InkForge — Web Novel Platform

A full-stack web novel platform (like RoyalRoad / ScribbleHub) built with Python + Flask + SQLite.

---

## 🚀 HOW TO START (3 steps)

### Step 1 — Make sure Python is installed
Open a terminal and type:
```
python --version
```
You should see Python 3.8 or higher. If not, download it from https://python.org

### Step 2 — Run the launcher
Double-click `START.py`, OR in your terminal:
```
python START.py
```
This auto-installs Flask and opens your browser.

### Step 3 — Open the site
The browser will open automatically at:
```
http://localhost:5000
```

---

## 🔑 DEMO LOGIN
- **Username:** scribe
- **Password:** forge123

---

## ✨ FEATURES

**For Readers:**
- Browse & search all novels
- Filter by genre (Fantasy, Isekai, Romance, Sci-Fi, etc.)
- Sort by Popular, Top Rated, Latest, Most Chapters
- Read chapters in a clean dark reader
- Rate novels (1–5 stars)
- Add novels to personal library
- Follow authors

**For Authors:**
- Full author dashboard with stats (views, followers, chapters)
- Create multiple novels with title, synopsis, genre tags, cover image, status
- Chapter editor with formatting toolbar (Bold, Italic, Underline, Headings, Quotes, HR)
- Auto-save every 3 seconds while writing
- Publish or save as draft
- Daily writing goal tracker (2,000 words)
- Author profile page

**Accounts:**
- Register with username, email, password (with validation)
- Secure password hashing (PBKDF2-SHA256)
- Change password in settings
- Edit bio, display name, website

---

## 📁 FILES
```
inkforge/
├── app.py              ← Main Flask backend + all routes
├── START.py            ← One-click launcher
├── requirements.txt
├── inkforge.db         ← SQLite database (auto-created on first run)
├── static/
│   └── uploads/        ← Novel cover images
└── templates/
    ├── base.html       ← Shared layout + nav
    ├── index.html      ← Homepage
    ├── auth.html       ← Login / Register
    ├── browse.html     ← Browse & search
    ├── novel.html      ← Novel detail page
    ├── reader.html     ← Chapter reader
    ├── editor.html     ← Chapter writer
    ├── dashboard.html  ← Author dashboard
    ├── profile.html    ← Author profile
    ├── new_novel.html  ← Create novel form
    ├── edit_novel.html ← Edit novel form
    └── settings.html   ← Account settings
```

---

## 🛑 TO STOP THE SERVER
Press `Ctrl + C` in the terminal.

---

## 🔧 CUSTOMIZATION
- Edit `app.py` to add features (comments, bookmarks, notifications, etc.)
- Templates use Jinja2 — edit `.html` files to change the UI
- Database is SQLite — no setup needed, resets by deleting `inkforge.db`
