from flask import Flask,render_template,request,redirect,session
import mysql.connector
import qrcode
from datetime import datetime,timedelta
import os

app = Flask(__name__)
app.secret_key="secret123"

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",
    database="attendance_db"
)
cursor = db.cursor()

QR_FOLDER="static/qr"
os.makedirs(QR_FOLDER,exist_ok=True)

# ---------------- ADMIN LOGIN ----------------
@app.route("/",methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=request.form["username"]
        p=request.form["password"]
        cursor.execute("SELECT * FROM admin WHERE username=%s AND password=%s",(u,p))
        if cursor.fetchone():
            session["admin"]=u
            return redirect("/dashboard")
    return render_template("admin_login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "admin" not in session:
        return redirect("/")
    return render_template("dashboard.html")

# ---------------- STUDENT CRUD ----------------
@app.route("/add_student",methods=["GET","POST"])
def add_student():
    if "admin" not in session:
        return redirect("/")
    if request.method=="POST":
        sid=request.form["student_id"]
        name=request.form["student_name"]
        cursor.execute("INSERT INTO students(student_id,student_name) VALUES(%s,%s)",(sid,name))
        db.commit()
    cursor.execute("SELECT * FROM students")
    students=cursor.fetchall()
    return render_template("add_student.html",students=students)

@app.route("/delete/<int:id>")
def delete(id):
    cursor.execute("DELETE FROM students WHERE id=%s",(id,))
    db.commit()
    return redirect("/add_student")

# ---------------- QR GENERATE ----------------
@app.route("/generate_qr",methods=["GET","POST"])
def generate_qr():
    if "admin" not in session:
        return redirect("/")
    qr_img=None
    if request.method=="POST":
        subject=request.form["subject"]
        cursor.execute("INSERT INTO qr_session(subject,created_at) VALUES(%s,%s)",
                       (subject,datetime.now()))
        db.commit()
        qr_id=cursor.lastrowid
        data=f"http://127.0.0.1:5000/scan/{qr_id}"
        img=qrcode.make(data)
        qr_img=f"qr_{qr_id}.png"
        img.save(os.path.join(QR_FOLDER,qr_img))
    return render_template("generate_qr.html",qr=qr_img)

# ---------------- STUDENT SCAN ----------------
@app.route("/scan/<int:id>",methods=["GET","POST"])
def scan(id):
    cursor.execute("SELECT subject,created_at,is_active FROM qr_session WHERE id=%s",(id,))
    qr=cursor.fetchone()
    if not qr:
        return "Invalid QR"

    subject,created,is_active=qr

    if not is_active:
        return "QR Cancelled"

    if datetime.now()>created+timedelta(minutes=1):
        return "QR Expired"

    if request.method=="POST":
        sid=request.form["student_id"]
        cursor.execute("SELECT student_name FROM students WHERE student_id=%s",(sid,))
        stu=cursor.fetchone()
        if not stu:
            return "Student not registered"

        today=datetime.now().date()
        cursor.execute("""SELECT * FROM attendance 
                          WHERE student_id=%s AND subject=%s AND date=%s""",
                       (sid,subject,today))
        if cursor.fetchone():
            return "Attendance already marked"

        cursor.execute("""INSERT INTO attendance
            (student_id,student_name,subject,date,time)
            VALUES(%s,%s,%s,%s,%s)""",
            (sid,stu[0],subject,today,datetime.now().time()))
        db.commit()
        return render_template("success.html")
    return render_template("student_attendance.html",subject=subject)

# ---------------- REPORT ----------------
@app.route("/report",methods=["GET","POST"])
def report():
    if "admin" not in session:
        return redirect("/")
    attendance={}
    cursor.execute("SELECT student_id,student_name FROM students")
    students=cursor.fetchall()
    if request.method=="POST":
        subject=request.form["subject"]
        date=request.form["date"]
        cursor.execute("SELECT student_id FROM attendance WHERE subject=%s AND date=%s",(subject,date))
        present=[x[0] for x in cursor.fetchall()]
        for s in students:
            attendance[s[0]]="Present" if s[0] in present else "Absent"
    return render_template("report.html",students=students,attendance=attendance)

app.run(debug=True)
