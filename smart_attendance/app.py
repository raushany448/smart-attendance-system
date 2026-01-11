from flask import Flask, render_template, request, redirect, session
import mysql.connector
import qrcode
from datetime import datetime, timedelta
import os
from threading import Timer

app = Flask(__name__)
app.secret_key = "secret123"

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",
    database="attendance_db"
)
cursor = db.cursor()

QR_FOLDER = "static/qr"
os.makedirs(QR_FOLDER, exist_ok=True)

# ------------------ ADMIN LOGIN ------------------
@app.route("/", methods=["GET","POST"])
def admin_login():
    if request.method=="POST":
        u = request.form["username"]
        p = request.form["password"]
        cursor.execute("SELECT * FROM admin WHERE username=%s AND password=%s", (u,p))
        if cursor.fetchone():
            session["admin"] = u
            return redirect("/dashboard")
    return render_template("admin_login.html")

@app.route("/logout")
def admin_logout():
    session.clear()
    return redirect("/")

# ------------------ TEACHER LOGIN ------------------
@app.route("/teacher_login", methods=["GET","POST"])
def teacher_login():
    if request.method=="POST":
        u = request.form["username"]
        p = request.form["password"]
        cursor.execute("SELECT * FROM teachers WHERE username=%s AND password=%s", (u,p))
        teacher = cursor.fetchone()
        if teacher:
            session["teacher"] = u
            session["teacher_id"] = teacher[0]
            session["can_generate_qr"] = teacher[4]
            session["can_view_report"] = teacher[5]
            return redirect("/teacher_dashboard")
    return render_template("teacher_login.html")

@app.route("/teacher_logout")
def teacher_logout():
    session.clear()
    return redirect("/teacher_login")

# ------------------ DASHBOARDS ------------------
@app.route("/dashboard")
def dashboard():
    if "admin" not in session:
        return redirect("/")
    return render_template("dashboard.html")

@app.route("/teacher_dashboard")
def teacher_dashboard():
    if "teacher" not in session:
        return redirect("/teacher_login")
    return render_template("teacher_dashboard.html",
                           can_generate_qr=session.get("can_generate_qr"),
                           can_view_report=session.get("can_view_report"))

# ------------------ ADD STUDENT ------------------
@app.route("/add_student", methods=["GET","POST"])
def add_student():
    if "admin" not in session:
        return redirect("/")
    if request.method=="POST":
        sid = request.form["student_id"]
        name = request.form["student_name"]
        cursor.execute("INSERT INTO students(student_id, student_name) VALUES(%s,%s)", (sid,name))
        db.commit()
    cursor.execute("SELECT * FROM students")
    students = cursor.fetchall()
    return render_template("add_student.html", students=students)

@app.route("/delete_student/<int:id>")
def delete_student(id):
    cursor.execute("DELETE FROM students WHERE id=%s",(id,))
    db.commit()
    return redirect("/add_student")

# ------------------ ADD TEACHER ------------------
@app.route("/add_teacher", methods=["GET","POST"])
def add_teacher():
    if "admin" not in session:
        return redirect("/")
    if request.method=="POST":
        name = request.form["teacher_name"]
        username = request.form["username"]
        password = request.form["password"]
        can_qr = True if request.form.get("can_generate_qr") else False
        can_report = True if request.form.get("can_view_report") else False
        cursor.execute("""
            INSERT INTO teachers(teacher_name, username, password, can_generate_qr, can_view_report)
            VALUES (%s,%s,%s,%s,%s)
        """,(name, username, password, can_qr, can_report))
        db.commit()
    cursor.execute("SELECT * FROM teachers")
    teachers = cursor.fetchall()
    return render_template("add_teacher.html", teachers=teachers)

# ------------------ GENERATE QR ------------------
@app.route("/generate_qr", methods=["GET","POST"])
def generate_qr():
    if "admin" not in session and "teacher" not in session:
        return redirect("/")
    if "teacher" in session and not session.get("can_generate_qr"):
        return "Access Denied"

    qr_img = None
    cursor.execute("SELECT name FROM subjects")
    subjects = [x[0] for x in cursor.fetchall()]

    if request.method=="POST":
        subject = request.form.get("subject_dropdown") or request.form.get("subject_text")
        if not subject:
            return "Please select or type a subject"
        cursor.execute("SELECT id FROM subjects WHERE name=%s", (subject,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO subjects(name) VALUES(%s)", (subject,))
            db.commit()

        cursor.execute("INSERT INTO qr_session(subject, created_at) VALUES(%s,%s)", (subject, datetime.now()))
        db.commit()
        qr_id = cursor.lastrowid
        data = f"https://parallelly-preoptic-jeni.ngrok-free.dev/scan/{qr_id}"

        img = qrcode.make(data)
        qr_img = f"qr_{qr_id}.png"
        img.save(os.path.join(QR_FOLDER, qr_img))

        def disable_qr(qr_id):
            cursor.execute("UPDATE qr_session SET is_active=FALSE WHERE id=%s", (qr_id,))
            db.commit()
        t = Timer(60, disable_qr, args=(qr_id,))
        t.start()

    return render_template("generate_qr.html", qr=qr_img, subjects=subjects)

# ------------------ SCAN / ATTENDANCE ------------------
@app.route("/scan/<int:id>", methods=["GET","POST"])
def scan(id):
    cursor.execute("SELECT subject, created_at, is_active FROM qr_session WHERE id=%s", (id,))
    qr = cursor.fetchone()
    if not qr:
        return "Invalid QR"

    subject, created, is_active = qr

    if not is_active:
        return "QR Expired"
    if datetime.now() > created + timedelta(minutes=1):
        return "QR Expired"

    if request.method == "POST":
        sid = request.form["student_id"].strip()
        cursor.execute("SELECT student_name FROM students WHERE student_id=%s", (sid,))
        stu = cursor.fetchone()
        if not stu:
            return "Student not registered"

        today = datetime.now().date()
        cursor.execute("""
            SELECT * FROM attendance 
            WHERE student_id=%s AND subject=%s AND date=%s
        """, (sid, subject, today))
        if cursor.fetchone():
            return "Attendance already marked ✅"

        device_key = f"marked_{id}_{sid}"
        if session.get(device_key):
            return "Attendance already submitted from this device ❌"
        session[device_key] = True

        cursor.execute("""
            INSERT INTO attendance(student_id, student_name, subject, date, time)
            VALUES(%s,%s,%s,%s,%s)
        """, (sid, stu[0], subject, today, datetime.now().time()))
        db.commit()
        return render_template("success.html")

    return render_template("student_attendance.html", subject=subject)

# ------------------ REPORT ------------------
@app.route("/report", methods=["GET","POST"])
def report():
    if "admin" not in session and "teacher" not in session:
        return redirect("/")
    if "teacher" in session and not session.get("can_view_report"):
        return "Access Denied"

    attendance = {}
    cursor.execute("SELECT student_id, student_name FROM students")
    students = cursor.fetchall()
    subjects = []

    if request.method=="POST":
        subject = request.form["subject"]
        date = request.form["date"]
        cursor.execute("SELECT student_id FROM attendance WHERE subject=%s AND date=%s", (subject, date))
        present_ids = [x[0] for x in cursor.fetchall()]
        for s in students:
            attendance[s[0]] = "Present" if s[0] in present_ids else "Absent"

    cursor.execute("SELECT name FROM subjects")
    subjects = [x[0] for x in cursor.fetchall()]

    return render_template("report.html", students=students, attendance=attendance,
                           subjects=subjects, date=request.form.get("date"),
                           subject=request.form.get("subject"))

# ------------------ RUN ------------------
if __name__=="__main__":
    app.run(debug=True)
