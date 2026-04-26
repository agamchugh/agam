import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, jsonify

app = Flask(__name__)
app.secret_key = 'supersecretkey_agam'

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    # Schema includes role and location for Uber-style matching
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            email TEXT NOT NULL UNIQUE,
            mobile TEXT,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'rider',
            lat REAL DEFAULT 0,
            lon REAL DEFAULT 0,
            is_online BOOLEAN DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- ROUTES ---

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        role = request.form.get('role')
        username = request.form.get('username')
        email = request.form.get('email')
        mobile = request.form.get('mobile')
        password = request.form.get('password')
        
        try:
            conn = sqlite3.connect('users.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (username, email, mobile, password, role) 
                VALUES (?, ?, ?, ?, ?)
            ''', (username, email, mobile, password, role))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return "Email exists! <a href='/signup'>Try again</a>"
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE email = ? AND password = ?', (email, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['email'] = user[2]
            session['role'] = user[5]
            session['is_admin'] = (user[2] == 'agamchugh153@gmail.com')
            return redirect(url_for('dashboard'))
        else:
            return "Invalid Login! <a href='/login'>Try again</a>"
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'email' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', 
                           username=session.get('username'),
                           email=session.get('email'), 
                           role=session.get('role'),
                           is_admin=session.get('is_admin'))

@app.route('/update_location', methods=['POST'])
def update_location():
    if 'user_id' not in session:
        return jsonify({"status": "error"}), 401
    data = request.json
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET lat = ?, lon = ?, is_online = 1 WHERE id = ?', 
                   (data.get('latitude'), data.get('longitude'), session['user_id']))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/admin')
def admin():
    if 'email' not in session or session.get('email') != 'agamchugh153@gmail.com':
        return "Access Denied!"
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, email, mobile, role FROM users')
    users = cursor.fetchall()
    conn.close()
    return render_template('admin.html', users=users)

@app.route('/delete/<int:id>')
def delete_user(id):
    if 'email' not in session or session.get('email') != 'agamchugh153@gmail.com':
        return "Access Denied!"
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM users WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
