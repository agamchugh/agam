import os
import math
import random 
from datetime import timedelta
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'agam_master_key_778899')
app.permanent_session_lifetime = timedelta(days=30)

# --- MONGODB CONFIG ---
MONGO_URI = os.environ.get('MONGO_URI', "mongodb+srv://agamchugh:agamchugh1234@agam.mn4qkm8.mongodb.net/?appName=agam")
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
    return render_template('dashboard.html', username=session['username'], role=session['role'])

@app.route('/get_active_ride')
def get_active_ride():
    if 'user_id' not in session: return jsonify({"status": "none"})
    uid = session['user_id']
    role = session['role']
    query = {"rider_id": uid} if role == "rider" else {"driver_id": uid}
    ride = rides_coll.find_one({**query, "status": {"$in": ["pending", "accepted", "started"]}}, sort=[("_id", -1)])
    
    if ride:
        other_id = ride['driver_id'] if role == 'rider' else ride['rider_id']
        other_user = users_coll.find_one({"_id": ObjectId(other_id)}) if other_id else None
        return jsonify({
            "status": ride['status'],
            "name": other_user['username'] if other_user else "Searching...",
            "otp": str(ride.get('otp')).strip() if role == 'rider' else None,
            "lat": other_user.get('lat') if other_user else None,
            "lon": other_user.get('lon') if other_user else None
        })
    return jsonify({"status": "none"})

@app.route('/verify_ride_otp', methods=['POST'])
def verify_ride_otp():
    entered_otp = str(request.json.get('otp', '')).strip()
    ride = rides_coll.find_one({"driver_id": session['user_id'], "status": "accepted"})
    if ride and str(ride.get('otp')).strip() == entered_otp:
        rides_coll.update_one({"_id": ride['_id']}, {"$set": {"status": "started"}})
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Wrong OTP!"})

@app.route('/update_location', methods=['POST'])
def update_location():
    data = request.json
    users_coll.update_one({"_id": ObjectId(session['user_id'])}, {"$set": {"lat": data['latitude'], "lon": data['longitude']}})
    return jsonify({"status": "ok"})

@app.route('/cancel_ride', methods=['POST'])
def cancel_ride():
    rides_coll.delete_many({"$or": [{"rider_id": session['user_id']}, {"driver_id": session['user_id']}], "status": {"$in": ["pending", "accepted"]}})
    return jsonify({"status": "success"})

@app.route('/finish_trip', methods=['POST'])
def finish_trip():
    rides_coll.update_one({"driver_id": session['user_id'], "status": "started"}, {"$set": {"status": "completed"}})
    return jsonify({"status": "success"})

if __name__ == '__main__':
    app.run(debug=True)
