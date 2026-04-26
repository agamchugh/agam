import os
import sqlite3
import math
from flask import Flask, render_template, request, redirect, url_for, session, jsonify

app = Flask(__name__)
app.secret_key = 'agam_rickshaw_secure_key'

# --- DATABASE PATH FIX ---
# This ensures the database is always in the same folder as app.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'users.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row # This makes results easier to handle
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        username TEXT, 
        email TEXT NOT NULL UNIQUE, 
        mobile TEXT, 
        password TEXT NOT NULL, 
        role TEXT DEFAULT 'rider', 
        lat REAL DEFAULT 0, 
        lon REAL DEFAULT 0, 
        is_online BOOLEAN DEFAULT 0)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS rides (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        rider_id INTEGER, 
        driver_id INTEGER, 
        status TEXT DEFAULT 'pending')''')
    conn.commit()
    conn.close()

init_db()

# --- HELPER FUNCTIONS ---
def get_distance(lat1, lon1, lat2, lon2):
    R = 6371
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))

# --- ROUTES ---
@app.route('/')
def home(): 
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        role, user, email, mob, pwd = request.form.get('role'), request.form.get('username'), request.form.get('email'), request.form.get('mobile'), request.form.get('password')
        try:
            conn = get_db_connection()
            conn.execute('INSERT INTO users (username, email, mobile, password, role) VALUES (?, ?, ?, ?, ?)', (user, email, mob, pwd, role))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except Exception as e: 
            return f"Signup Error: {e}"
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email, pwd = request.form.get('email'), request.form.get('password')
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ? AND password = ?', (email, pwd)).fetchone()
        conn.close()
        if user:
            is_admin = (user['email'] == 'agamchugh153@gmail.com')
            session.update({'user_id': user['id'], 'username': user['username'], 'role': user['role'], 'is_admin': is_admin})
            return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('dashboard.html', username=session['username'], role=session['role'], is_admin=session.get('is_admin'))

@app.route('/admin_panel')
def admin_panel():
    if not session.get('is_admin'): 
        return "Unauthorized Access", 403
    conn = get_db_connection()
    users = conn.execute('SELECT id, username, email, role, is_online FROM users').fetchall()
    rides = conn.execute('''SELECT rides.id, u1.username as rider, u2.username as driver, rides.status 
                          FROM rides 
                          JOIN users u1 ON rides.rider_id = u1.id 
                          JOIN users u2 ON rides.driver_id = u2.id''').fetchall()
    conn.close()
    return render_template('admin.html', users=users, rides=rides)

@app.route('/update_location', methods=['POST'])
def update_location():
    data = request.json
    conn = get_db_connection()
    conn.execute('UPDATE users SET lat = ?, lon = ? WHERE id = ?', (data['latitude'], data['longitude'], session['user_id']))
    conn.commit(); conn.close()
    return jsonify({"status": "success"})

@app.route('/book_ride', methods=['POST'])
def book_ride():
    uid = session.get('user_id')
    conn = get_db_connection()
    user = conn.execute('SELECT lat, lon FROM users WHERE id = ?', (uid,)).fetchone()
    drivers = conn.execute('SELECT id, lat, lon FROM users WHERE role = "driver" AND is_online = 1').fetchall()
    
    for d in drivers:
        if get_distance(user['lat'], user['lon'], d['lat'], d['lon']) <= 50.0:
            conn.execute("DELETE FROM rides WHERE rider_id = ? AND status != 'accepted'", (uid,))
            conn.execute('INSERT INTO rides (rider_id, driver_id, status) VALUES (?, ?, "pending")', (uid, d['id']))
            conn.commit(); conn.close()
            return jsonify({"status": "success"})
    conn.close(); return jsonify({"status": "none"})

@app.route('/get_active_ride')
def get_active_ride():
    if 'user_id' not in session: return jsonify({"status": "none"})
    uid = session['user_id']
    conn = get_db_connection()
    if session['role'] == 'driver':
        res = conn.execute('''SELECT u.username, u.lat, u.lon, r.status FROM rides r
                              JOIN users u ON r.rider_id = u.id WHERE r.driver_id = ? 
                              AND r.status IN ('accepted', 'completed') ORDER BY r.id DESC LIMIT 1''', (uid,)).fetchone()
    else:
        res = conn.execute('''SELECT u.username, u.lat, u.lon, r.status FROM rides r
                              JOIN users u ON r.driver_id = u.id WHERE r.rider_id = ? 
                              AND r.status IN ('accepted', 'completed') ORDER BY r.id DESC LIMIT 1''', (uid,)).fetchone()
    conn.close()
    return jsonify({"name": res[0], "lat": res[1], "lon": res[2], "status": res[3]}) if res else jsonify({"status": "none"})

@app.route('/accept_ride/<int:ride_id>', methods=['POST'])
def accept_ride(ride_id):
    conn = get_db_connection()
    conn.execute('UPDATE rides SET status = "accepted" WHERE id = ?', (ride_id,))
    conn.commit(); conn.close()
    return jsonify({"status": "success"})

@app.route('/finish_trip', methods=['POST'])
def finish_trip():
    uid = session.get('user_id')
    conn = get_db_connection()
    conn.execute("UPDATE rides SET status = 'completed' WHERE driver_id = ? AND status = 'accepted'", (uid,))
    conn.commit(); conn.close()
    return jsonify({"status": "success"})

@app.route('/check_requests')
def check_requests():
    did = session.get('user_id')
    conn = get_db_connection()
    res = conn.execute('''SELECT rides.id, users.username FROM rides JOIN users ON rides.rider_id = users.id WHERE rides.driver_id = ? AND rides.status = "pending"''', (did,)).fetchone()
    conn.close()
    return jsonify({"ride_id": res[0], "rider_name": res[1]}) if res else jsonify({"ride_id": None})

@app.route('/toggle_status', methods=['POST'])
def toggle_status():
    conn = get_db_connection()
    user = conn.execute('SELECT is_online FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    new_val = 0 if user['is_online'] == 1 else 1
    conn.execute('UPDATE users SET is_online = ? WHERE id = ?', (new_val, session['user_id']))
    conn.commit(); conn.close()
    return jsonify({"is_online": new_val})

@app.route('/logout')
def logout(): 
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__': 
    app.run(debug=True)
