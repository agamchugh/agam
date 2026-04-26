import os
import sqlite3
import math
from flask import Flask, render_template, request, redirect, url_for, session, jsonify

app = Flask(__name__)
app.secret_key = 'agam_rickshaw_secure_key'

# --- DATABASE INIT ---
def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT, email TEXT NOT NULL UNIQUE,
            mobile TEXT, password TEXT NOT NULL,
            role TEXT DEFAULT 'rider', 
            lat REAL DEFAULT 0, lon REAL DEFAULT 0, 
            is_online BOOLEAN DEFAULT 0
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

# --- HELPER FUNCTIONS ---
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
        role, user, email, mob, pwd = request.form.get('role'), request.form.get('username'), request.form.get('email'), request.form.get('mobile'), request.form.get('password')
        try:
            conn = sqlite3.connect('users.db')
            conn.execute('INSERT INTO users (username, email, mobile, password, role) VALUES (?, ?, ?, ?, ?)', (user, email, mob, pwd, role))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except: return "Signup Error: Email exists."
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email, pwd = request.form.get('email'), request.form.get('password')
        conn = sqlite3.connect('users.db')
        user = conn.execute('SELECT * FROM users WHERE email = ? AND password = ?', (email, pwd)).fetchone()
        conn.close()
        if user:
            # SECURITY LOCK: Only your email gets 'is_admin' = True
            is_admin_user = (user[2] == 'agamchugh153@gmail.com')
            
            session.update({
                'user_id': user[0], 
                'username': user[1], 
                'role': user[5],
                'is_admin': is_admin_user
            })
            return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('dashboard.html', username=session['username'], role=session['role'], is_admin=session.get('is_admin'))

# --- ADMIN PANEL (SECURE) ---
@app.route('/admin_panel')
def admin_panel():
    # If someone tries to type the URL manually, this block kicks them out
    if not session.get('is_admin'):
        return "<h1>403 Forbidden</h1><p>Only Agam can see this page.</p>", 403
        
    conn = sqlite3.connect('users.db')
    users = conn.execute('SELECT id, username, email, role, is_online FROM users').fetchall()
    rides = conn.execute('''
        SELECT rides.id, u1.username, u2.username, rides.status 
        FROM rides 
        JOIN users u1 ON rides.rider_id = u1.id 
        JOIN users u2 ON rides.driver_id = u2.id
    ''').fetchall()
    conn.close()
    return render_template('admin.html', users=users, rides=rides)

@app.route('/delete_user/<int:uid>')
def delete_user(uid):
    if session.get('is_admin'):
        conn = sqlite3.connect('users.db')
        conn.execute('DELETE FROM users WHERE id = ?', (uid,))
        conn.commit()
        conn.close()
    return redirect(url_for('admin_panel'))

# --- RIDE & LOCATION LOGIC (Keep existing) ---
@app.route('/update_location', methods=['POST'])
def update_location():
    data = request.json
    conn = sqlite3.connect('users.db')
    conn.execute('UPDATE users SET lat = ?, lon = ? WHERE id = ?', (data['latitude'], data['longitude'], session['user_id']))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/get_nearby_drivers')
def get_nearby_drivers():
    conn = sqlite3.connect('users.db')
    drivers = conn.execute('SELECT username, lat, lon FROM users WHERE role = "driver" AND is_online = 1 AND id != ?', (session.get('user_id', 0),)).fetchall()
    conn.close()
    return jsonify([{"name": r[0], "lat": r[1], "lon": r[2]} for r in drivers])

@app.route('/toggle_status', methods=['POST'])
def toggle_status():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT is_online FROM users WHERE id = ?', (session['user_id'],))
    new_status = 0 if cursor.fetchone()[0] == 1 else 1
    cursor.execute('UPDATE users SET is_online = ? WHERE id = ?', (new_status, session['user_id']))
    conn.commit()
    conn.close()
    return jsonify({"is_online": new_status})

@app.route('/book_ride', methods=['POST'])
def book_ride():
    uid = session.get('user_id')
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT lat, lon FROM users WHERE id = ?', (uid,))
    r_lat, r_lon = cursor.fetchone()
    drivers = conn.execute('SELECT id, lat, lon FROM users WHERE role = "driver" AND is_online = 1').fetchall()
    for d_id, d_lat, d_lon in drivers:
        if get_distance(r_lat, r_lon, d_lat, d_lon) <= 50.0:
            cursor.execute("DELETE FROM rides WHERE rider_id = ? AND status != 'accepted'", (uid,))
            cursor.execute('INSERT INTO rides (rider_id, driver_id, status) VALUES (?, ?, "pending")', (uid, d_id))
            conn.commit()
            conn.close()
            return jsonify({"status": "success"})
    conn.close()
    return jsonify({"status": "none"})

@app.route('/cancel_ride', methods=['POST'])
def cancel_ride():
    uid = session.get('user_id')
    conn = sqlite3.connect('users.db')
    conn.execute("UPDATE rides SET status = 'cancelled' WHERE (rider_id = ? OR driver_id = ?) AND status IN ('pending', 'accepted')", (uid, uid))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/check_requests')
def check_requests():
    did = session.get('user_id')
    conn = sqlite3.connect('users.db')
    res = conn.execute('''SELECT rides.id, users.username FROM rides 
                          JOIN users ON rides.rider_id = users.id 
                          WHERE rides.driver_id = ? AND rides.status = "pending"''', (did,)).fetchone()
    conn.close()
    return jsonify({"ride_id": res[0], "rider_name": res[1]}) if res else jsonify({"ride_id": None})

@app.route('/accept_ride/<int:ride_id>', methods=['POST'])
def accept_ride(ride_id):
    conn = sqlite3.connect('users.db')
    conn.execute('UPDATE rides SET status = "accepted" WHERE id = ?', (ride_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

@app.route('/ride_status')
def ride_status():
    conn = sqlite3.connect('users.db')
    res = conn.execute('''SELECT rides.status, users.username, users.mobile, users.lat, users.lon 
                          FROM rides JOIN users ON rides.driver_id = users.id 
                          WHERE rides.rider_id = ? ORDER BY rides.id DESC LIMIT 1''', (session['user_id'],)).fetchone()
    conn.close()
    if res:
        return jsonify({"status": res[0], "name": res[1], "phone": res[2], "lat": res[3], "lon": res[4]})
    return jsonify({"status": "none"})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
