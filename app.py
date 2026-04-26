import os
import sqlite3
import math
from flask import Flask, render_template, request, redirect, url_for, session, jsonify

app = Flask(__name__)
app.secret_key = 'supersecretkey_agam'

def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    # Main User Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT, email TEXT NOT NULL UNIQUE,
            mobile TEXT, password TEXT NOT NULL,
            role TEXT DEFAULT 'rider', lat REAL DEFAULT 0, lon REAL DEFAULT 0, is_online BOOLEAN DEFAULT 0
        )
    ''')
    # New Table for Rides
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rider_id INTEGER, driver_id INTEGER,
            status TEXT DEFAULT 'pending' -- pending, accepted, declined
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Math to find distance between two GPS points
def get_distance(lat1, lon1, lat2, lon2):
    radius = 6371 # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c

@app.route('/book_ride', methods=['POST'])
def book_ride():
    rider_id = session.get('user_id')
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    # Get Rider Location
    cursor.execute('SELECT lat, lon FROM users WHERE id = ?', (rider_id,))
    r_lat, r_lon = cursor.fetchone()
    
    # Find nearest online driver
    cursor.execute('SELECT id, lat, lon FROM users WHERE role = "driver" AND is_online = 1')
    drivers = cursor.fetchall()
    
    best_driver = None
    min_dist = 1.5 # 1.5km limit
    
    for d_id, d_lat, d_lon in drivers:
        dist = get_distance(r_lat, r_lon, d_lat, d_lon)
        if dist < min_dist:
            min_dist = dist
            best_driver = d_id
            
    if best_driver:
        cursor.execute('INSERT INTO rides (rider_id, driver_id) VALUES (?, ?)', (rider_id, best_driver))
        conn.commit()
        conn.close()
        return jsonify({"status": "searching", "message": "Request sent to nearest driver!"})
    
    conn.close()
    return jsonify({"status": "error", "message": "No drivers within 1.5km!"})

@app.route('/check_requests')
def check_requests():
    driver_id = session.get('user_id')
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT rides.id, users.username FROM rides JOIN users ON rides.rider_id = users.id WHERE driver_id = ? AND status = "pending"', (driver_id,))
    request = cursor.fetchone()
    conn.close()
    if request:
        return jsonify({"ride_id": request[0], "rider_name": request[1]})
    return jsonify({"ride_id": None})

# ... (Keep your existing login, signup, and dashboard routes here) ...
