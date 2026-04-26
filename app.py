import os
import math
import random  # Added for OTP generation
from datetime import timedelta
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId

app = Flask(__name__)
app.secret_key = 'agam_rickshaw_secure_key'
app.permanent_session_lifetime = timedelta(days=30)

# --- 1. MONGODB CONFIG ---
MONGO_URI = os.environ.get('MONGO_URI', "mongodb+srv://agamchugh:agamchugh1234@agam.mn4qkm8.mongodb.net/?appName=agam")

client = MongoClient(MONGO_URI)
db = client['rickshaw_db']
users_coll = db['users']
rides_coll = db['rides']

def get_distance(lat1, lon1, lat2, lon2):
    R = 6371
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))

@app.route('/')
def home():
    if 'user_id' in session: return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        if users_coll.find_one({"email": email}):
            return "Error: User exists. <a href='/login'>Login</a>"
        
        user_data = {
            "username": request.form.get('username'),
            "email": email,
            "mobile": request.form.get('mobile'),
            "password": request.form.get('password'),
            "role": request.form.get('role'),
            "lat": 0, "lon": 0, "is_online": 0
        }
        users_coll.insert_one(user_data)
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = users_coll.find_one({"email": email, "password": password})
        
        if user:
            session.permanent = True
            is_adm = (email == 'agamchugh153@gmail.com')
            session.update({
                'user_id': str(user['_id']), 
                'username': user['username'], 
                'role': user['role'], 
                'is_admin': is_adm
            })
            return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('dashboard.html', username=session['username'], role=session['role'], is_admin=session.get('is_admin'))

@app.route('/update_location', methods=['POST'])
def update_location():
    if 'user_id' not in session: return jsonify({"status": "unauthorized"}), 401
    users_coll.update_one(
        {"_id": ObjectId(session['user_id'])},
        {"$set": {"lat": request.json['latitude'], "lon": request.json['longitude']}}
    )
    return jsonify({"status": "success"})

@app.route('/book_ride', methods=['POST'])
def book_ride():
    user = users_coll.find_one({"_id": ObjectId(session['user_id'])})
    drivers = users_coll.find({"role": "driver", "is_online": 1})
    
    for d in drivers:
        if get_distance(user['lat'], user['lon'], d['lat'], d['lon']) <= 50.0:
            rides_coll.delete_many({"rider_id": session['user_id'], "status": "pending"})
            
            # Generate 4-digit OTP
            otp_code = str(random.randint(1000, 9999))
            
            rides_coll.insert_one({
                "rider_id": session['user_id'],
                "driver_id": str(d['_id']),
                "otp": otp_code,  # Store OTP in DB
                "status": "pending"
            })
            return jsonify({"status": "success"})
    return jsonify({"status": "none"})

@app.route('/get_active_ride')
def get_active_ride():
    uid = session['user_id']
    # Added "started" to the status check
    ride = rides_coll.find_one({
        "$or": [{"rider_id": uid}, {"driver_id": uid}],
        "status": {"$in": ["accepted", "started", "completed"]}
    }, sort=[("_id", -1)])
    
    if ride:
        other_id = ride['driver_id'] if session['role'] == 'rider' else ride['rider_id']
        other_user = users_coll.find_one({"_id": ObjectId(other_id)})
        return jsonify({
            "name": other_user['username'],
            "lat": other_user['lat'],
            "lon": other_user['lon'],
            "status": ride['status'],
            "otp": ride.get('otp') if session['role'] == 'rider' else None # Only rider sees OTP
        })
    return jsonify({"status": "none"})

@app.route('/accept_ride/<string:ride_id>', methods=['POST'])
def accept_ride(ride_id):
    ride = rides_coll.find_one({"_id": ObjectId(ride_id)})
    if ride:
        rides_coll.delete_many({"rider_id": ride['rider_id'], "status": "pending", "_id": {"$ne": ObjectId(ride_id)}})
        rides_coll.update_one({"_id": ObjectId(ride_id)}, {"$set": {"status": "accepted"}})
    return jsonify({"status": "success"})

# NEW ROUTE: Verify OTP to start the trip
@app.route('/verify_ride_otp', methods=['POST'])
def verify_ride_otp():
    if 'user_id' not in session: return jsonify({"success": False}), 401
    data = request.json
    user_otp = data.get('otp')
    
    # Find ride accepted by this driver
    ride = rides_coll.find_one({"driver_id": session['user_id'], "status": "accepted"})
    
    if ride and ride['otp'] == user_otp:
        rides_coll.update_one({"_id": ride['_id']}, {"$set": {"status": "started"}})
        return jsonify({"success": True})
    
    return jsonify({"success": False})

@app.route('/finish_trip', methods=['POST'])
def finish_trip():
    # Only finish if the status was 'started' (OTP was verified)
    rides_coll.update_one(
        {"driver_id": session['user_id'], "status": "started"},
        {"$set": {"status": "completed"}}
    )
    return jsonify({"status": "success"})

@app.route('/clear_completed_ride', methods=['POST'])
def clear_completed_ride():
    rides_coll.delete_many({
        "$or": [{"driver_id": session['user_id']}, {"rider_id": session['user_id']}],
        "status": "completed"
    })
    return
