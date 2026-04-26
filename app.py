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

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('dashboard.html', username=session['username'], role=session['role'], is_admin=session.get('is_admin'))

@app.route('/update_location', methods=['POST'])
def update_location():
    data = request.json
    users_coll.update_one(
        {"_id": ObjectId(session['user_id'])},
        {"$set": {"lat": data['latitude'], "lon": data['longitude']}}
    )
    return jsonify({"status": "success"})

@app.route('/book_ride', methods=['POST'])
def book_ride():
    # 1. Find any online driver
    driver = users_coll.find_one({"role": "driver", "is_online": True})
    
    if not driver:
        return jsonify({"status": "no_drivers", "message": "No drivers are online right now!"})

    # 2. Check if a ride already exists to prevent duplicates
    existing = rides_coll.find_one({"rider_id": session['user_id'], "status": {"$in": ["accepted", "started"]}})
    if existing:
        return jsonify({"status": "success", "message": "Ride already active"})

    # 3. Create the ride
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
    uid = session['user_id']
    role = session['role']
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

@app.route('/toggle_status', methods=['POST'])
def toggle_status():
    user = users_coll.find_one({"_id": ObjectId(session['user_id'])})
    new_status = not user.get('is_online', False)
    users_coll.update_one({"_id": ObjectId(session['user_id'])}, {"$set": {"is_online": new_status}})
    return jsonify({"is_online": new_status})

@app.route('/verify_ride_otp', methods=['POST'])
def verify_otp():
    otp = str(request.json.get('otp')).strip()
    ride = rides_coll.find_one({"driver_id": session['user_id'], "status": "accepted", "otp": otp})
    if ride:
        rides_coll.update_one({"_id": ride['_id']}, {"$set": {"status": "started"}})
        return jsonify({"success": True})
    return jsonify({"success": False})

@app.route('/cancel_ride', methods=['POST'])
def cancel():
    rides_coll.delete_many({"$or": [{"rider_id": session['user_id']}, {"driver_id": session['user_id']}], "status": "accepted"})
    return jsonify({"status": "success"})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
