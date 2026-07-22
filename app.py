import os
import math
import random
from datetime import timedelta
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId

app = Flask(__name__)
app.secret_key = 'agam_master_key_778899'
app.permanent_session_lifetime = timedelta(days=30)

# --- MONGODB CONFIG ---
MONGO_URI = "mongodb+srv://agamchugh:agamchugh1234@agam.mn4qkm8.mongodb.net/?appName=agam"
client = MongoClient(MONGO_URI)
db = client['rickshaw_db']
users_coll = db['users']
rides_coll = db['rides']

@app.route('/')
def home():
    if 'user_id' in session: return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = users_coll.find_one({"email": email, "password": password})
        if user:
            session.permanent = True
            is_adm = (email == 'agamchugh153@gmail.com')
            session.update({'user_id': str(user['_id']), 'username': user['username'], 'role': user['role'], 'is_admin': is_adm})
            return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))
    @app.route('/signup', methods=['GET', 'POST'])
def signup():

    if request.method == 'POST':
        role = request.form.get('role')
        username = request.form.get('username')
        email = request.form.get('email')
        mobile = request.form.get('mobile')
        password = request.form.get('password')

        # Check if email already exists
        existing = users_coll.find_one({"email": email})
        if existing:
            return "Email already registered."

        users_coll.insert_one({
            "role": role,
            "username": username,
            "email": email,
            "mobile": mobile,
            "password": password,
            "lat": None,
            "lon": None,
            "is_online": False
        })

        return redirect(url_for('login'))

    return render_template("signup.html")

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('dashboard.html', username=session['username'], role=session['role'], is_admin=session.get('is_admin'))

@app.route('/update_location', methods=['POST'])
def update_location():
    data = request.json
    users_coll.update_one(
        {"_id": ObjectId(session['user_id'])},
        {"$set": {"lat": data['latitude'], "lon": data['longitude'], "is_online": data.get('online', False)}}
    )
    return jsonify({"status": "success"})

@app.route('/book_ride', methods=['POST'])
def book_ride():
    driver = users_coll.find_one({"role": "driver", "is_online": True})
    if not driver:
        return jsonify({"status": "no_drivers"})
    otp = str(random.randint(1000, 9999))
    rides_coll.insert_one({
        "rider_id": session['user_id'],
        "driver_id": str(driver['_id']),
        "otp": otp,
        "status": "accepted"
    })
    return jsonify({"status": "success"})

@app.route('/get_active_ride')
def get_active_ride():
    uid = session.get('user_id')
    role = session.get('role')
    if not uid: return jsonify({"status": "none"})
    query = {"rider_id": uid} if role == "rider" else {"driver_id": uid}
    ride = rides_coll.find_one({**query, "status": {"$in": ["accepted", "started"]}}, sort=[("_id", -1)])
    if ride:
        other_id = ride['driver_id'] if role == 'rider' else ride['rider_id']
        other = users_coll.find_one({"_id": ObjectId(other_id)})
        return jsonify({
            "status": ride['status'],
            "name": other['username'] if other else "Partner",
            "otp": ride['otp'],
            "lat": other.get('lat') if other else None,
            "lon": other.get('lon') if other else None
        })
    return jsonify({"status": "none"})

@app.route('/verify_ride_otp', methods=['POST'])
def verify_otp():
    otp = str(request.json.get('otp')).strip()
    ride = rides_coll.find_one({"driver_id": session['user_id'], "status": "accepted", "otp": otp})
    if ride:
        rides_coll.update_one({"_id": ride['_id']}, {"$set": {"status": "started"}})
        return jsonify({"success": True})
    return jsonify({"success": False})

@app.route('/complete_ride', methods=['POST'])
def complete():
    rides_coll.update_many({"driver_id": session['user_id'], "status": "started"}, {"$set": {"status": "completed"}})
    return jsonify({"status": "success"})

@app.route('/cancel_ride', methods=['POST'])
def cancel():
    rides_coll.delete_many({"rider_id": session['user_id'], "status": "accepted"})
    return jsonify({"status": "success"})

@app.route('/admin_reset', methods=['POST'])
def admin_reset():
    if not session.get('is_admin'): return jsonify({"success": False})
    rides_coll.delete_many({})
    return jsonify({"success": True})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
