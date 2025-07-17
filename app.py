from flask import Flask, render_template, request, redirect, session
import sqlite3
import json
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# --- User DB Init ---
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT, password TEXT)''')
    conn.commit()
    conn.close()

# --- Workout DB Init ---
def init_workout_db():
    conn = sqlite3.connect('workouts.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            date TEXT,
            notes TEXT,
            exercises TEXT
        )
    ''')
    conn.commit()
    conn.close()

# --- Routes ---

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE email=? AND password=?', (email, password))
        user = c.fetchone()
        conn.close()

        if user:
            session['user'] = email
            return redirect('/dashboard')
        else:
            return 'Invalid Credentials'

    return render_template('login.html')

@app.route('/signup', methods=['POST'])
def signup():
    email = request.form['email']
    password = request.form['password']

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('INSERT INTO users (email, password) VALUES (?, ?)', (email, password))
    conn.commit()
    conn.close()

    return redirect('/')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user' not in session:
        return redirect('/')

    user = session['user']

    if request.method == 'POST':
        date = request.form['date']
        notes = request.form['notes']
        exercises = request.form.getlist('exercise')
        sets = request.form.getlist('sets')
        reps = request.form.getlist('reps')
        weight = request.form.getlist('weight')

        exercise_data = []
        for i in range(len(exercises)):
            exercise_data.append({
                "Exercise": exercises[i],
                "Sets": sets[i],
                "Reps": reps[i],
                "Weight": weight[i]
            })

        conn = sqlite3.connect('workouts.db')
        c = conn.cursor()
        c.execute('INSERT INTO workouts (user_email, date, notes, exercises) VALUES (?, ?, ?, ?)',
                  (user, date, notes, json.dumps(exercise_data)))
        conn.commit()
        conn.close()

        return redirect('/dashboard')

    # Load workouts
    conn = sqlite3.connect('workouts.db')
    c = conn.cursor()
    c.execute('SELECT * FROM workouts WHERE user_email=? ORDER BY date DESC', (user,))
    workouts = c.fetchall()
    conn.close()

    workout_list = []
    for w in workouts:
        workout_list.append({
            'id': w[0],
            'date': w[2],
            'notes': w[3],
            'exercises': json.loads(w[4])
        })

    now = datetime.now().strftime('%Y-%m-%d')
    return render_template('dashboard.html', user=user, workouts=workout_list, now=now)

@app.route('/delete/<int:workout_id>')
def delete_workout(workout_id):
    if 'user' not in session:
        return redirect('/')

    conn = sqlite3.connect('workouts.db')
    c = conn.cursor()
    c.execute('DELETE FROM workouts WHERE id=?', (workout_id,))
    conn.commit()
    conn.close()

    return redirect('/dashboard')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')

# --- Run ---
if __name__ == '__main__':
    init_db()
    init_workout_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)





    
