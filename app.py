from flask import Flask, render_template, request, redirect, session
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "secret123"

# Your Master Admin Email
MY_ADMIN_EMAIL = "agamchugh153@gmail.com"

# Helper function to handle DB connections
def get_db_connection():
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row 
    return conn

# ================= DATABASE INIT =================
def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            phone TEXT,
            password TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ================= ROUTES =================

@app.route('/')
def home():
    return render_template('login.html')

@app.route('/signup')
def signup():
    return render_template('signup.html')

@app.route('/register', methods=['POST'])
def register():
    data = request.form
    hashed_password = generate_password_hash(data['password'])
    
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO users (name, email, phone, password) VALUES (?, ?, ?, ?)",
            (data['name'], data['email'], data['phone'], hashed_password)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        return "User with this email already exists!"
    finally:
        conn.close()
        
    return redirect('/')

@app.route('/login', methods=['POST'])
def login():
    data = request.form
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE email=?", (data['email'],)).fetchone()
    conn.close()

    if user and check_password_hash(user['password'], data['password']):
        # Storing both name and email in session
        session['user'] = user['name']
        session['email'] = user['email'] 
        return redirect('/dashboard')

    return "Invalid Login Credentials"

@app.route('/dashboard')
def dashboard():
    if 'user' in session:
        return render_template('dashboard.html', name=session['user'])
    return redirect('/')

@app.route('/logout')
def logout():
    session.clear() # Clears the whole session for safety
    return redirect('/')

# ================= ADMIN PANEL (PROTECTED) =================

@app.route('/admin')
def admin():
    # 🛡️ THE MASTER LOCK: Only agamchugh153@gmail.com can pass
    if session.get('email') != MY_ADMIN_EMAIL:
        return "<h1>403 Forbidden</h1><p>Access Denied. This area is reserved for the Master Admin.</p>", 403

    conn = get_db_connection()
    users = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return render_template('admin.html', users=users)


@app.route('/delete/<int:id>')
def delete(id):
    # 🛡️ PROTECT ACTION: Prevent URL hacking
    if session.get('email') != MY_ADMIN_EMAIL:
        return "Unauthorized Action", 403

    conn = get_db_connection()
    conn.execute("DELETE FROM users WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect('/admin')

@app.route('/edit/<int:id>')
def edit(id):
    if session.get('email') != MY_ADMIN_EMAIL:
        return "Unauthorized", 403

    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id=?", (id,)).fetchone()
    conn.close()
    return render_template('edit.html', user=user)

@app.route('/update/<int:id>', methods=['POST'])
def update(id):
    if session.get('email') != MY_ADMIN_EMAIL:
        return "Unauthorized", 403

    data = request.form
    hashed_pw = generate_password_hash(data['password'])
    
    conn = get_db_connection()
    conn.execute("""
        UPDATE users
        SET name=?, email=?, phone=?, password=?
        WHERE id=?
    """, (data['name'], data['email'], data['phone'], hashed_pw, id))
    conn.commit()
    conn.close()
    return redirect('/admin')

# ================= RUN APP =================
if __name__ == "__main__":
    app.run(debug=True)