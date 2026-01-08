from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
from datetime import datetime, timedelta
import random

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "your-secret-key-here-change-in-production")

# Setup Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Database file
DB_FILE = "uniface360.db"

# ==================== DATABASE INITIALIZATION ====================

def init_database():
    """Initialize database with all required tables"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user'
        )
    """)
    
    # Departments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            parent_department_id INTEGER,
            manager_id INTEGER,
            FOREIGN KEY (parent_department_id) REFERENCES departments(id),
            FOREIGN KEY (manager_id) REFERENCES employees(id)
        )
    """)
    
    # Sites table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT,
            location TEXT,
            capacity INTEGER
        )
    """)
    
    # Positions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            department_id INTEGER,
            FOREIGN KEY (department_id) REFERENCES departments(id)
        )
    """)
    
    # Employees table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_number TEXT UNIQUE,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            department_id INTEGER,
            site_id INTEGER,
            position_id INTEGER,
            hire_date DATE,
            salary DECIMAL(10,2),
            status TEXT DEFAULT 'active',
            photo_url TEXT,
            FOREIGN KEY (department_id) REFERENCES departments(id),
            FOREIGN KEY (site_id) REFERENCES sites(id),
            FOREIGN KEY (position_id) REFERENCES positions(id)
        )
    """)
    
    # Attendance table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER,
            date DATE,
            check_in_time TIME,
            check_out_time TIME,
            shift_id INTEGER,
            status TEXT,
            work_hours DECIMAL(4,2),
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )
    """)
    
    # Leave types table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leave_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            is_paid INTEGER DEFAULT 1,
            max_days INTEGER
        )
    """)
    
    # Leaves table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leaves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER,
            leave_type_id INTEGER,
            start_date DATE,
            end_date DATE,
            days INTEGER,
            reason TEXT,
            status TEXT,
            approved_by INTEGER,
            FOREIGN KEY (employee_id) REFERENCES employees(id),
            FOREIGN KEY (leave_type_id) REFERENCES leave_types(id),
            FOREIGN KEY (approved_by) REFERENCES employees(id)
        )
    """)
    
    # Payroll table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payroll (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER,
            payroll_month INTEGER,
            payroll_year INTEGER,
            gross_salary DECIMAL(10,2),
            net_salary DECIMAL(10,2),
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )
    """)
    
    # HSE Categories table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hse_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )
    """)
    
    # HSE Tracking table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hse_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE,
            month TEXT,
            employee_id INTEGER,
            department_id INTEGER,
            type TEXT,
            description TEXT,
            priority TEXT,
            category_id INTEGER,
            corrective_action TEXT,
            action_status TEXT,
            closure_date DATE,
            days_to_close REAL,
            reported_by INTEGER,
            verified_by INTEGER,
            FOREIGN KEY (employee_id) REFERENCES employees(id),
            FOREIGN KEY (department_id) REFERENCES departments(id),
            FOREIGN KEY (category_id) REFERENCES hse_categories(id),
            FOREIGN KEY (reported_by) REFERENCES employees(id),
            FOREIGN KEY (verified_by) REFERENCES employees(id)
        )
    """)
    
    # HSE Trainings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hse_trainings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER,
            training_name TEXT,
            training_date DATE,
            status TEXT,
            completion_date DATE,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )
    """)
    
    # HSE Reports table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hse_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER,
            department_id INTEGER,
            report_date DATE,
            report_type TEXT,
            status TEXT,
            approved_by INTEGER,
            FOREIGN KEY (employee_id) REFERENCES employees(id),
            FOREIGN KEY (department_id) REFERENCES departments(id),
            FOREIGN KEY (approved_by) REFERENCES employees(id)
        )
    """)
    
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

# ==================== DUMMY DATA GENERATION ====================

def generate_dummy_data():
    """Generate and insert dummy data into database"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Check if data already exists
    cursor.execute("SELECT COUNT(*) FROM employees")
    if cursor.fetchone()[0] > 0:
        print("Dummy data already exists. Skipping generation.")
        conn.close()
        return
    
    print("Generating dummy data...")
    
    # Create default admin user
    cursor.execute("SELECT COUNT(*) FROM users WHERE username = ?", ("admin",))
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            ("admin", generate_password_hash("admin123"), "admin")
        )
        cursor.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            ("admin_hse", generate_password_hash("admin123"), "admin_hse")
        )
        cursor.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            ("user_hse", generate_password_hash("emp123"), "user_hse")
        )
    
    # Departments
    departments = ["Drilling", "Operations", "Production", "HSE", "Maintenance", "Logistics"]
    dept_ids = {}
    for dept in departments:
        cursor.execute("INSERT INTO departments (name) VALUES (?)", (dept,))
        dept_ids[dept] = cursor.lastrowid
    
    # Sites
    sites = [
        ("Main Office", "Cairo, Egypt", "Cairo", 200),
        ("Oil Platform Alpha", "Mediterranean Sea", "Offshore", 150),
        ("Refinery Site", "Alexandria, Egypt", "Alexandria", 300)
    ]
    site_ids = {}
    for site in sites:
        cursor.execute(
            "INSERT INTO sites (name, address, location, capacity) VALUES (?, ?, ?, ?)",
            site
        )
        site_ids[site[0]] = cursor.lastrowid
    
    # Positions
    positions = [
        ("HSE Officer", dept_ids["HSE"]),
        ("Engineer", dept_ids["Drilling"]),
        ("Technician", dept_ids["Operations"]),
        ("Operator", dept_ids["Production"]),
        ("Supervisor", dept_ids["Maintenance"]),
        ("Analyst", dept_ids["Logistics"]),
        ("Manager", None),
        ("Coordinator", None)
    ]
    position_ids = {}
    for pos in positions:
        cursor.execute(
            "INSERT INTO positions (title, department_id) VALUES (?, ?)",
            pos
        )
        position_ids[pos[0]] = cursor.lastrowid
    
    # Employees
    first_names = ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", 
                   "Thomas", "Charles", "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", 
                   "Barbara", "Susan", "Jessica", "Sarah", "Karen"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", 
                 "Rodriguez", "Martinez", "Hernandez", "Lopez", "Wilson", "Anderson", "Thomas"]
    
    employee_ids = []
    for i in range(1, 51):
        first_name = random.choice(first_names)
        last_name = random.choice(last_names)
        name = f"{first_name} {last_name}"
        emp_num = f"E{i:03d}"
        dept = random.choice(departments)
        site = random.choice(list(site_ids.keys()))
        position = random.choice(list(position_ids.keys()))
        
        year = random.randint(2020, 2024)
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        hire_date = f"{year}-{month:02d}-{day:02d}"
        
        salary = round(random.uniform(5000, 15000), 2)
        photo_url = f"https://i.pravatar.cc/150?img={i % 70 + 1}"
        
        cursor.execute("""
            INSERT INTO employees (employee_number, name, email, phone, department_id, 
                                 site_id, position_id, hire_date, salary, status, photo_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (emp_num, name, f"{first_name.lower()}.{last_name.lower()}@company.com", 
              f"+20{random.randint(1000000000, 9999999999)}", dept_ids[dept], 
              site_ids[site], position_ids[position], hire_date, salary, "active", photo_url))
        employee_ids.append(cursor.lastrowid)
    
    # Leave Types
    leave_types = [
        ("Annual Leave", 1, 21),
        ("Sick Leave", 1, 30),
        ("Emergency Leave", 0, 5),
        ("Maternity Leave", 1, 90),
        ("Paternity Leave", 1, 7)
    ]
    leave_type_ids = {}
    for lt in leave_types:
        cursor.execute(
            "INSERT INTO leave_types (name, is_paid, max_days) VALUES (?, ?, ?)",
            lt
        )
        leave_type_ids[lt[0]] = cursor.lastrowid
    
    # Attendance (last 30 days)
    for emp_id in employee_ids[:30]:  # Only for first 30 employees
        for day in range(30):
            date = (datetime.now() - timedelta(days=day)).strftime("%Y-%m-%d")
            if random.random() > 0.1:  # 90% attendance rate
                check_in = f"{random.randint(7, 9):02d}:{random.randint(0, 59):02d}:00"
                check_out = f"{random.randint(16, 18):02d}:{random.randint(0, 59):02d}:00"
                status = "present" if random.random() > 0.1 else "late"
                work_hours = round(random.uniform(7.5, 9.0), 2)
                
                cursor.execute("""
                    INSERT INTO attendance (employee_id, date, check_in_time, check_out_time, 
                                         status, work_hours)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (emp_id, date, check_in, check_out, status, work_hours))
    
    # Leaves
    for _ in range(50):
        emp_id = random.choice(employee_ids)
        leave_type = random.choice(list(leave_type_ids.keys()))
        start_date = (datetime.now() - timedelta(days=random.randint(1, 180))).strftime("%Y-%m-%d")
        days = random.randint(1, 7)
        end_date = (datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=days)).strftime("%Y-%m-%d")
        status = random.choice(["pending", "approved", "rejected"])
        approved_by = random.choice(employee_ids) if status != "pending" else None
        
        cursor.execute("""
            INSERT INTO leaves (employee_id, leave_type_id, start_date, end_date, days, 
                              reason, status, approved_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (emp_id, leave_type_ids[leave_type], start_date, end_date, days, 
              f"Leave request for {leave_type}", status, approved_by))
    
    # Payroll (last 3 months)
    for month_offset in range(3):
        month = (datetime.now() - timedelta(days=30*month_offset)).month
        year = (datetime.now() - timedelta(days=30*month_offset)).year
        for emp_id in employee_ids[:30]:
            gross = round(random.uniform(5000, 15000), 2)
            net = round(gross * 0.85, 2)  # 15% deductions
            
            cursor.execute("""
                INSERT INTO payroll (employee_id, payroll_month, payroll_year, gross_salary, net_salary)
                VALUES (?, ?, ?, ?, ?)
            """, (emp_id, month, year, gross, net))
    
    # HSE Categories
    hse_categories = ["Lifting", "Housekeeping", "Behavior", "Environmental", "Electrical", 
                     "Confined Space", "PPE", "Process Safety"]
    category_ids = {}
    for cat in hse_categories:
        cursor.execute("INSERT INTO hse_categories (name) VALUES (?)", (cat,))
        category_ids[cat] = cursor.lastrowid
    
    # HSE Tracking (last 3 months)
    types = ["Violation", "Near Miss", "Observation"]
    priorities = ["High", "Medium", "Low"]
    statuses = ["Closed", "In Progress", "Open"]
    
    for i in range(100):
        date_obj = datetime.now() - timedelta(days=random.randint(1, 90))
        date_str = date_obj.strftime("%Y-%m-%d")
        month_str = date_obj.strftime("%Y-%m")
        emp_id = random.choice(employee_ids)
        dept_id = random.choice(list(dept_ids.values()))
        event_type = random.choice(types)
        priority = random.choice(priorities)
        category_id = random.choice(list(category_ids.values()))
        action_status = random.choice(statuses)
        
        corrective_actions = ["Site inspection", "Toolbox talk", "PPE refresher", 
                            "JSA review", "Corrective training"]
        corrective_action = random.choice(corrective_actions)
        
        closure_date = None
        days_to_close = None
        if action_status == "Closed":
            closure_date_obj = date_obj + timedelta(days=random.randint(5, 20))
            closure_date = closure_date_obj.strftime("%Y-%m-%d")
            days_to_close = (closure_date_obj - date_obj).days
        
        reported_by = random.choice(employee_ids)
        verified_by = random.choice(employee_ids)
        
        cursor.execute("""
            INSERT INTO hse_tracking (date, month, employee_id, department_id, type, description,
                                     priority, category_id, corrective_action, action_status,
                                     closure_date, days_to_close, reported_by, verified_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (date_str, month_str, emp_id, dept_id, event_type, 
              f"{event_type} related to {list(category_ids.keys())[category_id-1].lower()}", 
              priority, category_id, corrective_action, action_status, closure_date, 
              days_to_close, reported_by, verified_by))
    
    # HSE Trainings
    training_names = ["Safety Orientation", "Fire Safety", "First Aid", "Hazard Communication",
                     "Confined Space Entry", "Lockout/Tagout", "PPE Training"]
    for _ in range(80):
        emp_id = random.choice(employee_ids)
        training_name = random.choice(training_names)
        training_date = (datetime.now() - timedelta(days=random.randint(1, 365))).strftime("%Y-%m-%d")
        status = random.choice(["completed", "in_progress", "pending"])
        completion_date = training_date if status == "completed" else None
        
        cursor.execute("""
            INSERT INTO hse_trainings (employee_id, training_name, training_date, status, completion_date)
            VALUES (?, ?, ?, ?, ?)
        """, (emp_id, training_name, training_date, status, completion_date))
    
    # HSE Reports
    report_types = ["Incident Report", "Inspection Report", "Audit Report", "Training Report"]
    for _ in range(40):
        emp_id = random.choice(employee_ids)
        dept_id = random.choice(list(dept_ids.values()))
        report_date = (datetime.now() - timedelta(days=random.randint(1, 90))).strftime("%Y-%m-%d")
        report_type = random.choice(report_types)
        status = random.choice(["pending", "approved", "rejected"])
        approved_by = random.choice(employee_ids) if status != "pending" else None
        
        cursor.execute("""
            INSERT INTO hse_reports (employee_id, department_id, report_date, report_type, status, approved_by)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (emp_id, dept_id, report_date, report_type, status, approved_by))
    
    conn.commit()
    conn.close()
    print("Dummy data generated successfully!")

# ==================== USER MODEL ====================

class User(UserMixin):
    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.execute("SELECT id, username, role FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return User(user[0], user[1], user[2])
    return None

# ==================== ROUTES ====================

@app.route("/")
@app.route("/home")
def home():
    return render_template("home.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        if current_user.role == "admin":
            return redirect(url_for("hr_home"))
        elif current_user.role == "admin_hse":
            return redirect(url_for("admin_hse_dashboard"))
        elif current_user.role == "user_hse":
            return redirect(url_for("employee_hse_dashboard"))
        return redirect(url_for("hr_home"))
    
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        
        # Only allow the three specific users
        allowed_users = ["admin", "admin_hse", "user_hse"]
        
        if username not in allowed_users:
            flash("Invalid username or password. Only admin, admin_hse, and user_hse are allowed.", "error")
            return render_template("login_2.html")
        
        # Get user from database and verify password
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.execute("SELECT id, username, password, role FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user[2], password):
            login_user(User(user[0], user[1], user[3]))
            # Redirect based on user role
            if user[3] == "admin":
                return redirect(url_for("hr_home"))
            elif user[3] == "admin_hse":
                return redirect(url_for("admin_hse_dashboard"))
            elif user[3] == "user_hse":
                return redirect(url_for("employee_hse_dashboard"))
            return redirect(url_for("hr_home"))
        
        flash("Invalid username or password. Only admin, admin_hse, and user_hse are allowed.", "error")
    
    return render_template("login_2.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    """Main dashboard - redirects based on user role"""
    if current_user.role == "admin":
        return redirect(url_for("hr_home"))
    elif current_user.role == "admin_hse":
        return redirect(url_for("admin_hse_dashboard"))
    elif current_user.role == "user_hse":
        return redirect(url_for("employee_hse_dashboard"))
    else:
        return redirect(url_for("hr_home"))

@app.route("/support")
def support():
    return render_template("support.html")

@app.route("/send_support_email", methods=["POST"])
def send_support_email():
    name = request.form.get("name")
    email = request.form.get("email")
    message = request.form.get("message")
    
    # In production, send actual email
    flash("Your message has been sent successfully! We will contact you soon.", "success")
    return redirect(url_for("support"))

@app.route("/request_demo", methods=["GET"])
def request_demo():
    return render_template("request_demo.html")

@app.route("/send_demo_request", methods=["POST"])
def send_demo_request():
    name = request.form.get("name")
    company = request.form.get("company")
    email = request.form.get("email", "Not provided")
    phone = request.form.get("phone", "Not provided")
    building_size = request.form.get("building_size", "Not provided")
    message = request.form.get("message", "")
    
    # In production, send actual email
    flash("Your demo request has been submitted successfully! Our team will contact you shortly.", "success")
    return redirect(url_for("request_demo"))

@app.route("/profile")
@login_required
def profile():
    return render_template("profile.html")

# ==================== HR MODULE ROUTES ====================

@app.route("/hr")
@app.route("/hr/")
@login_required
def hr_home():
    if current_user.role != "admin":
        flash("Access denied. Admin only.", "error")
        return redirect(url_for("login"))
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Get HR statistics
    cursor.execute("SELECT COUNT(*) FROM employees WHERE status = 'active'")
    total_employees = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM attendance WHERE date = DATE('now') AND status = 'present'")
    today_attendance = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM leaves WHERE status = 'pending'")
    pending_leaves = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM employees WHERE hire_date >= DATE('now', '-30 days')")
    recent_hires = cursor.fetchone()[0]
    
    conn.close()
    
    return render_template("hr/index.html",
                         total_employees=total_employees,
                         today_attendance=today_attendance,
                         pending_leaves=pending_leaves,
                         recent_hires=recent_hires)

@app.route("/hr/employees")
@login_required
def hr_employees():
    if current_user.role != "admin":
        flash("Access denied. Admin only.", "error")
        return redirect(url_for("login"))
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT e.*, d.name as department_name, s.name as site_name, p.title as position_title
        FROM employees e
        LEFT JOIN departments d ON e.department_id = d.id
        LEFT JOIN sites s ON e.site_id = s.id
        LEFT JOIN positions p ON e.position_id = p.id
        WHERE e.status = 'active'
        ORDER BY e.name
    """)
    
    employees = []
    for row in cursor.fetchall():
        employees.append({
            "id": row[0],  # e.id
            "employee_number": row[1],  # e.employee_number
            "name": row[2],  # e.name
            "email": row[3],  # e.email
            "phone": row[4],  # e.phone
            "department_name": row[12],  # d.name
            "site_name": row[13],  # s.name
            "position_title": row[14],  # p.title
            "hire_date": row[8],  # e.hire_date
            "salary": row[9]  # e.salary
        })
    
    conn.close()
    return render_template("hr/employees/index.html", employees=employees)

@app.route("/hr/departments")
@login_required
def hr_departments():
    if current_user.role != "admin":
        flash("Access denied. Admin only.", "error")
        return redirect(url_for("login"))
    return render_template("hr/departments/index.html")

@app.route("/hr/recruitment")
@login_required
def hr_recruitment():
    if current_user.role != "admin":
        flash("Access denied. Admin only.", "error")
        return redirect(url_for("login"))
    return render_template("hr/recruitment/index.html")

@app.route("/hr/attendance")
@login_required
def hr_attendance():
    if current_user.role != "admin":
        flash("Access denied. Admin only.", "error")
        return redirect(url_for("login"))
    return render_template("hr/attendance/index.html")

@app.route("/hr/leaves")
@login_required
def hr_leaves():
    if current_user.role != "admin":
        flash("Access denied. Admin only.", "error")
        return redirect(url_for("login"))
    return render_template("hr/leaves/index.html")

@app.route("/hr/payroll")
@login_required
def hr_payroll():
    if current_user.role != "admin":
        flash("Access denied. Admin only.", "error")
        return redirect(url_for("login"))
    return render_template("hr/payroll/index.html")

@app.route("/hr/compensation")
@login_required
def hr_compensation():
    if current_user.role != "admin":
        flash("Access denied. Admin only.", "error")
        return redirect(url_for("login"))
    return render_template("hr/compensation/index.html")

@app.route("/hr/performance")
@login_required
def hr_performance():
    if current_user.role != "admin":
        flash("Access denied. Admin only.", "error")
        return redirect(url_for("login"))
    return render_template("hr/performance/index.html")

@app.route("/hr/training")
@login_required
def hr_training():
    if current_user.role != "admin":
        flash("Access denied. Admin only.", "error")
        return redirect(url_for("login"))
    return render_template("hr/training/index.html")

@app.route("/hr/sites")
@login_required
def hr_sites():
    if current_user.role != "admin":
        flash("Access denied. Admin only.", "error")
        return redirect(url_for("login"))
    return render_template("hr/sites/index.html")

@app.route("/hr/access")
@login_required
def hr_access():
    if current_user.role != "admin":
        flash("Access denied. Admin only.", "error")
        return redirect(url_for("login"))
    return render_template("hr/access/index.html")

@app.route("/hr/reports")
@login_required
def hr_reports():
    if current_user.role != "admin":
        flash("Access denied. Admin only.", "error")
        return redirect(url_for("login"))
    return render_template("hr/reports/index.html")

# ==================== HSE MODULE ROUTES ====================

@app.route("/hse/admin")
@login_required
def admin_hse_dashboard():
    if current_user.role not in ["admin", "admin_hse"]:
        return redirect(url_for("employee_hse_dashboard"))
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Get HSE statistics
    cursor.execute("""
        SELECT COUNT(*) FROM hse_tracking 
        WHERE type = 'Violation' AND date >= DATE('now', 'start of year')
    """)
    total_violations = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM hse_tracking 
        WHERE type = 'Near Miss' AND date >= DATE('now', 'start of year')
    """)
    total_near_misses = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM hse_tracking 
        WHERE type = 'Observation' AND date >= DATE('now', 'start of year')
    """)
    total_observations = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM hse_trainings 
        WHERE status = 'completed' AND completion_date >= DATE('now', 'start of year')
    """)
    completed_trainings = cursor.fetchone()[0]
    
    conn.close()
    
    return render_template("admin_hse_dashboard.html",
                         current_year=datetime.now().year,
                         total_violations=total_violations,
                         total_near_misses=total_near_misses,
                         total_observations=total_observations,
                         completed_trainings=completed_trainings)

@app.route("/hse/admin/tracking")
@login_required
def admin_hse_tracking():
    if current_user.role not in ["admin", "admin_hse"]:
        return redirect(url_for("employee_hse_dashboard"))
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT ht.*, e.name as employee_name, d.name as department_name, hc.name as category_name
        FROM hse_tracking ht
        LEFT JOIN employees e ON ht.employee_id = e.id
        LEFT JOIN departments d ON ht.department_id = d.id
        LEFT JOIN hse_categories hc ON ht.category_id = hc.id
        ORDER BY ht.date DESC
        LIMIT 100
    """)
    
    tracking_data = []
    for row in cursor.fetchall():
        tracking_data.append({
            "date": row[1],
            "month": row[2],
            "employee_name": row[15] or "Unknown",
            "department": row[16] or "Unknown",
            "type": row[5],
            "description": row[6],
            "priority": row[7],
            "category": row[17] or "Unknown",  # category_name
            "corrective_action": row[9],
            "action_status": row[10],
            "closure_date": row[11],
            "days_to_close": row[12]
        })
    
    conn.close()
    return render_template("admin_hse_tracking.html", tracking_data=tracking_data)

@app.route("/hse/admin/reports")
@login_required
def admin_hse_reports():
    if current_user.role not in ["admin", "admin_hse"]:
        return redirect(url_for("employee_hse_dashboard"))
    return render_template("admin_hse_reports.html")

@app.route("/hse/admin/monthly-dashboard")
@login_required
def admin_hse_monthly_dashboard():
    if current_user.role not in ["admin", "admin_hse"]:
        return redirect(url_for("employee_hse_dashboard"))
    return render_template("admin_hse_monthly_dashboard.html", month=datetime.now().strftime('%Y-%m'))

@app.route("/hse/admin/employees")
@login_required
def admin_hse_employees():
    if current_user.role not in ["admin", "admin_hse"]:
        return redirect(url_for("employee_hse_dashboard"))
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT e.*, d.name as department_name
        FROM employees e
        LEFT JOIN departments d ON e.department_id = d.id
        WHERE e.status = 'active'
        ORDER BY e.name
    """)
    
    employees = []
    for row in cursor.fetchall():
        employees.append({
            "id": row[1] if row[1] else f"E{row[0]:03d}",
            "name": row[2],
            "department": row[12] or "Unknown",  # d.name (department_name)
            "position": "Employee",
            "supervisor": "Supervisor",
            "hire_date": row[8] or "2020-01-01",  # e.hire_date
            "photo_url": row[11] or "https://i.pravatar.cc/150?img=1"  # e.photo_url
        })
    
    conn.close()
    return render_template("admin_hse_employees.html", employees=employees)

@app.route("/hse/admin/settings")
@login_required
def admin_hse_settings():
    if current_user.role not in ["admin", "admin_hse"]:
        return redirect(url_for("employee_hse_dashboard"))
    return render_template("admin_hse_settings.html")

@app.route("/hse/admin/incidents")
@login_required
def admin_hse_incidents():
    if current_user.role not in ["admin", "admin_hse"]:
        return redirect(url_for("employee_hse_dashboard"))
    return render_template("admin_hse_incidents.html", current_year=datetime.now().year)

@app.route("/hse/admin/inspections")
@login_required
def admin_hse_inspections():
    if current_user.role not in ["admin", "admin_hse"]:
        return redirect(url_for("employee_hse_dashboard"))
    return render_template("admin_hse_inspections.html", current_year=datetime.now().year)

@app.route("/hse/admin/risks")
@login_required
def admin_hse_risks():
    if current_user.role not in ["admin", "admin_hse"]:
        return redirect(url_for("employee_hse_dashboard"))
    return render_template("admin_hse_risks.html", current_year=datetime.now().year)

@app.route("/hse/admin/trainings")
@login_required
def admin_hse_trainings():
    if current_user.role not in ["admin", "admin_hse"]:
        return redirect(url_for("employee_hse_dashboard"))
    return render_template("admin_hse_trainings.html", current_year=datetime.now().year)

@app.route("/hse/admin/ppe")
@login_required
def admin_hse_ppe():
    if current_user.role not in ["admin", "admin_hse"]:
        return redirect(url_for("employee_hse_dashboard"))
    return render_template("admin_hse_ppe.html", current_year=datetime.now().year)

@app.route("/hse/admin/environmental")
@login_required
def admin_hse_environmental():
    if current_user.role not in ["admin", "admin_hse"]:
        return redirect(url_for("employee_hse_dashboard"))
    return render_template("admin_hse_environmental.html", current_year=datetime.now().year)

@app.route("/hse/admin/medical")
@login_required
def admin_hse_medical():
    if current_user.role not in ["admin", "admin_hse"]:
        return redirect(url_for("employee_hse_dashboard"))
    return render_template("admin_hse_medical.html", current_year=datetime.now().year)

@app.route("/hse/admin/company-dashboard")
@login_required
def hse_company_dashboard():
    if current_user.role not in ["admin", "admin_hse"]:
        return redirect(url_for("employee_hse_dashboard"))
    
    year = request.args.get('year', datetime.now().year)
    
    # Generate monthly trend data for YTD
    monthly_trend = []
    total_violations = 0
    total_near_misses = 0
    total_observations = 0
    
    for month in range(1, 13):
        violations = random.randint(10, 25)
        near_misses = random.randint(4, 17)
        observations = random.randint(1, 10)
        
        monthly_trend.append({
            "month": month,
            "violations": violations,
            "near_misses": near_misses,
            "observations": observations
        })
        
        total_violations += violations
        total_near_misses += near_misses
        total_observations += observations
    
    # Calculate summary metrics
    total_events = total_violations + total_near_misses + total_observations
    high_percent = 25.9  # Sample data
    closed_percent = 41.0  # Sample data
    avg_days_to_close = 0.0  # Sample data
    
    return render_template("hse_company_dashboard.html",
                         year=year,
                         monthly_trend=monthly_trend,
                         total_violations=total_violations,
                         total_near_misses=total_near_misses,
                         total_observations=total_observations,
                         high_percent=high_percent,
                         closed_percent=closed_percent,
                         avg_days_to_close=avg_days_to_close)

@app.route("/hse/employee")
@login_required
def employee_hse_dashboard():
    return render_template("employee_hse_dashboard.html", current_year=datetime.now().year)

# ==================== MAIN ====================

if __name__ == "__main__":
    # Initialize database and generate dummy data
    init_database()
    generate_dummy_data()
    
    # Run the application
    app.run(debug=True, host="0.0.0.0", port=5000)

