# HR Dashboard Documentation

## نظرة عامة
نظام إدارة الموارد البشرية (HR) الشامل لشركات النفط والغاز. يتضمن إدارة الموظفين، الحضور، الرواتب، الأداء، التدريب، وغيرها من الوحدات الأساسية.

---

## 📋 جدول المحتويات
1. [الصفحة الرئيسية](#الصفحة-الرئيسية)
2. [إدارة الموظفين](#إدارة-الموظفين)
3. [الأقسام والهيكل التنظيمي](#الأقسام-والهيكل-التنظيمي)
4. [التوظيف](#التوظيف)
5. [الحضور والورديات](#الحضور-والورديات)
6. [الإجازات](#الإجازات)
7. [الرواتب](#الرواتب)
8. [المكافآت والتعويضات](#المكافآت-والتعويضات)
9. [تقييم الأداء](#تقييم-الأداء)
10. [التدريب والشهادات](#التدريب-والشهادات)
11. [إدارة المواقع](#إدارة-المواقع)
12. [الوصول والصلاحيات](#الوصول-والصلاحيات)
13. [التقارير](#التقارير)

---

## 1. الصفحة الرئيسية

### Route
```
GET /hr
GET /hr/
```

### Function Name
```python
hr_home()
```

### Template Path
```
templates/hr/index.html
```

### الوصف
الصفحة الرئيسية لداشبورد HR تعرض نظرة عامة على إحصائيات الموارد البشرية الرئيسية.

### المحتوى
- KPIs رئيسية (عدد الموظفين، الحضور اليومي، الإجازات المعلقة، الوظائف الشاغرة)
- إحصائيات الحضور (نسبة الحضور، الغياب، التأخير)
- إحصائيات الإجازات (المستخدمة، المتبقية، المعلقة)
- أحدث التعيينات
- المهام المعلقة
- إشعارات مهمة

### البيانات المطلوبة من الداتابيس

#### الجداول المطلوبة:
1. **employees** - جدول الموظفين
2. **attendance** - جدول الحضور
3. **leaves** - جدول الإجازات
4. **job_postings** - جدول الوظائف الشاغرة
5. **departments** - جدول الأقسام

#### الريليشنز:
- `employees.department_id` → `departments.id`
- `attendance.employee_id` → `employees.id`
- `leaves.employee_id` → `employees.id`

#### البيانات المطلوبة:
```sql
-- عدد الموظفين الإجمالي
SELECT COUNT(*) FROM employees WHERE status = 'active'

-- الحضور اليومي
SELECT COUNT(*) FROM attendance 
WHERE date = CURRENT_DATE AND status = 'present'

-- الإجازات المعلقة
SELECT COUNT(*) FROM leaves 
WHERE status = 'pending'

-- الوظائف الشاغرة
SELECT COUNT(*) FROM job_postings 
WHERE status = 'open'

-- نسبة الحضور الشهرية
SELECT 
    COUNT(CASE WHEN status = 'present' THEN 1 END) * 100.0 / COUNT(*) as attendance_rate
FROM attendance 
WHERE date >= DATE('now', 'start of month')

-- الإجازات المستخدمة والمتبقية
SELECT 
    SUM(used_days) as used,
    SUM(total_days - used_days) as remaining
FROM leave_balances 
WHERE employee_id IN (SELECT id FROM employees WHERE status = 'active')

-- أحدث التعيينات
SELECT e.*, d.name as department_name 
FROM employees e
LEFT JOIN departments d ON e.department_id = d.id
ORDER BY e.hire_date DESC 
LIMIT 5
```

---

## 2. إدارة الموظفين

### Route
```
GET /hr/employees
```

### Function Name
```python
hr_employees()
```

### Template Path
```
templates/hr/employees/index.html
```

### الوصف
صفحة شاملة لإدارة بيانات الموظفين، عرض القوائم، البحث، الفلترة، وإضافة/تعديل/حذف الموظفين.

### المحتوى
- جدول بجميع الموظفين مع معلومات أساسية
- فلترة حسب القسم، الموقع، الحالة
- بحث بالاسم، الرقم الوظيفي، البريد الإلكتروني
- إضافة موظف جديد
- عرض وتعديل بيانات الموظف
- عرض سجل الحضور والإجازات للموظف
- عرض الأداء والتقييمات

### البيانات المطلوبة من الداتابيس

#### الجداول المطلوبة:
1. **employees** - جدول الموظفين الرئيسي
2. **departments** - جدول الأقسام
3. **sites** - جدول المواقع
4. **positions** - جدول المناصب
5. **attendance** - جدول الحضور
6. **leaves** - جدول الإجازات
7. **performance_reviews** - جدول تقييمات الأداء

#### الريليشنز:
- `employees.department_id` → `departments.id`
- `employees.site_id` → `sites.id`
- `employees.position_id` → `positions.id`
- `attendance.employee_id` → `employees.id`
- `leaves.employee_id` → `employees.id`
- `performance_reviews.employee_id` → `employees.id`

#### البيانات المطلوبة:
```sql
-- قائمة جميع الموظفين
SELECT 
    e.*,
    d.name as department_name,
    s.name as site_name,
    p.title as position_title
FROM employees e
LEFT JOIN departments d ON e.department_id = d.id
LEFT JOIN sites s ON e.site_id = s.id
LEFT JOIN positions p ON e.position_id = p.id
WHERE e.status = 'active'
ORDER BY e.name

-- إحصائيات الموظف
SELECT 
    COUNT(DISTINCT a.date) as attendance_days,
    COUNT(DISTINCT l.id) as total_leaves,
    AVG(pr.overall_score) as avg_performance
FROM employees e
LEFT JOIN attendance a ON e.id = a.employee_id AND a.date >= DATE('now', '-30 days')
LEFT JOIN leaves l ON e.id = l.employee_id
LEFT JOIN performance_reviews pr ON e.id = pr.employee_id
WHERE e.id = ?
```

---

## 3. الأقسام والهيكل التنظيمي

### Route
```
GET /hr/departments
```

### Function Name
```python
hr_departments()
```

### Template Path
```
templates/hr/departments/index.html
```

### الوصف
صفحة لإدارة الأقسام والهيكل التنظيمي للشركة، عرض الشجرة التنظيمية، إدارة الأقسام والمناصب.

### المحتوى
- شجرة تنظيمية تفاعلية
- قائمة الأقسام مع التفاصيل
- إحصائيات لكل قسم (عدد الموظفين، الميزانية، الأداء)
- إضافة/تعديل/حذف أقسام
- إدارة المناصب داخل كل قسم
- هيكل الإدارة (Managers, Supervisors)

### البيانات المطلوبة من الداتابيس

#### الجداول المطلوبة:
1. **departments** - جدول الأقسام
2. **employees** - جدول الموظفين
3. **positions** - جدول المناصب
4. **department_budgets** - جدول ميزانيات الأقسام

#### الريليشنز:
- `departments.parent_department_id` → `departments.id` (self-referencing)
- `departments.manager_id` → `employees.id`
- `employees.department_id` → `departments.id`
- `positions.department_id` → `departments.id`

#### البيانات المطلوبة:
```sql
-- قائمة الأقسام مع الهيكل التنظيمي
SELECT 
    d.*,
    parent.name as parent_department_name,
    m.name as manager_name,
    COUNT(e.id) as employee_count
FROM departments d
LEFT JOIN departments parent ON d.parent_department_id = parent.id
LEFT JOIN employees m ON d.manager_id = m.id
LEFT JOIN employees e ON e.department_id = d.id AND e.status = 'active'
GROUP BY d.id
ORDER BY d.name

-- إحصائيات القسم
SELECT 
    d.id,
    COUNT(e.id) as total_employees,
    AVG(e.salary) as avg_salary,
    SUM(db.budget_amount) as total_budget
FROM departments d
LEFT JOIN employees e ON d.id = e.department_id AND e.status = 'active'
LEFT JOIN department_budgets db ON d.id = db.department_id AND db.year = YEAR(CURRENT_DATE)
WHERE d.id = ?
GROUP BY d.id
```

---

## 4. التوظيف

### Route
```
GET /hr/recruitment
```

### Function Name
```python
hr_recruitment()
```

### Template Path
```
templates/hr/recruitment/index.html
```

### الوصف
صفحة إدارة عملية التوظيف من نشر الوظائف، استقبال الطلبات، المقابلات، حتى التعيين.

### المحتوى
- قائمة الوظائف الشاغرة
- طلبات التوظيف (Applications)
- حالة كل طلب (Pending, Interview, Accepted, Rejected)
- جدول المقابلات
- تقييم المرشحين
- عرض السيرة الذاتية والملفات المرفقة

### البيانات المطلوبة من الداتابيس

#### الجداول المطلوبة:
1. **job_postings** - جدول الوظائف الشاغرة
2. **job_applications** - جدول طلبات التوظيف
3. **interviews** - جدول المقابلات
4. **candidates** - جدول المرشحين
5. **departments** - جدول الأقسام
6. **positions** - جدول المناصب

#### الريليشنز:
- `job_postings.department_id` → `departments.id`
- `job_postings.position_id` → `positions.id`
- `job_applications.job_posting_id` → `job_postings.id`
- `job_applications.candidate_id` → `candidates.id`
- `interviews.application_id` → `job_applications.id`

#### البيانات المطلوبة:
```sql
-- الوظائف الشاغرة
SELECT 
    jp.*,
    d.name as department_name,
    p.title as position_title,
    COUNT(ja.id) as application_count
FROM job_postings jp
LEFT JOIN departments d ON jp.department_id = d.id
LEFT JOIN positions p ON jp.position_id = p.id
LEFT JOIN job_applications ja ON jp.id = ja.job_posting_id
WHERE jp.status = 'open'
GROUP BY jp.id
ORDER BY jp.posted_date DESC

-- طلبات التوظيف
SELECT 
    ja.*,
    c.name as candidate_name,
    c.email as candidate_email,
    c.phone as candidate_phone,
    jp.title as job_title,
    d.name as department_name
FROM job_applications ja
LEFT JOIN candidates c ON ja.candidate_id = c.id
LEFT JOIN job_postings jp ON ja.job_posting_id = jp.id
LEFT JOIN departments d ON jp.department_id = d.id
ORDER BY ja.applied_date DESC

-- المقابلات القادمة
SELECT 
    i.*,
    c.name as candidate_name,
    jp.title as job_title,
    e.name as interviewer_name
FROM interviews i
LEFT JOIN job_applications ja ON i.application_id = ja.id
LEFT JOIN candidates c ON ja.candidate_id = c.id
LEFT JOIN job_postings jp ON ja.job_posting_id = jp.id
LEFT JOIN employees e ON i.interviewer_id = e.id
WHERE i.interview_date >= CURRENT_DATE
ORDER BY i.interview_date ASC
```

---

## 5. الحضور والورديات

### Route
```
GET /hr/attendance
```

### Function Name
```python
hr_attendance()
```

### Template Path
```
templates/hr/attendance/index.html
```

### الوصف
صفحة إدارة الحضور والانصراف، الورديات، التأخير، الغياب، مع إمكانية التسجيل اليدوي والتصحيح.

### المحتوى
- سجل الحضور اليومي
- إحصائيات الحضور (نسبة الحضور، التأخير، الغياب)
- جدول الورديات
- تسجيل حضور/انصراف
- طلبات تصحيح الحضور
- تقارير الحضور (يومي، أسبوعي، شهري)

### البيانات المطلوبة من الداتابيس

#### الجداول المطلوبة:
1. **attendance** - جدول الحضور الرئيسي
2. **employees** - جدول الموظفين
3. **shifts** - جدول الورديات
4. **attendance_corrections** - جدول طلبات تصحيح الحضور
5. **departments** - جدول الأقسام

#### الريليشنز:
- `attendance.employee_id` → `employees.id`
- `attendance.shift_id` → `shifts.id`
- `employees.department_id` → `departments.id`
- `attendance_corrections.attendance_id` → `attendance.id`
- `attendance_corrections.approved_by` → `employees.id`

#### البيانات المطلوبة:
```sql
-- الحضور اليومي
SELECT 
    a.*,
    e.name as employee_name,
    e.employee_number,
    d.name as department_name,
    s.name as shift_name,
    s.start_time,
    s.end_time
FROM attendance a
LEFT JOIN employees e ON a.employee_id = e.id
LEFT JOIN departments d ON e.department_id = d.id
LEFT JOIN shifts s ON a.shift_id = s.id
WHERE a.date = CURRENT_DATE
ORDER BY a.check_in_time

-- إحصائيات الحضور الشهرية
SELECT 
    e.id,
    e.name,
    COUNT(CASE WHEN a.status = 'present' THEN 1 END) as present_days,
    COUNT(CASE WHEN a.status = 'absent' THEN 1 END) as absent_days,
    COUNT(CASE WHEN a.status = 'late' THEN 1 END) as late_days,
    AVG(a.work_hours) as avg_work_hours
FROM employees e
LEFT JOIN attendance a ON e.id = a.employee_id 
    AND a.date >= DATE('now', 'start of month')
    AND a.date <= DATE('now', 'end of month')
WHERE e.status = 'active'
GROUP BY e.id, e.name

-- طلبات تصحيح الحضور
SELECT 
    ac.*,
    a.date as attendance_date,
    e.name as employee_name,
    approver.name as approver_name
FROM attendance_corrections ac
LEFT JOIN attendance a ON ac.attendance_id = a.id
LEFT JOIN employees e ON a.employee_id = e.id
LEFT JOIN employees approver ON ac.approved_by = approver.id
WHERE ac.status = 'pending'
ORDER BY ac.requested_date DESC
```

---

## 6. الإجازات

### Route
```
GET /hr/leaves
```

### Function Name
```python
hr_leaves()
```

### Template Path
```
templates/hr/leaves/index.html
```

### الوصف
صفحة إدارة طلبات الإجازات، الموافقات، رصيد الإجازات، وأنواع الإجازات المختلفة.

### المحتوى
- قائمة طلبات الإجازات (Pending, Approved, Rejected)
- رصيد الإجازات لكل موظف
- أنواع الإجازات (Annual, Sick, Emergency, etc.)
- تقويم الإجازات
- إحصائيات الإجازات
- طلبات الإجازات المعلقة للموافقة

### البيانات المطلوبة من الداتابيس

#### الجداول المطلوبة:
1. **leaves** - جدول طلبات الإجازات
2. **leave_balances** - جدول رصيد الإجازات
3. **leave_types** - جدول أنواع الإجازات
4. **employees** - جدول الموظفين
5. **departments** - جدول الأقسام

#### الريليشنز:
- `leaves.employee_id` → `employees.id`
- `leaves.leave_type_id` → `leave_types.id`
- `leaves.approved_by` → `employees.id`
- `leave_balances.employee_id` → `employees.id`
- `leave_balances.leave_type_id` → `leave_types.id`
- `employees.department_id` → `departments.id`

#### البيانات المطلوبة:
```sql
-- طلبات الإجازات
SELECT 
    l.*,
    e.name as employee_name,
    e.employee_number,
    d.name as department_name,
    lt.name as leave_type_name,
    lt.is_paid,
    approver.name as approver_name
FROM leaves l
LEFT JOIN employees e ON l.employee_id = e.id
LEFT JOIN departments d ON e.department_id = d.id
LEFT JOIN leave_types lt ON l.leave_type_id = lt.id
LEFT JOIN employees approver ON l.approved_by = approver.id
ORDER BY l.start_date DESC

-- رصيد الإجازات
SELECT 
    lb.*,
    e.name as employee_name,
    lt.name as leave_type_name,
    (lb.total_days - lb.used_days) as remaining_days
FROM leave_balances lb
LEFT JOIN employees e ON lb.employee_id = e.id
LEFT JOIN leave_types lt ON lb.leave_type_id = lt.id
WHERE e.status = 'active'
ORDER BY e.name, lt.name

-- الإجازات في فترة معينة (للتقويم)
SELECT 
    l.*,
    e.name as employee_name,
    d.name as department_name,
    lt.name as leave_type_name,
    lt.color
FROM leaves l
LEFT JOIN employees e ON l.employee_id = e.id
LEFT JOIN departments d ON e.department_id = d.id
LEFT JOIN leave_types lt ON l.leave_type_id = lt.id
WHERE l.status = 'approved'
    AND l.start_date <= ? 
    AND l.end_date >= ?
ORDER BY l.start_date
```

---

## 7. الرواتب

### Route
```
GET /hr/payroll
```

### Function Name
```python
hr_payroll()
```

### Template Path
```
templates/hr/payroll/index.html
```

### الوصف
صفحة إدارة الرواتب، حساب الرواتب الشهرية، الاستقطاعات، المكافآت، وكشوف الرواتب.

### المحتوى
- قائمة الرواتب الشهرية
- تفاصيل الراتب (الأساسي، البدلات، الاستقطاعات)
- كشوف الرواتب (PDF)
- إحصائيات الرواتب
- تاريخ الرواتب
- طلبات تعديل الراتب

### البيانات المطلوبة من الداتابيس

#### الجداول المطلوبة:
1. **payroll** - جدول الرواتب الشهرية
2. **employees** - جدول الموظفين
3. **salary_components** - جدول مكونات الراتب (Basic, Allowances, Deductions)
4. **payroll_items** - جدول بنود الراتب لكل موظف
5. **departments** - جدول الأقسام

#### الريليشنز:
- `payroll.employee_id` → `employees.id`
- `payroll_items.payroll_id` → `payroll.id`
- `payroll_items.component_id` → `salary_components.id`
- `employees.department_id` → `departments.id`

#### البيانات المطلوبة:
```sql
-- الرواتب الشهرية
SELECT 
    p.*,
    e.name as employee_name,
    e.employee_number,
    d.name as department_name,
    SUM(CASE WHEN sc.type = 'earning' THEN pi.amount ELSE 0 END) as total_earnings,
    SUM(CASE WHEN sc.type = 'deduction' THEN pi.amount ELSE 0 END) as total_deductions,
    (SUM(CASE WHEN sc.type = 'earning' THEN pi.amount ELSE 0 END) - 
     SUM(CASE WHEN sc.type = 'deduction' THEN pi.amount ELSE 0 END)) as net_salary
FROM payroll p
LEFT JOIN employees e ON p.employee_id = e.id
LEFT JOIN departments d ON e.department_id = d.id
LEFT JOIN payroll_items pi ON p.id = pi.payroll_id
LEFT JOIN salary_components sc ON pi.component_id = sc.id
WHERE p.payroll_month = ? AND p.payroll_year = ?
GROUP BY p.id
ORDER BY e.name

-- تفاصيل الراتب
SELECT 
    pi.*,
    sc.name as component_name,
    sc.type as component_type,
    sc.is_taxable
FROM payroll_items pi
LEFT JOIN salary_components sc ON pi.component_id = sc.id
WHERE pi.payroll_id = ?
ORDER BY sc.type, sc.name

-- إحصائيات الرواتب
SELECT 
    COUNT(DISTINCT p.employee_id) as total_employees,
    SUM(pi.amount) FILTER (WHERE sc.type = 'earning') as total_earnings,
    SUM(pi.amount) FILTER (WHERE sc.type = 'deduction') as total_deductions,
    AVG(pi.amount) FILTER (WHERE sc.type = 'earning') as avg_salary
FROM payroll p
LEFT JOIN payroll_items pi ON p.id = pi.payroll_id
LEFT JOIN salary_components sc ON pi.component_id = sc.id
WHERE p.payroll_month = ? AND p.payroll_year = ?
```

---

## 8. المكافآت والتعويضات

### Route
```
GET /hr/compensation
```

### Function Name
```python
hr_compensation()
```

### Template Path
```
templates/hr/compensation/index.html
```

### الوصف
صفحة إدارة المكافآت، البدلات، الحوافز، والمزايا الإضافية للموظفين.

### المحتوى
- قائمة المكافآت والبدلات
- أنواع التعويضات (Performance Bonus, Overtime, Travel Allowance, etc.)
- إحصائيات التعويضات
- تاريخ المكافآت
- مقارنة التعويضات بين الأقسام

### البيانات المطلوبة من الداتابيس

#### الجداول المطلوبة:
1. **compensations** - جدول التعويضات والمكافآت
2. **compensation_types** - جدول أنواع التعويضات
3. **employees** - جدول الموظفين
4. **departments** - جدول الأقسام
5. **performance_reviews** - جدول تقييمات الأداء (للمكافآت المرتبطة بالأداء)

#### الريليشنز:
- `compensations.employee_id` → `employees.id`
- `compensations.compensation_type_id` → `compensation_types.id`
- `compensations.approved_by` → `employees.id`
- `employees.department_id` → `departments.id`
- `compensations.performance_review_id` → `performance_reviews.id` (optional)

#### البيانات المطلوبة:
```sql
-- قائمة التعويضات
SELECT 
    c.*,
    e.name as employee_name,
    e.employee_number,
    d.name as department_name,
    ct.name as compensation_type_name,
    ct.category,
    approver.name as approver_name
FROM compensations c
LEFT JOIN employees e ON c.employee_id = e.id
LEFT JOIN departments d ON e.department_id = d.id
LEFT JOIN compensation_types ct ON c.compensation_type_id = ct.id
LEFT JOIN employees approver ON c.approved_by = approver.id
WHERE c.status = 'approved'
ORDER BY c.date DESC

-- إحصائيات التعويضات
SELECT 
    ct.name as compensation_type,
    ct.category,
    COUNT(c.id) as total_count,
    SUM(c.amount) as total_amount,
    AVG(c.amount) as avg_amount
FROM compensations c
LEFT JOIN compensation_types ct ON c.compensation_type_id = ct.id
WHERE c.status = 'approved'
    AND c.date >= DATE('now', 'start of year')
GROUP BY ct.id, ct.name, ct.category
ORDER BY total_amount DESC

-- التعويضات حسب القسم
SELECT 
    d.name as department_name,
    COUNT(c.id) as compensation_count,
    SUM(c.amount) as total_compensation,
    AVG(c.amount) as avg_compensation
FROM compensations c
LEFT JOIN employees e ON c.employee_id = e.id
LEFT JOIN departments d ON e.department_id = d.id
WHERE c.status = 'approved'
    AND c.date >= DATE('now', 'start of year')
GROUP BY d.id, d.name
ORDER BY total_compensation DESC
```

---

## 9. تقييم الأداء

### Route
```
GET /hr/performance
```

### Function Name
```python
hr_performance()
```

### Template Path
```
templates/hr/performance/index.html
```

### الوصف
صفحة إدارة تقييمات الأداء، الأهداف، KPIs، والتقييمات الدورية للموظفين.

### المحتوى
- قائمة تقييمات الأداء
- الأهداف والـ KPIs
- تقييمات ربع سنوية/سنوية
- مقارنة الأداء بين الموظفين
- خطط التطوير
- إحصائيات الأداء

### البيانات المطلوبة من الداتابيس

#### الجداول المطلوبة:
1. **performance_reviews** - جدول تقييمات الأداء
2. **performance_goals** - جدول الأهداف
3. **performance_kpis** - جدول مؤشرات الأداء
4. **employees** - جدول الموظفين
5. **departments** - جدول الأقسام
6. **reviewers** - جدول المقيمين

#### الريليشنز:
- `performance_reviews.employee_id` → `employees.id`
- `performance_reviews.reviewer_id` → `employees.id`
- `performance_goals.employee_id` → `employees.id`
- `performance_kpis.review_id` → `performance_reviews.id`
- `employees.department_id` → `departments.id`

#### البيانات المطلوبة:
```sql
-- تقييمات الأداء
SELECT 
    pr.*,
    e.name as employee_name,
    e.employee_number,
    d.name as department_name,
    reviewer.name as reviewer_name,
    COUNT(pg.id) as goals_count,
    AVG(pg.achievement_percentage) as avg_goal_achievement
FROM performance_reviews pr
LEFT JOIN employees e ON pr.employee_id = e.id
LEFT JOIN departments d ON e.department_id = d.id
LEFT JOIN employees reviewer ON pr.reviewer_id = reviewer.id
LEFT JOIN performance_goals pg ON e.id = pg.employee_id 
    AND pg.review_period = pr.review_period
WHERE pr.review_period = ?
GROUP BY pr.id
ORDER BY pr.overall_score DESC

-- الأهداف
SELECT 
    pg.*,
    e.name as employee_name,
    (pg.achieved_value * 100.0 / pg.target_value) as achievement_percentage
FROM performance_goals pg
LEFT JOIN employees e ON pg.employee_id = e.id
WHERE pg.review_period = ?
    AND pg.employee_id = ?
ORDER BY pg.priority

-- KPIs
SELECT 
    pk.*,
    pr.review_period,
    e.name as employee_name
FROM performance_kpis pk
LEFT JOIN performance_reviews pr ON pk.review_id = pr.id
LEFT JOIN employees e ON pr.employee_id = e.id
WHERE pk.review_id = ?
ORDER BY pk.kpi_name
```

---

## 10. التدريب والشهادات

### Route
```
GET /hr/training
```

### Function Name
```python
hr_training()
```

### Template Path
```
templates/hr/training/index.html
```

### الوصف
صفحة إدارة برامج التدريب، الدورات، الشهادات، ومتابعة تقدم الموظفين في التدريب.

### المحتوى
- قائمة برامج التدريب
- الدورات المتاحة
- سجل التدريب للموظفين
- الشهادات والتراخيص
- متطلبات التدريب حسب المنصب
- تقارير التدريب

### البيانات المطلوبة من الداتابيس

#### الجداول المطلوبة:
1. **training_programs** - جدول برامج التدريب
2. **training_courses** - جدول الدورات
3. **employee_training** - جدول سجل تدريب الموظفين
4. **certifications** - جدول الشهادات
5. **employees** - جدول الموظفين
6. **departments** - جدول الأقسام
7. **position_requirements** - جدول متطلبات المناصب

#### الريليشنز:
- `employee_training.employee_id` → `employees.id`
- `employee_training.course_id` → `training_courses.id`
- `training_courses.program_id` → `training_programs.id`
- `certifications.employee_id` → `employees.id`
- `position_requirements.position_id` → `positions.id`
- `position_requirements.course_id` → `training_courses.id`
- `employees.department_id` → `departments.id`

#### البيانات المطلوبة:
```sql
-- برامج التدريب
SELECT 
    tp.*,
    COUNT(DISTINCT tc.id) as courses_count,
    COUNT(DISTINCT et.employee_id) as enrolled_employees
FROM training_programs tp
LEFT JOIN training_courses tc ON tp.id = tc.program_id
LEFT JOIN employee_training et ON tc.id = et.course_id
GROUP BY tp.id
ORDER BY tp.start_date DESC

-- الدورات
SELECT 
    tc.*,
    tp.name as program_name,
    COUNT(et.id) as enrolled_count,
    COUNT(CASE WHEN et.status = 'completed' THEN 1 END) as completed_count
FROM training_courses tc
LEFT JOIN training_programs tp ON tc.program_id = tp.id
LEFT JOIN employee_training et ON tc.id = et.course_id
GROUP BY tc.id
ORDER BY tc.start_date DESC

-- سجل التدريب للموظف
SELECT 
    et.*,
    tc.name as course_name,
    tc.duration,
    tp.name as program_name,
    et.status,
    et.completion_date,
    et.score
FROM employee_training et
LEFT JOIN training_courses tc ON et.course_id = tc.id
LEFT JOIN training_programs tp ON tc.program_id = tp.id
WHERE et.employee_id = ?
ORDER BY et.enrollment_date DESC

-- الشهادات
SELECT 
    c.*,
    e.name as employee_name,
    e.employee_number,
    DATEDIFF(c.expiry_date, CURRENT_DATE) as days_until_expiry
FROM certifications c
LEFT JOIN employees e ON c.employee_id = e.id
WHERE c.status = 'active'
ORDER BY c.expiry_date ASC
```

---

## 11. إدارة المواقع

### Route
```
GET /hr/sites
```

### Function Name
```python
hr_sites()
```

### Template Path
```
templates/hr/sites/index.html
```

### الوصف
صفحة إدارة المواقع المختلفة للشركة (منصات النفط، المكاتب، المستودعات، etc.) والموظفين في كل موقع.

### المحتوى
- قائمة المواقع
- تفاصيل كل موقع (العنوان، السعة، المرافق)
- الموظفين في كل موقع
- إحصائيات المواقع
- خريطة المواقع (إن وجدت)

### البيانات المطلوبة من الداتابيس

#### الجداول المطلوبة:
1. **sites** - جدول المواقع
2. **employees** - جدول الموظفين
3. **departments** - جدول الأقسام
4. **site_facilities** - جدول مرافق المواقع
5. **site_capacity** - جدول سعة المواقع

#### الريليشنز:
- `employees.site_id` → `sites.id`
- `site_facilities.site_id` → `sites.id`
- `site_capacity.site_id` → `sites.id`

#### البيانات المطلوبة:
```sql
-- قائمة المواقع
SELECT 
    s.*,
    COUNT(e.id) as employee_count,
    COUNT(DISTINCT e.department_id) as departments_count
FROM sites s
LEFT JOIN employees e ON s.id = e.site_id AND e.status = 'active'
GROUP BY s.id
ORDER BY s.name

-- تفاصيل الموقع
SELECT 
    s.*,
    GROUP_CONCAT(sf.facility_name) as facilities,
    sc.max_capacity,
    sc.current_occupancy
FROM sites s
LEFT JOIN site_facilities sf ON s.id = sf.site_id
LEFT JOIN site_capacity sc ON s.id = sc.site_id
WHERE s.id = ?
GROUP BY s.id

-- الموظفين في الموقع
SELECT 
    e.*,
    d.name as department_name,
    p.title as position_title
FROM employees e
LEFT JOIN departments d ON e.department_id = d.id
LEFT JOIN positions p ON e.position_id = p.id
WHERE e.site_id = ? AND e.status = 'active'
ORDER BY d.name, e.name
```

---

## 12. الوصول والصلاحيات

### Route
```
GET /hr/access
```

### Function Name
```python
hr_access()
```

### Template Path
```
templates/hr/access/index.html
```

### الوصف
صفحة إدارة صلاحيات الوصول للموظفين، المناطق المسموح بها، البطاقات، والتحكم في الوصول.

### المحتوى
- قائمة صلاحيات الوصول
- المناطق المسموح بها لكل موظف
- سجل الوصول (Access Logs)
- البطاقات والتراخيص
- طلبات الوصول
- إحصائيات الوصول

### البيانات المطلوبة من الداتابيس

#### الجداول المطلوبة:
1. **access_permissions** - جدول صلاحيات الوصول
2. **access_areas** - جدول المناطق
3. **employee_access** - جدول صلاحيات الموظفين
4. **access_logs** - جدول سجل الوصول
5. **access_cards** - جدول البطاقات
6. **employees** - جدول الموظفين

#### الريليشنز:
- `employee_access.employee_id` → `employees.id`
- `employee_access.area_id` → `access_areas.id`
- `access_logs.employee_id` → `employees.id`
- `access_logs.area_id` → `access_areas.id`
- `access_cards.employee_id` → `employees.id`
- `access_permissions.employee_id` → `employees.id`

#### البيانات المطلوبة:
```sql
-- صلاحيات الوصول للموظفين
SELECT 
    ea.*,
    e.name as employee_name,
    e.employee_number,
    aa.name as area_name,
    aa.access_level,
    aa.requires_approval
FROM employee_access ea
LEFT JOIN employees e ON ea.employee_id = e.id
LEFT JOIN access_areas aa ON ea.area_id = aa.id
WHERE e.status = 'active'
ORDER BY e.name, aa.name

-- سجل الوصول
SELECT 
    al.*,
    e.name as employee_name,
    e.employee_number,
    aa.name as area_name,
    CASE 
        WHEN al.access_granted = 1 THEN 'Granted'
        ELSE 'Denied'
    END as access_status
FROM access_logs al
LEFT JOIN employees e ON al.employee_id = e.id
LEFT JOIN access_areas aa ON al.area_id = aa.id
ORDER BY al.access_time DESC
LIMIT 100

-- البطاقات النشطة
SELECT 
    ac.*,
    e.name as employee_name,
    e.employee_number,
    CASE 
        WHEN ac.expiry_date < CURRENT_DATE THEN 'Expired'
        WHEN ac.expiry_date <= DATE('now', '+30 days') THEN 'Expiring Soon'
        ELSE 'Active'
    END as card_status
FROM access_cards ac
LEFT JOIN employees e ON ac.employee_id = e.id
WHERE ac.status = 'active'
ORDER BY ac.expiry_date ASC
```

---

## 13. التقارير

### Route
```
GET /hr/reports
```

### Function Name
```python
hr_reports()
```

### Template Path
```
templates/hr/reports/index.html
```

### الوصف
صفحة التقارير الشاملة لجميع وحدات HR مع إمكانية التصدير (PDF, Excel).

### المحتوى
- تقارير الموظفين
- تقارير الحضور
- تقارير الإجازات
- تقارير الرواتب
- تقارير الأداء
- تقارير التدريب
- تقارير مخصصة

### البيانات المطلوبة من الداتابيس

#### الجداول المطلوبة:
جميع الجداول السابقة حسب نوع التقرير المطلوب.

#### الريليشنز:
جميع الريليشنز المذكورة سابقاً.

#### البيانات المطلوبة:
```sql
-- تقرير شامل للموظفين
SELECT 
    e.*,
    d.name as department_name,
    s.name as site_name,
    p.title as position_title,
    COUNT(DISTINCT a.date) as attendance_days,
    COUNT(DISTINCT l.id) as total_leaves,
    AVG(pr.overall_score) as avg_performance
FROM employees e
LEFT JOIN departments d ON e.department_id = d.id
LEFT JOIN sites s ON e.site_id = s.id
LEFT JOIN positions p ON e.position_id = p.id
LEFT JOIN attendance a ON e.id = a.employee_id 
    AND a.date >= DATE('now', 'start of year')
LEFT JOIN leaves l ON e.id = l.employee_id 
    AND l.start_date >= DATE('now', 'start of year')
LEFT JOIN performance_reviews pr ON e.id = pr.employee_id
    AND pr.review_period = YEAR(CURRENT_DATE)
WHERE e.status = 'active'
GROUP BY e.id
ORDER BY d.name, e.name
```

---

## 📊 هيكل قاعدة البيانات المقترح

### الجداول الرئيسية:

```sql
-- الموظفين
CREATE TABLE employees (
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
    FOREIGN KEY (department_id) REFERENCES departments(id),
    FOREIGN KEY (site_id) REFERENCES sites(id),
    FOREIGN KEY (position_id) REFERENCES positions(id)
);

-- الأقسام
CREATE TABLE departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    parent_department_id INTEGER,
    manager_id INTEGER,
    FOREIGN KEY (parent_department_id) REFERENCES departments(id),
    FOREIGN KEY (manager_id) REFERENCES employees(id)
);

-- المواقع
CREATE TABLE sites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    address TEXT,
    location TEXT,
    capacity INTEGER
);

-- الحضور
CREATE TABLE attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER,
    date DATE,
    check_in_time TIME,
    check_out_time TIME,
    shift_id INTEGER,
    status TEXT, -- 'present', 'absent', 'late'
    work_hours DECIMAL(4,2),
    FOREIGN KEY (employee_id) REFERENCES employees(id),
    FOREIGN KEY (shift_id) REFERENCES shifts(id)
);

-- الإجازات
CREATE TABLE leaves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER,
    leave_type_id INTEGER,
    start_date DATE,
    end_date DATE,
    days INTEGER,
    reason TEXT,
    status TEXT, -- 'pending', 'approved', 'rejected'
    approved_by INTEGER,
    FOREIGN KEY (employee_id) REFERENCES employees(id),
    FOREIGN KEY (leave_type_id) REFERENCES leave_types(id),
    FOREIGN KEY (approved_by) REFERENCES employees(id)
);

-- الرواتب
CREATE TABLE payroll (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER,
    payroll_month INTEGER,
    payroll_year INTEGER,
    gross_salary DECIMAL(10,2),
    net_salary DECIMAL(10,2),
    FOREIGN KEY (employee_id) REFERENCES employees(id)
);
```

---

## 🔐 الصلاحيات

جميع صفحات HR Dashboard تتطلب:
- تسجيل الدخول (`@login_required`)
- صلاحية Admin فقط (`current_user.username == "admin"`)

---

## 📝 ملاحظات

- جميع الصفحات حالياً تعرض بيانات تجريبية (Mock Data)
- يجب ربط الصفحات بقاعدة البيانات الفعلية عند التنفيذ
- يمكن إضافة API endpoints منفصلة للـ AJAX calls
- يجب إضافة Pagination للجداول الكبيرة
- يجب إضافة Search و Filtering متقدم

