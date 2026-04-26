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
    # Main Users Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT, email TEXT NOT NULL UNIQUE,
            mobile TEXT, password TEXT NOT NULL,
            role TEXT DEFAULT 'rider', 
            lat REAL DEFAULT 0, 
            lon REAL DEFAULT 0, 
            is_online BOOLEAN DEFAULT 0
        )
    ''')
    # Ride Tracking Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rider_id INTEGER, 
            driver_id INTEGER,
            status TEXT DEFAULT 'pending'
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Distance calculation formula (Haversine)
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
    return render_template('dashboard.html', username=session['username'], role=session['role'], is_admin=session.get('is_admin'))

@app.route('/toggle_status', methods=['POST'])
def toggle_status():
    if 'user_id' not in session: return jsonify({"status": "error"}), 401
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT is_online FROM users WHERE id = ?', (session['user_id'],))
    new_status = 0 if cursor.fetchone()[0] == 1 else 1
    cursor.execute('UPDATE users SET is_online = ? WHERE id = ?', (new_status, session['user_id']))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "is_online": new_status})

@app.route('/update_location', methods=['POST'])
def update_location():
    if 'user_id' not in session: return jsonify({"status": "unauthorized"}), 401
    data = request.json
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET lat = ?, lon = ? WHERE id = ?', 
                   (data.get('latitude'), data.get('longitude'), session['user_id']))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/get_nearby_drivers')
def get_nearby_drivers():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    # Fetch all online drivers to show on the Rider's map discovery
    cursor.execute('SELECT username, lat, lon FROM users WHERE role = "driver" AND is_online = 1')
    drivers = [{"name": row[0], "lat": row[1], "lon": row[2]} for row in cursor.fetchall()]
    conn.close()
    return jsonify(drivers)

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
        if get_distance(r_lat, r_lon, d_lat, d_lon) <= 3.0: # 3km booking range
            best_driver = d_id
            break
            
    if best_driver:
        cursor.execute('INSERT INTO rides (rider_id, driver_id) VALUES (?, ?)', (rider_id, best_driver))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": "Request sent to nearest Rickshaw!"})
    conn.close()
    return jsonify({"status": "none", "message": "No rickshaws found nearby."})

@app.route('/check_requests')
def check_requests():
    driver_id = session.get('user_id')
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT rides.id, users.username 
        FROM rides JOIN users ON rides.rider_id = users.id 
        WHERE driver_id = ? AND status = "pending"
    ''', (driver_id,))
    res = cursor.fetchone()
    conn.close()
    return jsonify({"ride_id": res[0], "rider_name": res[1]}) if res else jsonify({"ride_id": None})

@app.route('/accept_ride/<int:ride_id>', methods=['POST'])
def accept_ride(ride_id):
    conn =
