import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = 'supersecretkey_agam'

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    # Updated to include username and mobile
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            email TEXT NOT NULL UNIQUE,
            mobile TEXT,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- ROUTES ---

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        mobile = request.form.get('mobile')
        password = request.form.get('password')
        
        try:
            conn = sqlite3.connect('users.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (username, email, mobile, password) 
                VALUES (?, ?, ?, ?)
            ''', (username, email, mobile, password))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return "Email already exists! <a href='/signup'>Try again</a>"
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE email = ? AND password = ?', (email, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['user_id'] = user[0]
            session['email'] = user[2] # Email is the 3rd column now
            
            # ADMIN CHECK for agamchugh153@gmail.com
            if user[2] == 'agamchugh153@gmail.com':
                session['is_admin'] = True
            else:
                session['is_admin'] = False
                
            return redirect(url_for('dashboard'))
        else:
            return "Invalid Credentials! <a href='/login'>Try again</a>"
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'email' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', 
                           email=session['email'], 
                           is_admin=session.get('is_admin'))

@app.route('/admin')
def admin():
    # Security: Only your email can enter
    if 'email' not in session or session.get('email') != 'agamchugh153@gmail.com':
        return "Access Denied! Only Agam can see this."
    
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, email, mobile FROM users')
    users = cursor.fetchall()
    conn.close()
    return render_template('admin.html', users=users)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))
@app.route('/delete/<int:id>')
def delete_user(id):
    # Security: Only Agam can delete users
    if 'email' not in session or session.get('email') != 'agamchugh153@gmail.com':
        return "Access Denied!"
    
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM users WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    
    # After deleting, send the admin back to the list
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(debug=True)

