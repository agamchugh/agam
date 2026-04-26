import os
import sqlite3
import math
from flask import Flask, render_template, request, redirect, url_for, session, jsonify

app = Flask(__name__)
app.secret_key = 'agam_rickshaw_secure_key'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'users.db')

# --- DATABASE UTILITY ---
def query_db(query, args=(), one=False, commit=False):
    """Connects, executes, and closes automatically to prevent lag/locks."""
    with sqlite3.connect(DB_PATH, timeout=10) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(query, args)
        if commit: conn.commit()
        rv = cur.fetchall()
        return (rv[0] if rv else None) if one else rv

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, email TEXT NOT NULL UNIQUE, 
            mobile TEXT, password TEXT NOT NULL, role TEXT DEFAULT 'rider', 
            lat REAL DEFAULT 0, lon REAL DEFAULT 0, is_online BOOLEAN DEFAULT 0)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS rides (
            id INTEGER PRIMARY KEY AUTOINCREMENT, rider_id INTEGER, driver_id INTEGER, 
            status TEXT DEFAULT 'pending')''')

init_db()

def get_distance(lat1, lon1, lat2, lon2):
    R = 6371
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))

# --- ROUTES ---
@app.route('/')
def home(): return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        data = (request.form.get('username'), request.form.get('email'), request.form.get('mobile'), request.form.get('password'), request.form.get('role'))
        try:
            query_db('INSERT INTO users (username, email, mobile, password, role) VALUES (?, ?, ?, ?, ?)', data, commit=True)
            return redirect(url_for('login'))
        except: return "Error: Email exists."
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = query_db('SELECT * FROM users WHERE email = ? AND password = ?', (request.form.get('email'), request.form.get('password')), one=True)
        if user:
            session.update({'user_id': user['id'], 'username': user['username'], 'role': user['role'], 'is_admin': (user['email'] == 'agamchugh153@gmail.com')})
            return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('dashboard.html', username=session['username'], role=session['role'], is_admin=session.get('is_admin'))

@app.route('/update_location', methods=['POST'])
def update_location():
    query_db('UPDATE users SET lat = ?, lon = ? WHERE id = ?', (request.json['latitude'], request.json['longitude'], session['user_id']), commit=True)
    return jsonify({"status": "success"})

@app.route('/book_ride', methods=['POST'])
def book_ride():
    user = query_db('SELECT lat, lon FROM users WHERE id = ?', (session['user_id'],), one=True)
    drivers = query_db('SELECT id, lat, lon FROM users WHERE role = "driver" AND is_online = 1')
    for d in drivers:
        if get_distance(user['lat'], user['lon'], d['lat'], d['lon']) <= 10.5: # 1.5 KM RANGE
            query_db('DELETE FROM rides WHERE rider_id = ? AND status = "pending"', (session['user_id'],), commit=True)
            query_db('INSERT INTO rides (rider_id, driver_id, status) VALUES (?, ?, "pending")', (session['user_id'], d['id']), commit=True)
            return jsonify({"status": "success"})
    return jsonify({"status": "none"})

@app.route('/get_active_ride')
def get_active_ride():
    uid = session['user_id']
    role_col = 'driver_id' if session['role'] == 'driver' else 'rider_id'
    join_col = 'rider_id' if session['role'] == 'driver' else 'driver_id'
    res = query_db(f'''SELECT u.username, u.lat, u.lon, r.status FROM rides r 
                       JOIN users u ON r.{join_col} = u.id WHERE r.{role_col} = ? 
                       AND r.status IN ('accepted', 'completed') ORDER BY r.id DESC LIMIT 1''', (uid,), one=True)
    return jsonify({"name": res[0], "lat": res[1], "lon": res[2], "status": res[3]}) if res else jsonify({"status": "none"})

@app.route('/accept_ride/<int:ride_id>', methods=['POST'])
def accept_ride(ride_id):
    ride = query_db('SELECT rider_id FROM rides WHERE id = ?', (ride_id,), one=True)
    if ride:
        query_db('DELETE FROM rides WHERE rider_id = ? AND status = "pending" AND id != ?', (ride['rider_id'], ride_id), commit=True)
        query_db('UPDATE rides SET status = "accepted" WHERE id = ?', (ride_id,), commit=True)
    return jsonify({"status": "success"})

@app.route('/finish_trip', methods=['POST'])
def finish_trip():
    query_db("UPDATE rides SET status = 'completed' WHERE driver_id = ? AND status = 'accepted'", (session['user_id'],), commit=True)
    return jsonify({"status": "success"})

@app.route('/clear_completed_ride', methods=['POST'])
def clear_completed_ride():
    query_db("DELETE FROM rides WHERE (driver_id = ? OR rider_id = ?) AND status = 'completed'", (session['user_id'], session['user_id']), commit=True)
    return jsonify({"status": "success"})

@app.route('/check_requests')
def check_requests():
    res = query_db('''SELECT r.id, u.username FROM rides r JOIN users u ON r.rider_id = u.id 
                      WHERE r.driver_id = ? AND r.status = "pending"''', (session['user_id'],), one=True)
    return jsonify({"ride_id": res[0], "rider_name": res[1]}) if res else jsonify({"ride_id": None})

@app.route('/toggle_status', methods=['POST'])
def toggle_status():
    user = query_db('SELECT is_online FROM users WHERE id = ?', (session['user_id'],), one=True)
    new_val = 0 if user['is_online'] == 1 else 1
    query_db('UPDATE users SET is_online = ? WHERE id = ?', (new_val, session['user_id']), commit=True)
    return jsonify({"is_online": new_val})

@app.route('/logout')
def logout(): 
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__': app.run(debug=True, host='0.0.0.0', port=5000)
