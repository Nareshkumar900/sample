from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'servicemgmt_secret_2024'

DB_PATH = 'service_app.db'

# ─── Database Setup ───────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS service_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        service_category TEXT NOT NULL,
        service_type TEXT NOT NULL,
        description TEXT,
        address TEXT NOT NULL,
        phone TEXT NOT NULL,
        status TEXT DEFAULT 'Pending',
        admin_note TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # Seed default admin
    c.execute("SELECT * FROM admins WHERE username='admin'")
    if not c.fetchone():
        c.execute("INSERT INTO admins (username, password) VALUES (?, ?)", ('admin', 'admin123'))

    conn.commit()
    conn.close()

# ─── Decorators ───────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('user_login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_id' not in session:
            flash('Admin access required.', 'warning')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

# ─── Public Routes ────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')

# ─── User Auth ────────────────────────────────────────────────────────────────

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        confirm = request.form['confirm_password']

        if password != confirm:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')

        conn = get_db()
        try:
            conn.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)", (name, email, password))
            conn.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('user_login'))
        except sqlite3.IntegrityError:
            flash('Email already registered.', 'error')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password)).fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            return redirect(url_for('user_dashboard'))
        flash('Invalid email or password.', 'error')
    return render_template('user_login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# ─── User Dashboard ───────────────────────────────────────────────────────────

@app.route('/dashboard')
@login_required
def user_dashboard():
    conn = get_db()
    requests_list = conn.execute(
        "SELECT * FROM service_requests WHERE user_id=? ORDER BY created_at DESC",
        (session['user_id'],)
    ).fetchall()
    conn.close()

    stats = {
        'total': len(requests_list),
        'pending': sum(1 for r in requests_list if r['status'] == 'Pending'),
        'in_progress': sum(1 for r in requests_list if r['status'] == 'In Progress'),
        'completed': sum(1 for r in requests_list if r['status'] == 'Completed'),
    }
    return render_template('user_dashboard.html', requests=requests_list, stats=stats)

@app.route('/submit-request', methods=['GET', 'POST'])
@login_required
def submit_request():
    services = {
        'Maintenance': ['Home Maintenance', 'Water Leakage Issues', 'Plumbing Issues'],
        'Cleaning': ['Home Cleaning', 'Office Cleaning', 'Factory Cleaning'],
        'Repair': ['Electrical Repair', 'Computer Repair']
    }
    if request.method == 'POST':
        category = request.form['service_category']
        stype = request.form['service_type']
        description = request.form['description'].strip()
        address = request.form['address'].strip()
        phone = request.form['phone'].strip()

        conn = get_db()
        conn.execute(
            "INSERT INTO service_requests (user_id, service_category, service_type, description, address, phone) VALUES (?,?,?,?,?,?)",
            (session['user_id'], category, stype, description, address, phone)
        )
        conn.commit()
        conn.close()
        flash('Your service request has been submitted successfully!', 'success')
        return redirect(url_for('user_dashboard'))
    return render_template('submit_request.html', services=services)

@app.route('/request/<int:req_id>')
@login_required
def view_request(req_id):
    conn = get_db()
    req = conn.execute(
        "SELECT * FROM service_requests WHERE id=? AND user_id=?",
        (req_id, session['user_id'])
    ).fetchone()
    conn.close()
    if not req:
        flash('Request not found.', 'error')
        return redirect(url_for('user_dashboard'))
    return render_template('view_request.html', req=req)

# ─── Admin Auth ───────────────────────────────────────────────────────────────

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        conn = get_db()
        admin = conn.execute("SELECT * FROM admins WHERE username=? AND password=?", (username, password)).fetchone()
        conn.close()
        if admin:
            session['admin_id'] = admin['id']
            session['admin_name'] = admin['username']
            return redirect(url_for('admin_dashboard'))
        flash('Invalid credentials.', 'error')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('index'))

# ─── Admin Dashboard ──────────────────────────────────────────────────────────

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    conn = get_db()
    all_requests = conn.execute('''
        SELECT sr.*, u.name as user_name, u.email as user_email
        FROM service_requests sr
        JOIN users u ON sr.user_id = u.id
        ORDER BY sr.created_at DESC
    ''').fetchall()

    stats = {
        'total': len(all_requests),
        'pending': sum(1 for r in all_requests if r['status'] == 'Pending'),
        'in_progress': sum(1 for r in all_requests if r['status'] == 'In Progress'),
        'completed': sum(1 for r in all_requests if r['status'] == 'Completed'),
        'users': conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    }
    conn.close()
    return render_template('admin_dashboard.html', requests=all_requests, stats=stats)

@app.route('/admin/request/<int:req_id>', methods=['GET', 'POST'])
@admin_required
def admin_view_request(req_id):
    conn = get_db()
    if request.method == 'POST':
        status = request.form['status']
        note = request.form['admin_note'].strip()
        conn.execute(
            "UPDATE service_requests SET status=?, admin_note=?, updated_at=? WHERE id=?",
            (status, note, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), req_id)
        )
        conn.commit()
        flash('Request updated successfully.', 'success')
        return redirect(url_for('admin_dashboard'))

    req = conn.execute('''
        SELECT sr.*, u.name as user_name, u.email as user_email
        FROM service_requests sr
        JOIN users u ON sr.user_id = u.id
        WHERE sr.id=?
    ''', (req_id,)).fetchone()
    conn.close()
    if not req:
        flash('Request not found.', 'error')
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_view_request.html', req=req)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
