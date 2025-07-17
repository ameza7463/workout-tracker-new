from flask import Flask, render_template, request, redirect, session
import psycopg2
import json
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# --- Connect to Postgres ---
def get_db_connection():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        raise Exception("❗ DATABASE_URL environment variable not set ❗")
    print("✅ Using DATABASE_URL:", db_url)
    return psycopg2.connect(db_url)

# --- Initialize Tables ---
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE,
            password TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS workouts (
            id SERIAL PRIMARY KEY,
            user_email TEXT,
            date TEXT,
            notes TEXT,
            exercises JSONB
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

# --- Routes ---
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT * FROM users WHERE email = %s AND password = %s', (email, password))
        user = cur.fetchone()
        cur.close()
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

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('INSERT INTO users (email, password) VALUES (%s, %s) ON CONFLICT (email) DO NOTHING', (email, password))
    conn.commit()
    cur.close()
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

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('INSERT INTO workouts (user_email, date, notes, exercises) VALUES (%s, %s, %s, %s)',
                    (user, date, notes, json.dumps(exercise_data)))
        conn.commit()
        cur.close()
        conn.close()

        return redirect('/dashboard')

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT id, date, notes, exercises FROM workouts WHERE user_email = %s ORDER BY date DESC', (user,))
    workouts = cur.fetchall()
    cur.close()
    conn.close()

    workout_list = []
    for w in workouts:
        workout_list.append({
            'id': w[0],
            'date': w[1],
            'notes': w[2],
            'exercises': w[3]
        })

    now = datetime.now().strftime('%Y-%m-%d')
    return render_template('dashboard.html', user=user, workouts=workout_list, now=now)

@app.route('/delete/<int:workout_id>')
def delete_workout(workout_id):
    if 'user' not in session:
        return redirect('/')

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM workouts WHERE id = %s', (workout_id,))
    conn.commit()
    cur.close()
    conn.close()

    return redirect('/dashboard')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')

# --- Initialize DB on App Start ---
init_db()








    
