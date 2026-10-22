import os
import secrets
import sqlite3
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("DATABASE_PATH", BASE_DIR / "school.db"))
UPLOAD_FOLDER = Path(os.environ.get("UPLOAD_FOLDER", BASE_DIR / "static" / "uploads"))
ALLOWED_IMAGES = {"png", "jpg", "jpeg", "gif", "webp"}

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
    MAX_CONTENT_LENGTH=8 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
)


def connect_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with connect_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS principals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            admission_no TEXT UNIQUE NOT NULL,
            class_name TEXT NOT NULL,
            section TEXT DEFAULT '',
            parent_name TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            email TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            employee_id TEXT UNIQUE NOT NULL,
            designation TEXT NOT NULL,
            phone TEXT DEFAULT '',
            email TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS gallery (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            filename TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS inquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_name TEXT NOT NULL,
            student_name TEXT NOT NULL,
            class_applied TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT DEFAULT '',
            message TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'New'
        );
        CREATE TABLE IF NOT EXISTS csrf_tokens (
            token TEXT PRIMARY KEY,
            created_at TEXT NOT NULL
        );
        """)
        existing = db.execute("SELECT * FROM principals LIMIT 1").fetchone()
        if existing and existing["email"] == "principal@svschool.edu" and check_password_hash(existing["password_hash"], "School@123"):
            password = secrets.token_urlsafe(18)
            db.execute("UPDATE principals SET password_hash = ? WHERE id = ?",
                       (generate_password_hash(password), existing["id"]))
            print(f"The old demo password was replaced. New principal password (save it now): {password}")
        if not existing:
            email = os.environ.get("PRINCIPAL_EMAIL", "principal@svschool.edu").strip().lower()
            password = os.environ.get("PRINCIPAL_PASSWORD", "")
            if not password:
                password = secrets.token_urlsafe(15)
                print(f"Initial principal password (save it now): {password}")
            db.execute("INSERT INTO principals (email, password_hash) VALUES (?, ?)",
                       (email, generate_password_hash(password)))


def principal_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("principal_id"):
            flash("Please sign in with the Principal account first.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.before_request
def protect_forms():
    if request.method != "POST":
        return
    token = request.form.get("csrf_token", "")
    expected = session.get("csrf_token", "")
    if not token or not expected or not secrets.compare_digest(token, expected):
        return "Your form session expired. Go back, reload the page, and try again.", 400


@app.context_processor
def inject_globals():
    if not session.get("csrf_token"):
        session["csrf_token"] = secrets.token_urlsafe(32)
    return {"school_name": "Swami Vivekanand School"}


@app.route("/")
def home():
    with connect_db() as db:
        student_count = db.execute("SELECT COUNT(*) n FROM students").fetchone()["n"]
        staff_count = db.execute("SELECT COUNT(*) n FROM staff").fetchone()["n"]
        gallery_count = db.execute("SELECT COUNT(*) n FROM gallery").fetchone()["n"]
        photos = db.execute("SELECT * FROM gallery ORDER BY id DESC LIMIT 3").fetchall()
    return render_template("index.html", student_count=student_count, staff_count=staff_count,
                           gallery_count=gallery_count, photos=photos)


@app.route("/admissions", methods=["GET", "POST"])
def admissions():
    if request.method == "POST":
        values = [request.form.get(k, "").strip() for k in
                  ["parent_name", "student_name", "class_applied", "phone", "email", "message"]]
        if not all(values[:4]):
            flash("Please complete the required fields.", "danger")
        else:
            with connect_db() as db:
                db.execute("""INSERT INTO inquiries
                    (parent_name, student_name, class_applied, phone, email, message, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""", (*values, datetime.now().strftime("%d %b %Y, %I:%M %p")))
            flash("Thank you. The school office has received your admission inquiry.", "success")
            return redirect(url_for("admissions"))
    return render_template("admissions.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with connect_db() as db:
            principal = db.execute("SELECT * FROM principals WHERE email = ?", (email,)).fetchone()
        if principal and check_password_hash(principal["password_hash"], password):
            session.clear()
            session["principal_id"] = principal["id"]
            session["principal_email"] = principal["email"]
            session["csrf_token"] = secrets.token_urlsafe(32)
            flash("Welcome back, Principal.", "success")
            return redirect(url_for("dashboard"))
        flash("Incorrect email or password.", "danger")
    return render_template("login.html")


@app.post("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("home"))


@app.route("/dashboard")
@principal_required
def dashboard():
    with connect_db() as db:
        students = db.execute("SELECT COUNT(*) n FROM students").fetchone()["n"]
        staff = db.execute("SELECT COUNT(*) n FROM staff").fetchone()["n"]
        photos = db.execute("SELECT COUNT(*) n FROM gallery").fetchone()["n"]
        inquiries = db.execute("SELECT COUNT(*) n FROM inquiries WHERE status = 'New'").fetchone()["n"]
    return render_template("dashboard.html", students=students, staff=staff, photos=photos, inquiries=inquiries)


@app.route("/inquiries")
@principal_required
def inquiry_list():
    with connect_db() as db:
        inquiries = db.execute("SELECT * FROM inquiries ORDER BY id DESC").fetchall()
    return render_template("inquiries.html", inquiries=inquiries)


@app.post("/inquiries/<int:item_id>/status")
@principal_required
def update_inquiry(item_id):
    status = request.form.get("status", "New")
    if status not in {"New", "Contacted", "Closed"}:
        flash("Choose a valid inquiry status.", "danger")
    else:
        with connect_db() as db:
            db.execute("UPDATE inquiries SET status = ? WHERE id = ?", (status, item_id))
        flash("Inquiry status updated.", "success")
    return redirect(url_for("inquiry_list"))


@app.route("/students")
@principal_required
def students():
    q = request.args.get("q", "").strip()
    with connect_db() as db:
        if q:
            like = f"%{q}%"
            rows = db.execute("""SELECT * FROM students WHERE name LIKE ? OR admission_no LIKE ?
                                 OR class_name LIKE ? ORDER BY name""", (like, like, like)).fetchall()
        else:
            rows = db.execute("SELECT * FROM students ORDER BY name").fetchall()
    return render_template("students.html", students=rows, q=q)


@app.post("/students/add")
@principal_required
def add_student():
    values = [request.form.get(k, "").strip() for k in
              ["name", "admission_no", "class_name", "section", "parent_name", "phone", "email"]]
    if not all(values[:3]):
        flash("Student name, admission number, and class are required.", "danger")
    else:
        try:
            with connect_db() as db:
                db.execute("""INSERT INTO students (name, admission_no, class_name, section, parent_name, phone, email)
                              VALUES (?, ?, ?, ?, ?, ?, ?)""", values)
            flash("Student added successfully.", "success")
        except sqlite3.IntegrityError:
            flash("That admission number already exists.", "danger")
    return redirect(url_for("students"))


@app.post("/students/delete/<int:item_id>")
@principal_required
def delete_student(item_id):
    with connect_db() as db:
        db.execute("DELETE FROM students WHERE id = ?", (item_id,))
    flash("Student record deleted.", "success")
    return redirect(url_for("students"))


@app.route("/staff")
@principal_required
def staff_page():
    q = request.args.get("q", "").strip()
    with connect_db() as db:
        if q:
            like = f"%{q}%"
            rows = db.execute("""SELECT * FROM staff WHERE name LIKE ? OR employee_id LIKE ?
                                 OR designation LIKE ? ORDER BY name""", (like, like, like)).fetchall()
        else:
            rows = db.execute("SELECT * FROM staff ORDER BY name").fetchall()
    return render_template("staff.html", staff=rows, q=q)


@app.post("/staff/add")
@principal_required
def add_staff():
    values = [request.form.get(k, "").strip() for k in
              ["name", "employee_id", "designation", "phone", "email"]]
    if not all(values[:3]):
        flash("Staff name, employee ID, and designation are required.", "danger")
    else:
        try:
            with connect_db() as db:
                db.execute("""INSERT INTO staff (name, employee_id, designation, phone, email)
                              VALUES (?, ?, ?, ?, ?)""", values)
            flash("Staff member added successfully.", "success")
        except sqlite3.IntegrityError:
            flash("That employee ID already exists.", "danger")
    return redirect(url_for("staff_page"))


@app.post("/staff/delete/<int:item_id>")
@principal_required
def delete_staff(item_id):
    with connect_db() as db:
        db.execute("DELETE FROM staff WHERE id = ?", (item_id,))
    flash("Staff record deleted.", "success")
    return redirect(url_for("staff_page"))


@app.route("/gallery")
def gallery():
    with connect_db() as db:
        photos = db.execute("SELECT * FROM gallery ORDER BY id DESC").fetchall()
    return render_template("gallery.html", photos=photos)


@app.post("/gallery/add")
@principal_required
def add_photo():
    title = request.form.get("title", "").strip()
    image_file = request.files.get("image")
    if not title or not image_file or not image_file.filename:
        flash("Enter a title and choose an image.", "danger")
        return redirect(url_for("gallery"))
    ext = image_file.filename.rsplit(".", 1)[-1].lower() if "." in image_file.filename else ""
    if ext not in ALLOWED_IMAGES:
        flash("Use a JPG, PNG, GIF, or WEBP image.", "danger")
        return redirect(url_for("gallery"))
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    filename = secure_filename(f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}_{image_file.filename}")
    image_file.save(UPLOAD_FOLDER / filename)
    with connect_db() as db:
        db.execute("INSERT INTO gallery (title, filename, created_at) VALUES (?, ?, ?)",
                   (title, filename, datetime.now().strftime("%d %b %Y")))
    flash("Photo added to the gallery.", "success")
    return redirect(url_for("gallery"))


@app.post("/gallery/delete/<int:item_id>")
@principal_required
def delete_photo(item_id):
    with connect_db() as db:
        photo = db.execute("SELECT filename FROM gallery WHERE id = ?", (item_id,)).fetchone()
        if photo:
            path = UPLOAD_FOLDER / photo["filename"]
            if path.is_file():
                path.unlink()
            db.execute("DELETE FROM gallery WHERE id = ?", (item_id,))
    flash("Photo removed.", "success")
    return redirect(url_for("gallery"))


@app.errorhandler(413)
def too_large(_error):
    flash("Image is too large. Please upload an image smaller than 8 MB.", "danger")
    return redirect(url_for("gallery"))


init_db()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
