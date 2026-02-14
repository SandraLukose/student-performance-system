import sqlite3
from flask import Flask, render_template, request, session, redirect, url_for
import matplotlib.pyplot as plt
import io
import base64
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ================= DATABASE =================

def get_db_connection():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        study_hours REAL,
        attendance REAL,
        internal_marks REAL,
        predicted_marks REAL,
        username TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

init_db()

# =====================================================
# ================= PUBLIC ROUTES =====================
# =====================================================

@app.route('/')
def landing():
    return render_template("landing.html")


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                (username, password, 'student')
            )
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except:
            conn.close()
            return render_template("signup.html", error="Username already exists")

    return render_template("signup.html")


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, password)
        )
        user = cursor.fetchone()
        conn.close()

        if user:
            session['username'] = user["username"]
            session['role'] = user["role"]

            if user["role"] == 'admin':
                return redirect(url_for('admin'))
            else:
                return redirect(url_for('dashboard'))
        else:
            return render_template("login.html", error="Invalid credentials")

    return render_template("login.html")


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing'))

# =====================================================
# ================= STUDENT ROUTES ====================
# =====================================================

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template("index.html")


@app.route('/predict', methods=['POST'])
def predict():
    if 'username' not in session:
        return redirect(url_for('login'))

    study_hours = float(request.form['study_hours'])
    attendance = float(request.form['attendance'])
    internal_marks = float(request.form['internal_marks'])

    predicted_value = (
        (study_hours * 3) +
        (attendance * 0.3) +
        (internal_marks * 2)
    )

    predicted_value = max(0, min(100, predicted_value))

    # Performance
    if predicted_value >= 80:
        status = "Excellent"
        status_color = "excellent"
    elif predicted_value >= 60:
        status = "Good"
        status_color = "good"
    else:
        status = "Needs Improvement"
        status_color = "poor"

    # Suggestions
    suggestions = []
    if attendance < 60:
        suggestions.append("Improve attendance to increase your score.")
    if internal_marks < 10:
        suggestions.append("Focus more on internal assessments.")
    if study_hours < 3:
        suggestions.append("Increase daily study time for better results.")
    if predicted_value >= 80:
        suggestions.append("Keep up the excellent work!")

    # Grade
    if predicted_value >= 90:
        grade = "A+"
    elif predicted_value >= 80:
        grade = "A"
    elif predicted_value >= 70:
        grade = "B"
    elif predicted_value >= 60:
        grade = "C"
    else:
        grade = "D"

    # Risk
    risk = "Low"
    if attendance < 40 and internal_marks < 8:
        risk = "High"
    elif attendance < 60 or internal_marks < 10:
        risk = "Medium"

    # Save to DB
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO predictions
        (study_hours, attendance, internal_marks, predicted_marks, username)
        VALUES (?, ?, ?, ?, ?)
    """, (
        study_hours,
        attendance,
        internal_marks,
        predicted_value,
        session['username']
    ))
    conn.commit()
    conn.close()

    return render_template(
        "index.html",
        predicted_value=round(predicted_value, 2),
        status=status,
        status_color=status_color,
        suggestions=suggestions,
        grade=grade,
        risk=risk
    )


@app.route('/history')
def history():
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT predicted_marks, created_at
        FROM predictions
        WHERE username=?
        ORDER BY created_at ASC
    """, (session['username'],))

    history_data = cursor.fetchall()
    conn.close()

    scores = [float(row["predicted_marks"]) for row in history_data]
    dates = [str(row["created_at"]) for row in history_data]

    return render_template(
        "history.html",
        history_data=history_data,
        scores=scores,
        dates=dates
    )

# =====================================================
# ================= ADMIN ROUTES ======================
# =====================================================

@app.route('/admin')
def admin():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM predictions ORDER BY created_at DESC")
    records = cursor.fetchall()

    cursor.execute("SELECT study_hours, predicted_marks FROM predictions")
    data = cursor.fetchall()

    graph_url = None
    avg_marks = 0

    if data:
        study_hours = [row["study_hours"] for row in data]
        predicted_marks = [row["predicted_marks"] for row in data]
        avg_marks = sum(predicted_marks) / len(predicted_marks)

        plt.figure()
        plt.scatter(study_hours, predicted_marks)
        plt.xlabel("Study Hours")
        plt.ylabel("Predicted Marks")
        plt.title("Study Hours vs Predicted Marks")

        img = io.BytesIO()
        plt.savefig(img, format='png')
        img.seek(0)
        graph_url = base64.b64encode(img.getvalue()).decode()
        plt.close()

    conn.close()

    return render_template(
        "admin.html",
        records=records,
        graph_url=graph_url,
        avg_marks=round(avg_marks, 2)
    )

# =====================================================
# ================= RUN APP ===========================
# =====================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
