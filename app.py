from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from authlib.integrations.flask_client import OAuth
import sqlite3
import os
import json
from voting import (
    calculate_rcv_winner, get_poll_results,
    calculate_borda_count, get_borda_rankings,
    calculate_condorcet_winner, get_pairwise_results,
    calculate_schulze_winners, get_schulze_details,
    calculate_all_winners
)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

DATABASE = 'static/db/polls.db'

# Flask-Login
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# Google OAuth
oauth = OAuth(app)
oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    access_token_url='https://accounts.google.com/o/oauth2/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params={'access_type': 'offline', 'prompt': 'select_account'},
    api_base_url='https://www.googleapis.com/oauth2/v2/',
    userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo',
    client_kwargs={'scope': 'openid email profile'},
)

class User(UserMixin):
    def __init__(self, id_, email, name):
        self.id = id_
        self.email = email
        self.name = name

@login_manager.user_loader
def load_user(user_id):
    with sqlite3.connect(DATABASE) as conn:
        cur = conn.cursor()
        cur.execute('SELECT id, email, name FROM users WHERE id=?', (user_id,))
        row = cur.fetchone()
        return User(*row) if row else None

def save_user(email, name):
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
    with sqlite3.connect(DATABASE) as conn:
        cur = conn.cursor()
        cur.execute('SELECT id FROM users WHERE email=?', (email,))
        user = cur.fetchone()
        if user:
            return user[0]
        cur.execute('INSERT INTO users (email, name) VALUES (?, ?)', (email, name))
        conn.commit()
        return cur.lastrowid

def init_db():
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
    with sqlite3.connect(DATABASE) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS polls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS options (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                poll_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                order_num INTEGER,
                FOREIGN KEY (poll_id) REFERENCES polls(id) ON DELETE CASCADE
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                poll_id INTEGER NOT NULL,
                ranked_choices TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (poll_id) REFERENCES polls(id) ON DELETE CASCADE
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS authorized_poll_users (
                poll_id INTEGER,
                user_id INTEGER,
                UNIQUE (poll_id, user_id),
                FOREIGN KEY (poll_id) REFERENCES polls(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        conn.commit()

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def user_is_authorized(poll_id, user_id):
    with sqlite3.connect(DATABASE) as conn:
        row = conn.execute('SELECT 1 FROM authorized_poll_users WHERE poll_id=? AND user_id=?', (poll_id, user_id)).fetchone()
        return bool(row)

@app.route('/login')
def login():
    redirect_uri = url_for('auth_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.')
    return redirect(url_for('index'))

@app.route('/auth/callback')
def auth_callback():
    try:
        token = oauth.google.authorize_access_token()
        userdata = oauth.google.parse_id_token(token)
        email = userdata['email']
        name = userdata.get('name', email)
        user_id = save_user(email, name)
        user = User(user_id, email, name)
        login_user(user)
        flash(f'Welcome, {name}!')
        return redirect(url_for('index'))
    except Exception as e:
        flash(f'Authentication error: {str(e)}')
        return redirect(url_for('index'))

@app.route('/')
def index():
    init_db()
    if current_user.is_authenticated:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT id, title, description, created_at, status FROM polls ORDER BY created_at DESC')
        polls = [
            {
                'id': row[0],
                'title': row[1],
                'description': row[2],
                'created_at': row[3],
                'status': row[4]
            }
            for row in cursor.fetchall()
        ]
        db.close()
        return render_template('index.html', polls=polls, user=current_user)
    return render_template('index.html', polls=[], user=None)

@app.route('/poll/create', methods=['GET', 'POST'])
@login_required
def create_poll():
    if request.method == 'POST':
        data = request.get_json()
        title = data.get('title')
        description = data.get('description')
        options = [o for o in data.get('options', []) if o.strip()]
        allowed_emails = [e for e in data.get('allowed_emails', []) if e.strip()]
        
        if not title or len(options) < 2:
            return jsonify({'error': 'Poll needs a title and at least 2 options'}), 400

        db = get_db()
        cursor = db.cursor()
        
        cursor.execute('INSERT INTO polls (title, description, status) VALUES (?, ?, ?)', 
                      (title, description, 'active'))
        poll_id = cursor.lastrowid
        
        for idx, option in enumerate(options):
            cursor.execute('INSERT INTO options (poll_id, text, order_num) VALUES (?, ?, ?)', 
                          (poll_id, option, idx))
        
        for email in allowed_emails:
            cursor.execute('SELECT id FROM users WHERE email=?', (email,))
            user_row = cursor.fetchone()
            if user_row:
                cursor.execute('INSERT OR IGNORE INTO authorized_poll_users (poll_id, user_id) VALUES (?, ?)', 
                              (poll_id, user_row[0]))
        
        db.commit()
        db.close()
        return jsonify({'id': poll_id, 'redirect': url_for('vote_poll', poll_id=poll_id)}), 201
    
    db = get_db()
    users = db.execute('SELECT id, email FROM users ORDER BY email').fetchall()
    db.close()
    return render_template('create-poll.html', users=[(row[0], row[1]) for row in users])

@app.route('/poll/<int:poll_id>')
@login_required
def vote_poll(poll_id):
    if not user_is_authorized(poll_id, current_user.id):
        flash('You are not authorized to vote in this poll.')
        return redirect(url_for('index'))
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT id, title, description, status FROM polls WHERE id = ?', (poll_id,))
    poll_row = cursor.fetchone()
    
    if not poll_row:
        db.close()
        return redirect(url_for('index'))
    
    cursor.execute('SELECT id, text FROM options WHERE poll_id = ? ORDER BY order_num', (poll_id,))
    options = [{'id': row[0], 'text': row[1]} for row in cursor.fetchall()]
    db.close()
    
    poll = {
        'id': poll_row[0],
        'title': poll_row[1],
        'description': poll_row[2],
        'status': poll_row[3],
        'options': options
    }
    
    return render_template('poll.html', poll=poll, user=current_user)

@app.route('/poll/<int:poll_id>/vote', methods=['POST'])
@login_required
def submit_vote(poll_id):
    if not user_is_authorized(poll_id, current_user.id):
        return jsonify({'error': 'Not authorized to vote.'}), 403
    
    data = request.get_json()
    ranked_choices = data.get('ranked_choices', [])
    
    if len(ranked_choices) == 0:
        return jsonify({'error': 'At least one choice is required'}), 400
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT id FROM options WHERE poll_id = ?', (poll_id,))
    valid_option_ids = {row[0] for row in cursor.fetchall()}
    
    if not all(choice_id in valid_option_ids for choice_id in ranked_choices):
        db.close()
        return jsonify({'error': 'Invalid choices for this poll'}), 400
    
    cursor.execute('INSERT INTO votes (poll_id, ranked_choices) VALUES (?, ?)', 
                  (poll_id, json.dumps(ranked_choices)))
    db.commit()
    db.close()
    
    return jsonify({'success': True, 'message': 'Vote recorded'}), 201

@app.route('/poll/<int:poll_id>/results')
@login_required
def poll_results(poll_id):
    if not user_is_authorized(poll_id, current_user.id):
        flash('You are not authorized to view this poll\'s results.')
        return redirect(url_for('index'))
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT id, title, description FROM polls WHERE id = ?', (poll_id,))
    poll_row = cursor.fetchone()
    
    if not poll_row:
        db.close()
        return redirect(url_for('index'))
    
    cursor.execute('SELECT id, text FROM options WHERE poll_id = ? ORDER BY order_num', (poll_id,))
    options = {row[0]: row[1] for row in cursor.fetchall()}
    cursor.execute('SELECT ranked_choices FROM votes WHERE poll_id = ?', (poll_id,))
    votes = [json.loads(row[0]) for row in cursor.fetchall()]
    db.close()
    
    candidate_ids = list(options.keys())
    all_winners = calculate_all_winners(votes, candidate_ids)
    irv_rounds = get_poll_results(votes, candidate_ids)
    borda_rankings = get_borda_rankings(votes, candidate_ids)
    pairwise_results = get_pairwise_results(votes, candidate_ids)
    schulze_winners, schulze_paths = get_schulze_details(votes, candidate_ids)
    
    results = {
        'poll_id': poll_row[0],
        'title': poll_row[1],
        'description': poll_row[2],
        'options': options,
        'total_votes': len(votes),
        'irv_winner': all_winners['irv'],
        'irv_winner_name': options.get(all_winners['irv']) if all_winners['irv'] else None,
        'irv_rounds': irv_rounds,
        'borda_winner': all_winners['borda'],
        'borda_winner_name': options.get(all_winners['borda']) if all_winners['borda'] else None,
        'borda_scores': {options[cid]: score for cid, score in all_winners['borda_scores'].items()},
        'borda_rankings': [(options[cid], score) for cid, score in borda_rankings],
        'condorcet_winner': all_winners['condorcet'],
        'condorcet_winner_name': options.get(all_winners['condorcet']) if all_winners['condorcet'] else None,
        'pairwise_results': pairwise_results,
        'schulze_winners': all_winners['schulze'],
        'schulze_winner_names': [options[wid] for wid in all_winners['schulze']],
        'schulze_paths': schulze_paths
    }
    
    return render_template('results.html', results=results, user=current_user)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
