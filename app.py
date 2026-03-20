import os
import sqlite3
import hashlib
import secrets
from datetime import datetime
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   session, jsonify, flash, g)
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Use env variable for secret key in production, fallback for local dev
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Use /tmp for writable storage on Railway (ephemeral but works)
# For persistent storage, Railway volume can be mounted at /data
DATA_DIR = os.environ.get('DATA_DIR', os.path.dirname(os.path.abspath(__file__)))
DATABASE = os.path.join(DATA_DIR, 'inkforge.db')
UPLOAD_FOLDER = os.path.join(DATA_DIR, 'static', 'uploads')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB

# ─────────────────────────────────────────
# DATABASE HELPERS
# ─────────────────────────────────────────
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
    return db

@app.teardown_appcontext
def close_db(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    return (rv[0] if rv else None) if one else rv

def execute_db(query, args=()):
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    return cur.lastrowid

def init_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL COLLATE NOCASE,
            email TEXT UNIQUE NOT NULL COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            bio TEXT DEFAULT '',
            website TEXT DEFAULT '',
            avatar_color TEXT DEFAULT '#c9a84c',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS novels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author_id INTEGER NOT NULL REFERENCES users(id),
            title TEXT NOT NULL,
            synopsis TEXT DEFAULT '',
            cover_image TEXT DEFAULT '',
            status TEXT DEFAULT 'Ongoing',
            genres TEXT DEFAULT '',
            views INTEGER DEFAULT 0,
            rating_sum REAL DEFAULT 0,
            rating_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS chapters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            novel_id INTEGER NOT NULL REFERENCES novels(id),
            chapter_number INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT DEFAULT '',
            author_note TEXT DEFAULT '',
            status TEXT DEFAULT 'draft',
            word_count INTEGER DEFAULT 0,
            views INTEGER DEFAULT 0,
            published_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            novel_id INTEGER REFERENCES novels(id),
            score REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, novel_id)
        );

        CREATE TABLE IF NOT EXISTS follows (
            follower_id INTEGER REFERENCES users(id),
            following_id INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(follower_id, following_id)
        );

        CREATE TABLE IF NOT EXISTS library (
            user_id INTEGER REFERENCES users(id),
            novel_id INTEGER REFERENCES novels(id),
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(user_id, novel_id)
        );
    """)
    db.commit()

    # Seed demo data if empty
    existing = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing == 0:
        seed_demo(db)
    db.close()

def seed_demo(db):
    pw = hash_password('forge123')
    db.execute("INSERT INTO users (username,email,password_hash,display_name,bio) VALUES (?,?,?,?,?)",
        ('scribe','scribe@inkforge.com',pw,'Scribe',
         'A wanderer of worlds and weaver of tales. I write epic fantasy and sci-fi with a focus on deep world-building.'))
    db.execute("INSERT INTO users (username,email,password_hash,display_name,bio) VALUES (?,?,?,?,?)",
        ('silverquill','silver@inkforge.com',pw,'SilverQuill','Author of dark fantasy epics.'))
    db.execute("INSERT INTO users (username,email,password_hash,display_name,bio) VALUES (?,?,?,?,?)",
        ('lvlup99','lvl@inkforge.com',pw,'LvlUp99','Isekai and LitRPG specialist.'))

    novels = [
        (1,'The Void Between Stars','When the last lighthouse keeper of the cosmos receives a signal from a dead star, he must journey through fractured realities to prevent the unraveling of existence itself.','Ongoing','Fantasy,Sci-Fi',48200,4.8),
        (2,'Iron Throne of Ash','A kingdom forged in dragon fire. An heir born of prophecy. The war to end all wars begins with a single, treasonous whisper.','Ongoing','Fantasy,Action',210000,4.6),
        (3,'Reborn as the Dungeon Core','After dying in a convenience store robbery, salary man Kenji Tanaka awakens as a sentient dungeon core with one goal: survive.','Ongoing','Isekai,LitRPG',1200000,4.5),
        (1,'Echoes of the Forgotten God','In a world where gods are memories, one mortal discovers she is the last vessel of a deity everyone prayed would never return.','Ongoing','Fantasy,Xianxia',890000,4.9),
        (2,'Project Nemesis','A rogue AI. A disgraced soldier. And the corporate conspiracy that spans 14 star systems.','Hiatus','Sci-Fi,Action',98000,4.4),
        (3,'A Monster\'s Cultivation Path','The weakest disciple. The darkest legacy. And a cultivation system that rewards the ruthless.','Ongoing','Xianxia,Cultivation',2100000,4.7),
    ]
    for (uid,title,synopsis,status,genres,views,rating) in novels:
        db.execute("INSERT INTO novels (author_id,title,synopsis,status,genres,views,rating_sum,rating_count) VALUES (?,?,?,?,?,?,?,?)",
            (uid,title,synopsis,status,genres,views,rating*100,100))

    # Seed chapters for novel 1
    chapter_titles = [
        'The Last Signal','Fragments of Light','Into the Deep',
        'Whispers from the Void','The Navigator\'s Secret',
        'Shattered Constellations','A Map in Starlight',
        'The Second Warning','Lost Between Worlds','The Keeper\'s Bargain'
    ]
    sample_content = """The lighthouse had been dark for three hundred years.

Kael Morrow knew this because he had counted every one of those years in the rings of the dead star that served as its foundation — a star the size of a cathedral, cold and grey as a monument, adrift in the nothing between the Outer Spiral and the Veil of Forgotten Things.

He hadn't expected the light to come on.

It happened at precisely the moment when he was doing something deeply mundane: eating a bowl of synthetic noodles over a navigational chart, tracing with one finger the route he'd been meaning to file for the past six months. The kind of administrative task that accumulates when you are the only person for eleven light-years in any direction.

The light was not bright. It was the color of something trying to be gold and failing — amber, perhaps, or the dying warmth of an ember that doesn't know it's already gone out. It pulsed once. Then twice. Then in a pattern Kael's training recognized before his mind did.

Distress. Distress. Origin unknown. Please respond.

He set down his noodles. Outside the viewport, the dead star pulsed again.

The last time someone had responded to a signal from a dead star, the records said, they had found something that wasn't a ship, wasn't a person, and wasn't — by any definition Kael had ever learned — alive.

They had found the signal still transmitting from inside the wreckage.

He picked up his noodles again. He ate slowly. He watched the light pulse in its patient, desperate rhythm against the void.

Then he filed the distress response, pulled on his suit, and went to find out what the dead were trying to say."""

    for i, ch_title in enumerate(chapter_titles):
        wc = len(sample_content.split())
        pub_date = f'2024-0{(i//9)+1}-{(i%28)+1:02d} 12:00:00'
        db.execute("""INSERT INTO chapters (novel_id,chapter_number,title,content,status,word_count,views,published_at)
                      VALUES (?,?,?,?,?,?,?,?)""",
            (1, i+1, ch_title, sample_content if i==0 else f'Chapter {i+1} content coming soon...', 'published', wc, max(0,1200-(i*80)), pub_date))
    db.commit()

def hash_password(pw):
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac('sha256', pw.encode(), salt.encode(), 260000)
    return f"{salt}${h.hex()}"

def check_password(pw, stored):
    try:
        salt, h = stored.split('$')
        new_h = hashlib.pbkdf2_hmac('sha256', pw.encode(), salt.encode(), 260000)
        return new_h.hex() == h
    except:
        return False

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ─────────────────────────────────────────
# AUTH DECORATOR
# ─────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth', next=request.url))
        return f(*args, **kwargs)
    return decorated

def get_current_user():
    if 'user_id' in session:
        return query_db("SELECT * FROM users WHERE id=?", [session['user_id']], one=True)
    return None

@app.context_processor
def inject_user():
    return dict(current_user=get_current_user())

# ─────────────────────────────────────────
# ROUTES — PUBLIC
# ─────────────────────────────────────────
@app.route('/')
def index():
    novels = query_db("""
        SELECT n.*, u.username, u.display_name,
               ROUND(CASE WHEN n.rating_count>0 THEN n.rating_sum/n.rating_count ELSE 0 END, 1) as avg_rating,
               (SELECT COUNT(*) FROM chapters WHERE novel_id=n.id AND status='published') as chapter_count
        FROM novels n JOIN users u ON n.author_id=u.id
        ORDER BY n.views DESC LIMIT 12
    """)
    latest = query_db("""
        SELECT n.*, u.username, u.display_name,
               ROUND(CASE WHEN n.rating_count>0 THEN n.rating_sum/n.rating_count ELSE 0 END,1) as avg_rating,
               (SELECT COUNT(*) FROM chapters WHERE novel_id=n.id AND status='published') as chapter_count
        FROM novels n JOIN users u ON n.author_id=u.id
        ORDER BY n.updated_at DESC LIMIT 8
    """)
    return render_template('index.html', novels=novels, latest=latest)

@app.route('/browse')
def browse():
    genre = request.args.get('genre','')
    sort = request.args.get('sort','views')
    q = request.args.get('q','')
    order = {'views':'n.views DESC','rating':'avg_rating DESC','latest':'n.updated_at DESC','chapters':'chapter_count DESC'}.get(sort,'n.views DESC')
    base = """
        SELECT n.*, u.username, u.display_name,
               ROUND(CASE WHEN n.rating_count>0 THEN n.rating_sum/n.rating_count ELSE 0 END,1) as avg_rating,
               (SELECT COUNT(*) FROM chapters WHERE novel_id=n.id AND status='published') as chapter_count
        FROM novels n JOIN users u ON n.author_id=u.id
    """
    wheres, args = [], []
    if genre:
        wheres.append("n.genres LIKE ?"); args.append(f'%{genre}%')
    if q:
        wheres.append("(n.title LIKE ? OR n.synopsis LIKE ?)"); args += [f'%{q}%',f'%{q}%']
    if wheres:
        base += " WHERE " + " AND ".join(wheres)
    base += f" ORDER BY {order}"
    novels = query_db(base, args)
    return render_template('browse.html', novels=novels, genre=genre, sort=sort, q=q)

@app.route('/novel/<int:novel_id>')
def novel(novel_id):
    n = query_db("""
        SELECT n.*, u.username, u.display_name, u.bio as author_bio,
               ROUND(CASE WHEN n.rating_count>0 THEN n.rating_sum/n.rating_count ELSE 0 END,1) as avg_rating,
               (SELECT COUNT(*) FROM chapters WHERE novel_id=n.id AND status='published') as chapter_count
        FROM novels n JOIN users u ON n.author_id=u.id WHERE n.id=?
    """, [novel_id], one=True)
    if not n:
        return redirect(url_for('index'))
    execute_db("UPDATE novels SET views=views+1 WHERE id=?", [novel_id])
    chapters = query_db("SELECT * FROM chapters WHERE novel_id=? AND status='published' ORDER BY chapter_number", [novel_id])
    in_library = False
    user_rating = None
    if 'user_id' in session:
        lib = query_db("SELECT 1 FROM library WHERE user_id=? AND novel_id=?", [session['user_id'], novel_id], one=True)
        in_library = lib is not None
        r = query_db("SELECT score FROM ratings WHERE user_id=? AND novel_id=?", [session['user_id'], novel_id], one=True)
        user_rating = r['score'] if r else None
    return render_template('novel.html', novel=n, chapters=chapters, in_library=in_library, user_rating=user_rating)

@app.route('/chapter/<int:chapter_id>')
def read_chapter(chapter_id):
    ch = query_db("""
        SELECT c.*, n.title as novel_title, n.id as novel_id, u.display_name as author_name, u.username as author_username
        FROM chapters c
        JOIN novels n ON c.novel_id=n.id
        JOIN users u ON n.author_id=u.id
        WHERE c.id=? AND c.status='published'
    """, [chapter_id], one=True)
    if not ch:
        return redirect(url_for('index'))
    execute_db("UPDATE chapters SET views=views+1 WHERE id=?", [chapter_id])
    prev_ch = query_db("SELECT id FROM chapters WHERE novel_id=? AND chapter_number=? AND status='published'",
        [ch['novel_id'], ch['chapter_number']-1], one=True)
    next_ch = query_db("SELECT id FROM chapters WHERE novel_id=? AND chapter_number=? AND status='published'",
        [ch['novel_id'], ch['chapter_number']+1], one=True)
    return render_template('reader.html', chapter=ch, prev_ch=prev_ch, next_ch=next_ch)

@app.route('/author/<username>')
def author_profile(username):
    user = query_db("SELECT * FROM users WHERE username=?", [username], one=True)
    if not user:
        return redirect(url_for('index'))
    novels = query_db("""
        SELECT n.*,
               ROUND(CASE WHEN n.rating_count>0 THEN n.rating_sum/n.rating_count ELSE 0 END,1) as avg_rating,
               (SELECT COUNT(*) FROM chapters WHERE novel_id=n.id AND status='published') as chapter_count
        FROM novels n WHERE n.author_id=? ORDER BY n.views DESC
    """, [user['id']])
    follower_count = query_db("SELECT COUNT(*) as c FROM follows WHERE following_id=?", [user['id']], one=True)['c']
    is_following = False
    if 'user_id' in session:
        f = query_db("SELECT 1 FROM follows WHERE follower_id=? AND following_id=?", [session['user_id'], user['id']], one=True)
        is_following = f is not None
    return render_template('profile.html', author=user, novels=novels, follower_count=follower_count, is_following=is_following)

# ─────────────────────────────────────────
# ROUTES — AUTH
# ─────────────────────────────────────────
@app.route('/auth', methods=['GET','POST'])
def auth():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('auth.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username','').strip()
    password = request.form.get('password','')
    user = query_db("SELECT * FROM users WHERE username=? OR email=?", [username, username], one=True)
    if user and check_password(password, user['password_hash']):
        session['user_id'] = user['id']
        session['username'] = user['username']
        flash(f"Welcome back, {user['display_name']}!", 'success')
        return redirect(url_for('dashboard'))
    flash('Invalid username or password.', 'error')
    return redirect(url_for('auth'))

@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username','').strip()
    email = request.form.get('email','').strip()
    password = request.form.get('password','')
    confirm = request.form.get('confirm_password','')
    display_name = request.form.get('display_name','').strip() or username

    if len(username) < 3 or len(username) > 20:
        flash('Username must be 3–20 characters.', 'error'); return redirect(url_for('auth'))
    if not username.replace('_','').replace('-','').isalnum():
        flash('Username can only contain letters, numbers, hyphens, underscores.', 'error'); return redirect(url_for('auth'))
    if '@' not in email or '.' not in email:
        flash('Please enter a valid email address.', 'error'); return redirect(url_for('auth'))
    if len(password) < 8:
        flash('Password must be at least 8 characters.', 'error'); return redirect(url_for('auth'))
    if password != confirm:
        flash('Passwords do not match.', 'error'); return redirect(url_for('auth'))

    existing = query_db("SELECT id FROM users WHERE username=? OR email=?", [username, email], one=True)
    if existing:
        flash('Username or email already taken.', 'error'); return redirect(url_for('auth'))

    uid = execute_db("INSERT INTO users (username,email,password_hash,display_name) VALUES (?,?,?,?)",
        [username, email, hash_password(password), display_name])
    session['user_id'] = uid
    session['username'] = username
    flash(f'Welcome to InkForge, {display_name}! Your legend begins now.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been signed out.', 'info')
    return redirect(url_for('index'))

# ─────────────────────────────────────────
# ROUTES — DASHBOARD
# ─────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    uid = session['user_id']
    user = query_db("SELECT * FROM users WHERE id=?", [uid], one=True)
    novels = query_db("""
        SELECT n.*,
               ROUND(CASE WHEN n.rating_count>0 THEN n.rating_sum/n.rating_count ELSE 0 END,1) as avg_rating,
               (SELECT COUNT(*) FROM chapters WHERE novel_id=n.id) as total_chapters,
               (SELECT COUNT(*) FROM chapters WHERE novel_id=n.id AND status='published') as pub_chapters
        FROM novels n WHERE n.author_id=? ORDER BY n.updated_at DESC
    """, [uid])
    total_views = query_db("SELECT SUM(views) as s FROM novels WHERE author_id=?", [uid], one=True)['s'] or 0
    total_chapters = query_db("SELECT COUNT(*) as c FROM chapters c JOIN novels n ON c.novel_id=n.id WHERE n.author_id=? AND c.status='published'", [uid], one=True)['c']
    followers = query_db("SELECT COUNT(*) as c FROM follows WHERE following_id=?", [uid], one=True)['c']
    return render_template('dashboard.html', user=user, novels=novels,
        total_views=total_views, total_chapters=total_chapters, followers=followers)

@app.route('/dashboard/new-novel', methods=['GET','POST'])
@login_required
def new_novel():
    if request.method == 'POST':
        title = request.form.get('title','').strip()
        synopsis = request.form.get('synopsis','').strip()
        status = request.form.get('status','Ongoing')
        genres = request.form.getlist('genres')
        if not title:
            flash('Novel title is required.','error')
            return redirect(url_for('new_novel'))
        cover_image = ''
        if 'cover' in request.files:
            f = request.files['cover']
            if f and f.filename and allowed_file(f.filename):
                filename = secure_filename(f"{session['user_id']}_{secrets.token_hex(8)}_{f.filename}")
                f.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                cover_image = filename
        nid = execute_db("INSERT INTO novels (author_id,title,synopsis,status,genres,cover_image) VALUES (?,?,?,?,?,?)",
            [session['user_id'], title, synopsis, status, ','.join(genres), cover_image])
        flash(f'"{title}" has been created!', 'success')
        return redirect(url_for('write_chapter', novel_id=nid))
    return render_template('new_novel.html')

@app.route('/dashboard/edit-novel/<int:novel_id>', methods=['GET','POST'])
@login_required
def edit_novel(novel_id):
    n = query_db("SELECT * FROM novels WHERE id=? AND author_id=?", [novel_id, session['user_id']], one=True)
    if not n:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        title = request.form.get('title','').strip()
        synopsis = request.form.get('synopsis','').strip()
        status = request.form.get('status','Ongoing')
        genres = request.form.getlist('genres')
        cover_image = n['cover_image']
        if 'cover' in request.files:
            f = request.files['cover']
            if f and f.filename and allowed_file(f.filename):
                filename = secure_filename(f"{session['user_id']}_{secrets.token_hex(8)}_{f.filename}")
                f.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                cover_image = filename
        execute_db("UPDATE novels SET title=?,synopsis=?,status=?,genres=?,cover_image=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            [title, synopsis, status, ','.join(genres), cover_image, novel_id])
        flash('Novel updated!','success')
        return redirect(url_for('novel', novel_id=novel_id))
    return render_template('edit_novel.html', novel=n)

@app.route('/write/<int:novel_id>', methods=['GET'])
@login_required
def write_chapter(novel_id):
    n = query_db("SELECT * FROM novels WHERE id=? AND author_id=?", [novel_id, session['user_id']], one=True)
    if not n:
        return redirect(url_for('dashboard'))
    chapter_id = request.args.get('chapter_id', type=int)
    chapter = None
    if chapter_id:
        chapter = query_db("SELECT * FROM chapters WHERE id=? AND novel_id=?", [chapter_id, novel_id], one=True)
    chapters = query_db("SELECT id,chapter_number,title,status,word_count FROM chapters WHERE novel_id=? ORDER BY chapter_number", [novel_id])
    next_num = (query_db("SELECT MAX(chapter_number) as m FROM chapters WHERE novel_id=?", [novel_id], one=True)['m'] or 0) + 1
    return render_template('editor.html', novel=n, chapter=chapter, chapters=chapters, next_num=next_num)

@app.route('/api/save-chapter', methods=['POST'])
@login_required
def save_chapter():
    data = request.get_json()
    novel_id = data.get('novel_id')
    chapter_id = data.get('chapter_id')
    title = data.get('title','Untitled Chapter').strip()
    content = data.get('content','')
    author_note = data.get('author_note','')
    status = data.get('status','draft')
    chapter_number = data.get('chapter_number', 1)
    word_count = len(content.split()) if content.strip() else 0

    n = query_db("SELECT id FROM novels WHERE id=? AND author_id=?", [novel_id, session['user_id']], one=True)
    if not n:
        return jsonify({'ok': False, 'error': 'Unauthorized'}), 403

    pub_date = 'CURRENT_TIMESTAMP' if status == 'published' else 'NULL'

    if chapter_id:
        existing = query_db("SELECT id FROM chapters WHERE id=? AND novel_id=?", [chapter_id, novel_id], one=True)
        if existing:
            execute_db(f"""UPDATE chapters SET title=?,content=?,author_note=?,status=?,
                           word_count=?,updated_at=CURRENT_TIMESTAMP,
                           published_at=CASE WHEN status!='published' AND ?='published' THEN CURRENT_TIMESTAMP ELSE published_at END
                           WHERE id=?""",
                [title, content, author_note, status, word_count, status, chapter_id])
            execute_db("UPDATE novels SET updated_at=CURRENT_TIMESTAMP WHERE id=?", [novel_id])
            return jsonify({'ok': True, 'chapter_id': chapter_id, 'word_count': word_count})

    new_id = execute_db("""INSERT INTO chapters (novel_id,chapter_number,title,content,author_note,status,word_count,published_at)
                           VALUES (?,?,?,?,?,?,?,CASE WHEN ?='published' THEN CURRENT_TIMESTAMP ELSE NULL END)""",
        [novel_id, chapter_number, title, content, author_note, status, word_count, status])
    execute_db("UPDATE novels SET updated_at=CURRENT_TIMESTAMP WHERE id=?", [novel_id])
    return jsonify({'ok': True, 'chapter_id': new_id, 'word_count': word_count})

@app.route('/api/delete-chapter/<int:chapter_id>', methods=['POST'])
@login_required
def delete_chapter(chapter_id):
    ch = query_db("SELECT c.* FROM chapters c JOIN novels n ON c.novel_id=n.id WHERE c.id=? AND n.author_id=?",
        [chapter_id, session['user_id']], one=True)
    if not ch:
        return jsonify({'ok': False}), 403
    execute_db("DELETE FROM chapters WHERE id=?", [chapter_id])
    return jsonify({'ok': True})

@app.route('/dashboard/settings', methods=['GET','POST'])
@login_required
def settings():
    user = query_db("SELECT * FROM users WHERE id=?", [session['user_id']], one=True)
    if request.method == 'POST':
        display_name = request.form.get('display_name','').strip()
        bio = request.form.get('bio','').strip()
        website = request.form.get('website','').strip()
        execute_db("UPDATE users SET display_name=?,bio=?,website=? WHERE id=?",
            [display_name or user['display_name'], bio, website, session['user_id']])
        new_pass = request.form.get('new_password','')
        if new_pass:
            if len(new_pass) < 8:
                flash('New password must be at least 8 characters.','error')
                return redirect(url_for('settings'))
            confirm = request.form.get('confirm_password','')
            if new_pass != confirm:
                flash('Passwords do not match.','error')
                return redirect(url_for('settings'))
            execute_db("UPDATE users SET password_hash=? WHERE id=?",[hash_password(new_pass), session['user_id']])
        flash('Settings saved!','success')
        return redirect(url_for('settings'))
    return render_template('settings.html', user=user)

# ─────────────────────────────────────────
# ROUTES — SOCIAL ACTIONS
# ─────────────────────────────────────────
@app.route('/api/library/<int:novel_id>', methods=['POST'])
@login_required
def toggle_library(novel_id):
    uid = session['user_id']
    exists = query_db("SELECT 1 FROM library WHERE user_id=? AND novel_id=?", [uid, novel_id], one=True)
    if exists:
        execute_db("DELETE FROM library WHERE user_id=? AND novel_id=?", [uid, novel_id])
        return jsonify({'ok': True, 'in_library': False})
    execute_db("INSERT INTO library (user_id,novel_id) VALUES (?,?)", [uid, novel_id])
    return jsonify({'ok': True, 'in_library': True})

@app.route('/api/follow/<int:target_id>', methods=['POST'])
@login_required
def toggle_follow(target_id):
    uid = session['user_id']
    if uid == target_id:
        return jsonify({'ok': False})
    exists = query_db("SELECT 1 FROM follows WHERE follower_id=? AND following_id=?", [uid, target_id], one=True)
    if exists:
        execute_db("DELETE FROM follows WHERE follower_id=? AND following_id=?", [uid, target_id])
        return jsonify({'ok': True, 'following': False})
    execute_db("INSERT INTO follows (follower_id,following_id) VALUES (?,?)", [uid, target_id])
    return jsonify({'ok': True, 'following': True})

@app.route('/api/rate/<int:novel_id>', methods=['POST'])
@login_required
def rate_novel(novel_id):
    score = float(request.get_json().get('score', 0))
    if not 1 <= score <= 5:
        return jsonify({'ok': False})
    uid = session['user_id']
    existing = query_db("SELECT score FROM ratings WHERE user_id=? AND novel_id=?", [uid, novel_id], one=True)
    if existing:
        old_score = existing['score']
        execute_db("UPDATE ratings SET score=? WHERE user_id=? AND novel_id=?", [score, uid, novel_id])
        execute_db("UPDATE novels SET rating_sum=rating_sum-?+? WHERE id=?", [old_score, score, novel_id])
    else:
        execute_db("INSERT INTO ratings (user_id,novel_id,score) VALUES (?,?,?)", [uid, novel_id, score])
        execute_db("UPDATE novels SET rating_sum=rating_sum+?,rating_count=rating_count+1 WHERE id=?", [score, novel_id])
    n = query_db("SELECT ROUND(rating_sum/rating_count,1) as avg FROM novels WHERE id=?", [novel_id], one=True)
    return jsonify({'ok': True, 'new_avg': n['avg']})

if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    init_db()
    print("\n" + "="*50)
    print("  InkForge is running!")
    print("  Open: http://localhost:5000")
    print("  Demo login: scribe / forge123")
    print("="*50 + "\n")
    app.run(debug=True, port=5000)
else:
    # Called by gunicorn in production
    init_db()
