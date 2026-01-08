# HR Management System for Oil & Gas Companies

Complete HR management system built with Laravel and SQLite.

## 📁 Project Structure

```
hr-management/
├── app/
│   ├── Http/
│   │   ├── Controllers/
│   │   │   ├── Auth/
│   │   │   ├── EmployeeController.php
│   │   │   ├── AttendanceController.php
│   │   │   ├── DashboardController.php
│   │   │   └── ...
│   │   ├── Middleware/
│   │   │   └── JwtAuth.php
│   │   └── Requests/
│   ├── Models/
│   │   ├── User.php
│   │   ├── Employee.php
│   │   ├── Attendance.php
│   │   └── ...
│   └── Services/
│       ├── AuthService.php
│       ├── EmployeeService.php
│       └── AttendanceService.php
├── database/
│   └── migrations/
│       ├── 2024_01_01_create_users_table.php
│       ├── 2024_01_02_create_employees_table.php
│       └── ...
├── resources/
│   ├── views/
│   │   ├── layouts/
│   │   ├── auth/
│   │   ├── dashboard/
│   │   └── ...
│   └── lang/
│       ├── en/
│       └── ar/
├── routes/
│   ├── web.php
│   └── api.php
└── public/
    └── css/
```

## 🚀 Installation

1. Install Laravel dependencies:
```bash
composer install
```

2. Configure `.env` for SQLite:
```env
DB_CONNECTION=sqlite
DB_DATABASE=/absolute/path/to/database.sqlite
```

3. Run migrations:
```bash
php artisan migrate
```

4. Seed initial data:
```bash
php artisan db:seed
```

## 📦 Core Modules

- ✅ Employee Management
- ✅ Recruitment
- ✅ Attendance & Shifts
- ✅ Leave Management
- ✅ Payroll
- ✅ Benefits & Compensation
- ✅ Performance Appraisal
- ✅ Training & Certification
- ✅ HSE Management
- ✅ Site Management
- ✅ Roles & Permissions
- ✅ Reports & Dashboard

## 🔐 Authentication

JWT-based authentication with role-based access control.

Default admin: `admin@company.com` / `admin123`

## 🌐 Multi-language

Supports Arabic and English with RTL support.

