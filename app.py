import os
import sqlite3
import math
from flask import Flask, render_template, request, redirect, url_for, session, jsonify

app = Flask(__name__)
app.secret_key = 'agam_rickshaw_secure_key'

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT, email TEXT NOT NULL UNIQUE,
            mobile TEXT, password TEXT NOT NULL,
            role TEXT DEFAULT 'rider', lat REAL DEFAULT 0, lon REAL DEFAULT 0, is_online BOOLEAN DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rider_id INTEGER, driver_id INTEGER,
            status TEXT DEFAULT 'pending'
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Distance Math
def get_distance(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))

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
            cursor.execute('INSERT INTO users (username, email, mobile, password, role) VALUES (?, ?, ?, ?, ?)', 
                           (username, email, mobile, password, role))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except Exception as e:
            return f"Error: {str(e)}. <a href='/signup'>Try again</a>"
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
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('dashboard.html', username=session['username'], email=session['email'], role=session['role'], is_admin=session.get('is_admin'))

@app.route('/update_location', methods=['POST'])
def update_location():
    if 'user_id' not in session: return jsonify({"status": "unauthorized"}), 401
    data = request.json
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET lat = ?, lon = ?, is_online = 1 WHERE id = ?', 
                   (data.get('latitude'), data.get('longitude'), session['user_id']))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/book_ride', methods=['POST'])
def book_ride():
    rider_id = session.get('user_id')
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT lat, lon FROM users WHERE id = ?', (rider_id,))
    r_lat, r_lon = cursor.fetchone()
    cursor.execute('SELECT id, lat, lon FROM users WHERE role = "driver" AND is_online = 1')
    drivers = cursor.fetchall()
    
    best_driver = None
    for d_id, d_lat, d_lon in drivers:
        if get_distance(r_lat, r_lon, d_lat, d_lon) <= 1.5:
            best_driver = d_id
            break
            
    if best_driver:
        cursor.execute('INSERT INTO rides (rider_id, driver_id) VALUES (?, ?)', (rider_id, best_driver))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Driver Found! Request sent."})
    conn.close()
    return jsonify({"status": "none", "message": "No autos nearby (1.5km)."})

@app.route('/check_requests')
def check_requests():
    driver_id = session.get('user_id')
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT rides.id, users.username FROM rides JOIN users ON rides.rider_id = users.id WHERE driver_id = ? AND status = "pending"', (driver_id,))
    res = cursor.fetchone()
    conn.close()
    return jsonify({"ride_id": res[0], "rider_name": res[1]}) if res else jsonify({"ride_id": None})

@app.route('/admin')
def admin():
    if session.get('email') != 'agamchugh153@gmail.com': return "Denied"
    conn = sqlite3.connect('users.db')
    users = conn.execute('SELECT id, username, email, mobile, role FROM users').fetchall()
    conn.close()
    return render_template('admin.html', users=users)

@app.route('/delete/<int:id>')
def delete_user(id):
    if session.get('email') != 'agamchugh153@gmail.com': return "Denied"
    conn = sqlite3.connect('users.db'); conn.execute('DELETE FROM users WHERE id = ?', (id,)); conn.commit(); conn.close()
    return redirect(url_for('admin'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
