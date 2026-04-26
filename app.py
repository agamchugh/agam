import os
import math
import random 
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
                "otp": otp_code, 
                "status": "pending"
            })
            return jsonify({"status": "success"})
    return jsonify({"status": "none"})

@app.route('/get_active_ride')
def get_active_ride():
    if 'user_id' not in session: return jsonify({"status": "none"})
    uid = session['user_id']
    
    # Check for any ride that isn't pending (Accepted, Started, or Completed)
    ride = rides_coll.find_one({
        "$or": [{"rider_id": uid}, {"driver_id": uid}],
        "status": {"$in": ["accepted", "started", "completed"]}
    }, sort=[("_id", -1)])
    
    if ride:
        other_role = 'driver' if session['role'] == 'rider' else 'rider'
        other_id = ride['driver_id'] if session['role'] == 'rider' else ride['rider_id']
        other_user = users_coll.find_one({"_id": ObjectId(other_id)})
        
        return jsonify({
            "name": other_user['username'] if other_user else "Unknown",
            "lat": other_user['lat'] if other_user else 0,
            "lon": other_user['lon'] if other_user else 0,
            "status": ride['status'],
            "otp": ride.get('otp') if session['role'] == 'rider' else None # Rider gets the OTP to show
        })
    return jsonify({"status": "none"})

@app.route('/accept_ride/<string:ride_id>', methods=['POST'])
def accept_ride(ride_id):
    ride = rides_coll.find_one({"_id": ObjectId(ride_id)})
    if ride:
        # Clear other potential pending requests for this specific rider
        rides_coll.delete_many({"rider_id": ride['rider_id'], "status": "pending", "_id": {"$ne": ObjectId(ride_id)}})
        # Set status to accepted so the dashboards update
        rides_coll.update_one({"_id": ObjectId(ride_id)}, {"$set": {"status": "accepted"}})
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 404

@app.route('/verify_ride_otp', methods=['POST'])
def verify_ride_otp():
    if 'user_id' not in session: return jsonify({"success": False}), 401
    data = request.json
    user_otp = data.get('otp')
    
    # Driver verifying the OTP for the ride they accepted
    ride = rides_coll.find_one({"driver_id": session['user_id'], "status": "accepted"})
    
    if ride and ride.get('otp') == str(user_otp):
        rides_coll.update_one({"_id": ride['_id']}, {"$set": {"status": "started"}})
        return jsonify({"success": True})
    
    return jsonify({"success": False, "message": "Invalid OTP"})

@app.route('/finish_trip', methods=['POST'])
def finish_trip():
    # Only allow finishing if the trip was actually started via OTP
    res = rides_coll.update_one(
        {"driver_id": session['user_id'], "status": "started"},
        {"$set": {"status": "completed"}}
    )
    if res.modified_count > 0:
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Trip not started or already finished"})

@app.route('/clear_completed_ride', methods=['POST'])
def clear_completed_ride():
    rides_coll.delete_many({
        "$or": [{"driver_id": session['user_id']}, {"rider_id": session['user_id']}],
        "status": "completed"
    })
    return jsonify({"status": "success"})

@app.route('/check_requests')
def check_requests():
    res = rides_coll.find_one({"driver_id": session['user_id'], "status": "pending"})
    if res:
        rider = users_coll.find_one({"_id": ObjectId(res['rider_id'])})
        return jsonify({"ride_id": str(res['_id']), "rider_name": rider['username'] if rider else "Rider"})
    return jsonify({"ride_id": None})

@app.route('/toggle_status', methods=['POST'])
def toggle_status():
    user = users_coll.find_one({"_id": ObjectId(session['user_id'])})
    new_val = 1 if user.get('is_online') == 0 else 0
    users_coll.update_one({"_id": ObjectId(session['user_id'])}, {"$set": {"is_online": new_val}})
    return jsonify({"is_online": new_val})

@app.route('/admin_panel')
def admin_panel():
    if not session.get('is_admin'): return redirect(url_for('login'))
    all_users = list(users_coll.find())
    for u in all_users: u['id'] = str(u['_id'])
    
    all_rides = []
    for r in rides_coll.find().sort("_id", -1):
        rdr = users_coll.find_one({"_id": ObjectId(r['rider_id'])})
        drv = users_coll.find_one({"_id": ObjectId(r['driver_id'])})
        all_rides.append({
            "id": str(r['_id']),
            "rider": rdr['username'] if rdr else "Deleted User",
            "driver": drv['username'] if drv else "Deleted User",
            "status": r['status']
        })
    return render_template('admin.html', all_users=all_users, all_rides=all_rides)

@app.route('/logout')
def logout(): 
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug
