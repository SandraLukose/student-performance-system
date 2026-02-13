import mysql.connector
from flask import Flask, render_template, request, session, redirect, url_for
import matplotlib.pyplot as plt
import io
import base64

# ---------------- FLASK APP ----------------
app = Flask(__name__)
app.secret_key = "supersecretkey"

# ---------------- DATABASE CONNECTION ----------------
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="windows",
    database="student_prediction_db"
)

cursor = db.cursor()

# =====================================================
# ================= PUBLIC ROUTES =====================
# =====================================================

# -------- Landing Page --------
@app.route('/')
def landing():
    return render_template("landing.html")


# -------- Signup --------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        try:
            cursor.execute(
                "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
                (username, password, 'student')
            )
            db.commit()
            return redirect(url_for('login'))
        except:
            return render_template("signup.html", error="Username already exists")

    return render_template("signup.html")


# -------- Login --------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cursor.execute(
            "SELECT * FROM users WHERE username=%s AND password=%s",
            (username, password)
        )
        user = cursor.fetchone()

        if user:
            session['username'] = user[1]
            session['role'] = user[3]

            # Role-based redirect
            if user[3] == 'admin':
                return redirect(url_for('admin'))
            else:
                return redirect(url_for('dashboard'))
        else:
            return render_template("login.html", error="Invalid credentials")

    return render_template("login.html")


# -------- Logout --------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing'))


# =====================================================
# ================= STUDENT ROUTES ====================
# =====================================================

# -------- Student Dashboard --------
@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))

    return render_template("index.html")


# -------- Predict --------
@app.route('/predict', methods=['POST'])
def predict():
    if 'username' not in session:
        return redirect(url_for('login'))

    study_hours = float(request.form['study_hours'])
    attendance = float(request.form['attendance'])
    internal_marks = float(request.form['internal_marks'])

    # -------- Controlled Weighted Formula --------
    predicted_value = (
        (study_hours * 3) +
        (attendance * 0.3) +
        (internal_marks * 2)
    )

    # Clamp between 0 and 100
    predicted_value = max(0, min(100, predicted_value))
# -------- PERFORMANCE STATUS --------
    if predicted_value >= 80:
        status = "Excellent"
        status_color = "excellent"
    elif predicted_value >= 60:
        status = "Good"
        status_color = "good"
    else:
        status = "Needs Improvement"
        status_color = "poor"
    suggestions = []

    if attendance < 60:
        suggestions.append("Improve attendance to increase your score.")

    if internal_marks < 10:
        suggestions.append("Focus more on internal assessments.")

    if study_hours < 3:
        suggestions.append("Increase daily study time for better results.")    
    if predicted_value >= 80:
        suggestions.append("Keep up the excellent work!")
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
    risk = "Low"
    if attendance < 40 and internal_marks < 8:
        risk = "High"
    elif attendance < 60 or internal_marks < 10:
        risk = "Medium"

    # Save to database
    sql = """
        INSERT INTO predictions
        (study_hours, attendance, internal_marks, predicted_marks, username)
        VALUES (%s, %s, %s, %s, %s)
    """
    values = (
    study_hours,
    attendance,
    internal_marks,
    predicted_value,
    session['username']   # ✅ storing logged-in student
)

    cursor.execute(sql, values)
    db.commit()

    return render_template(
        "index.html",
        predicted_value=round(predicted_value, 2),
        status=status,
        status_color=status_color,
        suggestions=suggestions,   # ✅ PASSING TO HTML
        grade=grade,
        risk=risk
        )
# -------- Student History --------
@app.route('/history')
def history():
    if 'username' not in session:
        return redirect(url_for('login'))

    cursor.execute(
        "SELECT predicted_marks, created_at FROM predictions WHERE username=%s ORDER BY created_at ASC",
        (session['username'],)
    )

    history_data = cursor.fetchall()

    # Prepare lists separately
    scores = [float(row[0]) for row in history_data]
    dates = [str(row[1]) for row in history_data]

    return render_template(
    "history.html",
    history_data=history_data,
    scores=scores,
    dates=dates
)





# =====================================================
# ================= ADMIN ROUTES ======================
# =====================================================

# -------- Admin Dashboard --------
# -------- Admin Dashboard --------
@app.route('/admin')
def admin():
    if 'role' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    # ================= GET TABLE DATA =================
    cursor.execute("SELECT * FROM predictions ORDER BY created_at DESC")
    records = cursor.fetchall()

    # ================= STUDY HOURS vs MARKS =================
    cursor.execute("SELECT study_hours, predicted_marks FROM predictions")
    data = cursor.fetchall()

    graph_url = None
    attendance_graph = None
    avg_marks = 0

    if data:
        study_hours = [row[0] for row in data]
        predicted_marks = [row[1] for row in data]

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

    # ================= ATTENDANCE vs PERFORMANCE =================
    cursor.execute("SELECT attendance, predicted_marks FROM predictions")
    attendance_data = cursor.fetchall()

    if attendance_data:
        low = 0
        medium = 0
        high = 0

        for att, marks in attendance_data:
            if att < 50:
                low += 1
            elif att < 75:
                medium += 1
            else:
                high += 1

        plt.figure()
        plt.bar(["<50%", "50-74%", "75%+"], [low, medium, high])
        plt.xlabel("Attendance Range")
        plt.ylabel("Number of Students")
        plt.title("Attendance vs Performance Distribution")

        img2 = io.BytesIO()
        plt.savefig(img2, format='png')
        img2.seek(0)
        attendance_graph = base64.b64encode(img2.getvalue()).decode()
        plt.close()

    # ================= PERFORMANCE TREND OVER TIME =================
    cursor.execute("""
    SELECT DATE(created_at), AVG(predicted_marks)
    FROM predictions
    GROUP BY DATE(created_at)
    ORDER BY DATE(created_at)""")
    trend_data = cursor.fetchall()
    trend_graph = None
    if trend_data:
        dates = [str(row[0]) for row in trend_data]
        avg_scores = [float(row[1]) for row in trend_data]
        plt.figure()
        plt.plot(dates, avg_scores, marker='o')
        plt.xlabel("Date")
        plt.ylabel("Average Predicted Marks")
        plt.title("Performance Trend Over Time")
        plt.xticks(rotation=45)
        img3 = io.BytesIO()
        plt.tight_layout()
        plt.savefig(img3, format='png')
        img3.seek(0)

        trend_graph = base64.b64encode(img3.getvalue()).decode()
        plt.close()
    # ================= INTERNAL MARKS IMPACT =================
    cursor.execute("SELECT internal_marks, predicted_marks FROM predictions")
    internal_data = cursor.fetchall()
    internal_graph = None
    if internal_data:
        groups = {
            "0-5": [],
            "6-10": [],
            "11-15": [],
            "16-20": []
        }
    for internal, marks in internal_data:
        if internal <= 5:
            groups["0-5"].append(marks)
        elif internal <= 10:
            groups["6-10"].append(marks)
        elif internal <= 15:
            groups["11-15"].append(marks)
        else:
            groups["16-20"].append(marks)
    avg_values = []
    for key in groups:
        if groups[key]:
            avg_values.append(sum(groups[key]) / len(groups[key]))
        else:
            avg_values.append(0)
    plt.figure()
    plt.bar(groups.keys(), avg_values)
    plt.xlabel("Internal Marks Range")
    plt.ylabel("Average Predicted Marks")
    plt.title("Internal Marks Impact")
    img4 = io.BytesIO()
    plt.savefig(img4, format='png')
    img4.seek(0)
    internal_graph = base64.b64encode(img4.getvalue()).decode()
    plt.close()
        # ================= PERFORMANCE PIE CHART =================
    cursor.execute("SELECT predicted_marks FROM predictions")
    marks_data = cursor.fetchall()
    pie_graph = None

    if marks_data:
        excellent = 0
        good = 0
        low = 0
    for (marks,) in marks_data:
        if marks >= 80:
            excellent += 1
        elif marks >= 60:
            good += 1
        else:
            low += 1
    plt.figure()
    plt.pie(
        [excellent, good, low],
        labels=["Excellent", "Good", "Needs Improvement"],
        autopct='%1.1f%%'
    )
    plt.title("Performance Distribution")

    img5 = io.BytesIO()
    plt.savefig(img5, format='png')
    img5.seek(0)

    pie_graph = base64.b64encode(img5.getvalue()).decode()
    plt.close()
# ================= HEATMAP =================
    cursor.execute("SELECT study_hours, attendance FROM predictions")
    heat_data = cursor.fetchall()

    heat_graph = None

    if heat_data:
        study_vals = [row[0] for row in heat_data]
        attendance_vals = [row[1] for row in heat_data]

        plt.figure()
        plt.hist2d(study_vals, attendance_vals, bins=5)
        plt.colorbar(label="Number of Students")
        plt.xlabel("Study Hours")
        plt.ylabel("Attendance")
        plt.title("Study Hours vs Attendance Heatmap")

        img6 = io.BytesIO()
        plt.savefig(img6, format='png')
        img6.seek(0)

        heat_graph = base64.b64encode(img6.getvalue()).decode()
        plt.close()

    return render_template(
    "admin.html",
    records=records,
    graph_url=graph_url,
    attendance_graph=attendance_graph,
    trend_graph=trend_graph,
    internal_graph=internal_graph,
    pie_graph=pie_graph,
    heat_graph=heat_graph,
    avg_marks=round(avg_marks, 2)
)


# =====================================================
# ================= RUN APP ===========================
# =====================================================

if __name__ == "__main__":
    app.run(debug=True, port=8081)
