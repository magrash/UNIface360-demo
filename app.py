# from flask import Flask, render_template
# import sqlite3

# app = Flask(__name__)

# @app.route("/")
# def emergency_status():
#     conn = sqlite3.connect("tracking.db")
#     cursor = conn.execute("SELECT name, floor, MAX(time) as last_seen FROM logs GROUP BY name")
#     people = [{"name": row[0], "floor": row[1], "last_seen": row[2], "status": "Present"} for row in cursor]
#     conn.close()
#     return render_template("status.html", people=people)

# if __name__ == "__main__":
#     app.run(debug=True, host="0.0.0.0", port=5000)






# version 2


# from flask import Flask, render_template, send_from_directory
# import sqlite3
# from os.path import basename

# app = Flask(__name__)
# app.jinja_env.filters['basename'] = basename

# @app.route("/")
# def emergency_status():
#     conn = sqlite3.connect("tracking.db")
#     cursor = conn.execute("SELECT name, floor, MAX(time) as last_seen, image_path FROM logs GROUP BY name")
#     people = [{"name": row[0], "floor": row[1], "last_seen": row[2], "image_path": row[3]} for row in cursor]
#     conn.close()
#     return render_template("status.html", people=people)

# @app.route("/evidence/<path:filename>")
# def serve_evidence(filename):
#     return send_from_directory("evidence", filename)

# if __name__ == "__main__":
#     app.run(debug=True, host="0.0.0.0", port=5000)




from flask import Flask, render_template, send_from_directory, request, redirect, url_for, session, flash
import sqlite3
from os.path import basename

app = Flask(__name__)
app.jinja_env.filters['basename'] = basename
app.secret_key = "change-this-secret"

# Demo users (frontend testing)
USERS = {
    "admin": {"password": "admin123", "role": "admin"},
    "employee": {"password": "emp123", "role": "employee"}
}

@app.route("/")
def emergency_status():
    conn = sqlite3.connect("tracking.db")
    cursor = conn.execute("SELECT name, floor, MAX(time) as last_seen, image_path FROM logs GROUP BY name")
    people = [{"name": row[0], "floor": row[1], "last_seen": row[2], "image_path": row[3]} for row in cursor]
    conn.close()
    return render_template("status.html", people=people)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = USERS.get(username)
        if user and user["password"] == password:
            session["username"] = username
            session["role"] = user["role"]
            flash("Logged in successfully", "success")
            if user["role"] == "admin":
                return redirect(url_for("admin_hse_dashboard"))
            return redirect(url_for("employee_hse_dashboard"))
        flash("Invalid credentials", "error")
    return render_template("login_2.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out", "success")
    return redirect(url_for("login"))

def login_required(role=None):
    def wrapper(fn):
        def inner(*args, **kwargs):
            if not session.get("username"):
                return redirect(url_for("login"))
            if role and session.get("role") != role:
                return redirect(url_for("login"))
            return fn(*args, **kwargs)
        inner.__name__ = fn.__name__
        return inner
    return wrapper

@app.route("/admin")
@login_required(role="admin")
def admin_dashboard():
    return render_template("admin_dashboard.html")

@app.route("/employee")
@login_required(role="employee")
def employee_dashboard():
    # Backward compatibility; go to HSE Employee dashboard
    return redirect(url_for("employee_hse_dashboard"))

# ---------------- HSE Dashboards ----------------
from datetime import datetime

@app.route("/hse/admin")
@login_required(role="admin")
def admin_hse_dashboard():
    return render_template("admin_hse_dashboard.html", current_year=datetime.now().year)

@app.route("/hse/employee")
@login_required(role="employee")
def employee_hse_dashboard():
    return render_template("employee_hse_dashboard.html", current_year=datetime.now().year)

# Quick access demo routes
@app.route("/login/admin")
def quick_login_admin():
    session["username"] = "admin"
    session["role"] = "admin"
    return redirect(url_for("admin_hse_dashboard"))

@app.route("/login/employee")
def quick_login_employee():
    session["username"] = "employee"
    session["role"] = "employee"
    return redirect(url_for("employee_hse_dashboard"))

@app.route("/logs/<name>")
def person_logs(name):
    conn = sqlite3.connect("tracking.db")
    cursor = conn.execute("SELECT name, floor, time, image_path FROM logs WHERE name = ? ORDER BY time DESC", (name,))
    logs = [{"name": row[0], "floor": row[1], "time": row[2], "image_path": row[3]} for row in cursor]
    conn.close()
    return render_template("person_logs.html", name=name, logs=logs)

@app.route("/evidence/<path:filename>")
def serve_evidence(filename):
    return send_from_directory("evidence", filename)

# ---------------- Admin Pages ----------------
@app.route("/admin/approvals")
@login_required(role="admin")
def admin_approvals():
    return render_template("admin_approvals.html")

@app.route("/admin/employees")
@login_required(role="admin")
def admin_employees():
    return render_template("admin_employees.html")

@app.route("/admin/settings")
@login_required(role="admin")
def admin_settings():
    return render_template("admin_settings.html")

@app.route("/profile")
@login_required()
def profile():
    return render_template("profile.html")

# ---------------- HR Module Routes ----------------
@app.route("/hr")
@login_required(role="admin")
def hr_home():
    return render_template("hr/index.html")

@app.route("/hr/employees")
@login_required(role="admin")
def hr_employees():
    return render_template("hr/employees/index.html")

@app.route("/hr/departments")
@login_required(role="admin")
def hr_departments():
    return render_template("hr/departments/index.html")

@app.route("/hr/recruitment")
@login_required(role="admin")
def hr_recruitment():
    return render_template("hr/recruitment/index.html")

@app.route("/hr/attendance")
@login_required(role="admin")
def hr_attendance():
    return render_template("hr/attendance/index.html")

@app.route("/hr/leaves")
@login_required(role="admin")
def hr_leaves():
    return render_template("hr/leaves/index.html")

@app.route("/hr/payroll")
@login_required(role="admin")
def hr_payroll():
    return render_template("hr/payroll/index.html")

@app.route("/hr/compensation")
@login_required(role="admin")
def hr_compensation():
    return render_template("hr/compensation/index.html")

@app.route("/hr/performance")
@login_required(role="admin")
def hr_performance():
    return render_template("hr/performance/index.html")

@app.route("/hr/training")
@login_required(role="admin")
def hr_training():
    return render_template("hr/training/index.html")

@app.route("/hr/hse")
@login_required(role="admin")
def hr_hse():
    return render_template("hr/hse/index.html")

@app.route("/hr/sites")
@login_required(role="admin")
def hr_sites():
    return render_template("hr/sites/index.html")

@app.route("/hr/access")
@login_required(role="admin")
def hr_access():
    return render_template("hr/access/index.html")

@app.route("/hr/reports")
@login_required(role="admin")
def hr_reports():
    return render_template("hr/reports/index.html")

# ---------------- Unauthorized Area Dashboard Routes ---------------- 
@app.route("/unauthorized")
@app.route("/unauthorized/")
@login_required(role="admin")
def unauthorized_home():
    return render_template("unauthorized/index.html")

@app.route("/unauthorized/violations")
@login_required(role="admin")
def unauthorized_violations():
    return render_template("unauthorized/violations.html")

@app.route("/unauthorized/unauthorized-areas")
@login_required(role="admin")
def unauthorized_areas():
    return render_template("unauthorized/unauthorized-areas.html")

@app.route("/unauthorized/violations-by-person")
@login_required(role="admin")
def unauthorized_violations_by_person():
    return render_template("unauthorized/violations-by-person.html")

@app.route("/unauthorized/violations-by-department")
@login_required(role="admin")
def unauthorized_violations_by_department():
    return render_template("unauthorized/violations-by-department.html")

@app.route("/unauthorized/violations-by-location")
@login_required(role="admin")
def unauthorized_violations_by_location():
    return render_template("unauthorized/violations-by-location.html")

@app.route("/unauthorized/risk-analysis")
@login_required(role="admin")
def unauthorized_risk_analysis():
    return render_template("unauthorized/risk-analysis.html")

@app.route("/unauthorized/daily-log")
@login_required(role="admin")
def unauthorized_daily_log():
    return render_template("unauthorized/daily-log.html")

@app.route("/unauthorized/incident-reporting")
@login_required(role="admin")
def unauthorized_incident_reporting():
    return render_template("unauthorized/incident-reporting.html")

@app.route("/unauthorized/investigations")
@login_required(role="admin")
def unauthorized_investigations():
    return render_template("unauthorized/investigations.html")

@app.route("/unauthorized/corrective-actions")
@login_required(role="admin")
def unauthorized_corrective_actions():
    return render_template("unauthorized/corrective-actions.html")

@app.route("/unauthorized/training-needs")
@login_required(role="admin")
def unauthorized_training_needs():
    return render_template("unauthorized/training-needs.html")

@app.route("/unauthorized/compliance-score")
@login_required(role="admin")
def unauthorized_compliance_score():
    return render_template("unauthorized/compliance-score.html")

@app.route("/unauthorized/policies")
@login_required(role="admin")
def unauthorized_policies():
    return render_template("unauthorized/policies.html")

@app.route("/unauthorized/security-log")
@login_required(role="admin")
def unauthorized_security_log():
    return render_template("unauthorized/security-log.html")

@app.route("/unauthorized/roles-permissions")
@login_required(role="admin")
def unauthorized_roles_permissions():
    return render_template("unauthorized/roles-permissions.html")

@app.route("/unauthorized/reports")
@login_required(role="admin")
def unauthorized_reports():
    return render_template("unauthorized/reports.html")

@app.route("/unauthorized/settings")
@login_required(role="admin")
def unauthorized_settings():
    return render_template("unauthorized/settings.html")

@app.errorhandler(404)
def page_not_found(e):
    return render_template("404_2.html"), 404

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)