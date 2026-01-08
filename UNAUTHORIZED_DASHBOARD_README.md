# Unauthorized Area Dashboard Documentation

## نظرة عامة
نظام إدارة المناطق غير المصرح بها ومتابعة المخالفات في شركات النفط والغاز. يتضمن تتبع المخالفات، التحقيقات، الإجراءات التصحيحية، وتحليل المخاطر.

---

## 📋 جدول المحتويات
1. [الصفحة الرئيسية](#الصفحة-الرئيسية)
2. [سجل المخالفات](#سجل-المخالفات)
3. [المناطق غير المصرح بها](#المناطق-غير-المصرح-بها)
4. [المخالفات حسب الشخص](#المخالفات-حسب-الشخص)
5. [المخالفات حسب القسم](#المخالفات-حسب-القسم)
6. [المخالفات حسب الموقع](#المخالفات-حسب-الموقع)
7. [تحليل المخاطر](#تحليل-المخاطر)
8. [السجل اليومي / سجل الورديات](#السجل-اليومي--سجل-الورديات)
9. [الإبلاغ عن الحوادث](#الإبلاغ-عن-الحوادث)
10. [التحقيقات وسبب الجذر](#التحقيقات-وسبب-الجذر)
11. [إدارة الإجراءات التصحيحية](#إدارة-الإجراءات-التصحيحية)
12. [احتياجات التدريب](#احتياجات-التدريب)
13. [نقاط الالتزام](#نقاط-الالتزام)
14. [السياسات وقواعد السلامة](#السياسات-وقواعد-السلامة)
15. [تكامل سجل الأمان](#تكامل-سجل-الأمان)
16. [الأدوار والصلاحيات](#الأدوار-والصلاحيات)
17. [تصدير التقارير](#تصدير-التقارير)
18. [الإعدادات](#الإعدادات)

---

## 1. الصفحة الرئيسية

### Route
```
GET /unauthorized
GET /unauthorized/
```

### Function Name
```python
unauthorized_home()
```

### Template Path
```
templates/unauthorized/index.html
```

### الوصف
الصفحة الرئيسية لداشبورد Unauthorized Area تعرض نظرة عامة على جميع المخالفات والإحصائيات الرئيسية.

### المحتوى
- **KPIs رئيسية:**
  - عدد الحوادث غير المصرح بها اليوم
  - إجمالي الحالات خلال هذا الشهر
  - Top 5 Hot Zones (أخطر أماكن)
  - Top High-Risk Employees (أكثر الموظفين مخالفة)

- **Violations by Department (Pie Chart):** توزيع المخالفات حسب الأقسام
- **Violations by Location (Heatmap):** خريطة حرارية للمواقع
- **Trends (Line Chart):** اتجاهات المخالفات (يومي/أسبوعي/شهري/سنوي)
- **Severity Breakdown (Doughnut Chart):** توزيع المخالفات حسب الخطورة (Low/Medium/High/Critical)

### البيانات المطلوبة من الداتابيس

#### الجداول المطلوبة:
1. **violations** - جدول المخالفات الرئيسي
2. **employees** - جدول الموظفين
3. **departments** - جدول الأقسام
4. **locations** - جدول المواقع
5. **violation_types** - جدول أنواع المخالفات

#### الريليشنز:
- `violations.employee_id` → `employees.id`
- `violations.department_id` → `departments.id`
- `violations.location_id` → `locations.id`
- `violations.violation_type_id` → `violation_types.id`
- `employees.department_id` → `departments.id`

#### البيانات المطلوبة:
```sql
-- عدد الحوادث اليوم
SELECT COUNT(*) as today_violations
FROM violations
WHERE DATE(incident_datetime) = CURRENT_DATE

-- إجمالي الحالات الشهرية
SELECT COUNT(*) as monthly_violations
FROM violations
WHERE YEAR(incident_datetime) = YEAR(CURRENT_DATE)
    AND MONTH(incident_datetime) = MONTH(CURRENT_DATE)

-- Top 5 Hot Zones
SELECT 
    l.name as location_name,
    COUNT(v.id) as violation_count
FROM violations v
LEFT JOIN locations l ON v.location_id = l.id
WHERE v.incident_datetime >= DATE('now', '-30 days')
GROUP BY l.id, l.name
ORDER BY violation_count DESC
LIMIT 5

-- Top High-Risk Employees
SELECT 
    e.name as employee_name,
    e.employee_number,
    COUNT(v.id) as violation_count
FROM violations v
LEFT JOIN employees e ON v.employee_id = e.id
WHERE v.incident_datetime >= DATE('now', '-90 days')
GROUP BY e.id, e.name, e.employee_number
ORDER BY violation_count DESC
LIMIT 5

-- Violations by Department (Pie Chart)
SELECT 
    d.name as department_name,
    COUNT(v.id) as violation_count
FROM violations v
LEFT JOIN departments d ON v.department_id = d.id
WHERE v.incident_datetime >= DATE('now', '-30 days')
GROUP BY d.id, d.name
ORDER BY violation_count DESC

-- Violations by Location (Heatmap Data)
SELECT 
    l.name as location_name,
    l.latitude,
    l.longitude,
    COUNT(v.id) as violation_count,
    AVG(CASE 
        WHEN v.severity = 'Critical' THEN 4
        WHEN v.severity = 'High' THEN 3
        WHEN v.severity = 'Medium' THEN 2
        ELSE 1
    END) as avg_severity_score
FROM violations v
LEFT JOIN locations l ON v.location_id = l.id
WHERE v.incident_datetime >= DATE('now', '-30 days')
GROUP BY l.id, l.name, l.latitude, l.longitude

-- Trends (Line Chart) - Daily
SELECT 
    DATE(incident_datetime) as date,
    COUNT(*) as violation_count
FROM violations
WHERE incident_datetime >= DATE('now', '-7 days')
GROUP BY DATE(incident_datetime)
ORDER BY date

-- Severity Breakdown
SELECT 
    severity,
    COUNT(*) as count
FROM violations
WHERE incident_datetime >= DATE('now', '-30 days')
GROUP BY severity
```

---

## 2. سجل المخالفات

### Route
```
GET /unauthorized/violations
```

### Function Name
```python
unauthorized_violations()
```

### Template Path
```
templates/unauthorized/violations.html
```

### الوصف
صفحة شاملة تعرض جميع المخالفات مع إمكانية الفلترة القوية وعرض تفاصيل كل حادث.

### المحتوى
- جدول بجميع المخالفات مع:
  - نوع المخالفة
  - الشخص المسؤول
  - المكان
  - القسم
  - التاريخ والوقت
  - مستوى الخطورة
  - حالة الحادث (Open / Under Investigation / Closed)

- **فلترة حسب:**
  - النوع
  - القسم
  - الشخص
  - الموقع
  - الخطورة
  - التاريخ
  - الحالة

- زر "View Incident" لعرض التفاصيل الكاملة

- **صفحة تفاصيل الحادث:**
  - وصف الحادث بالتفصيل
  - الصور والفيديوهات
  - الأشخاص المتورطين
  - الإجراءات التي تمت
  - سبب الحادث (RCA – Root Cause Analysis)
  - الإجراءات التصحيحية (Corrective Actions)
  - Manager notes
  - Attachments

### البيانات المطلوبة من الداتابيس

#### الجداول المطلوبة:
1. **violations** - جدول المخالفات الرئيسي
2. **violation_types** - جدول أنواع المخالفات
3. **employees** - جدول الموظفين
4. **departments** - جدول الأقسام
5. **locations** - جدول المواقع
6. **violation_attachments** - جدول المرفقات (صور/فيديو)
7. **violation_witnesses** - جدول الشهود
8. **corrective_actions** - جدول الإجراءات التصحيحية
9. **investigations** - جدول التحقيقات

#### الريليشنز:
- `violations.employee_id` → `employees.id`
- `violations.department_id` → `departments.id`
- `violations.location_id` → `locations.id`
- `violations.violation_type_id` → `violation_types.id`
- `violations.investigation_id` → `investigations.id`
- `violation_attachments.violation_id` → `violations.id`
- `violation_witnesses.violation_id` → `violations.id`
- `violation_witnesses.employee_id` → `employees.id`
- `corrective_actions.violation_id` → `violations.id`

#### البيانات المطلوبة:
```sql
-- قائمة جميع المخالفات
SELECT 
    v.*,
    vt.name as violation_type_name,
    e.name as employee_name,
    e.employee_number,
    d.name as department_name,
    l.name as location_name,
    i.status as investigation_status
FROM violations v
LEFT JOIN violation_types vt ON v.violation_type_id = vt.id
LEFT JOIN employees e ON v.employee_id = e.id
LEFT JOIN departments d ON v.department_id = d.id
LEFT JOIN locations l ON v.location_id = l.id
LEFT JOIN investigations i ON v.investigation_id = i.id
ORDER BY v.incident_datetime DESC

-- تفاصيل حادث معين
SELECT 
    v.*,
    vt.name as violation_type_name,
    vt.description as violation_type_description,
    e.name as employee_name,
    e.employee_number,
    e.email as employee_email,
    d.name as department_name,
    l.name as location_name,
    l.address as location_address,
    i.id as investigation_id,
    i.status as investigation_status
FROM violations v
LEFT JOIN violation_types vt ON v.violation_type_id = vt.id
LEFT JOIN employees e ON v.employee_id = e.id
LEFT JOIN departments d ON v.department_id = d.id
LEFT JOIN locations l ON v.location_id = l.id
LEFT JOIN investigations i ON v.investigation_id = i.id
WHERE v.id = ?

-- مرفقات الحادث
SELECT 
    va.*,
    va.file_path,
    va.file_type,
    va.uploaded_at
FROM violation_attachments va
WHERE va.violation_id = ?
ORDER BY va.uploaded_at

-- الشهود
SELECT 
    vw.*,
    e.name as witness_name,
    e.employee_number,
    e.email as witness_email
FROM violation_witnesses vw
LEFT JOIN employees e ON vw.employee_id = e.id
WHERE vw.violation_id = ?

-- الإجراءات التصحيحية
SELECT 
    ca.*,
    e.name as responsible_name
FROM corrective_actions ca
LEFT JOIN employees e ON ca.responsible_person_id = e.id
WHERE ca.violation_id = ?
ORDER BY ca.created_at
```

---

## 3. المناطق غير المصرح بها

### Route
```
GET /unauthorized/unauthorized-areas
```

### Function Name
```python
unauthorized_areas()
```

### Template Path
```
templates/unauthorized/unauthorized-areas.html
```

### الوصف
صفحة تعرض قائمة المناطق المحظور دخولها مع تفاصيل كل منطقة ومستويات التصريح.

### المحتوى
- قائمة الأماكن غير المصرح بها
- مستويات التصريح لكل مكان (Level 1, 2, 3, etc.)
- الموظفين المسموح لهم بالدخول
- وقت السماح بالدخول (Work Permit Times)
- حالة كل منطقة (Active / Under Maintenance / Restricted)
- إضافة/تعديل/حذف مناطق

### البيانات المطلوبة من الداتابيس

#### الجداول المطلوبة:
1. **unauthorized_areas** - جدول المناطق غير المصرح بها
2. **area_access_levels** - جدول مستويات الوصول
3. **area_authorized_employees** - جدول الموظفين المصرح لهم
4. **work_permits** - جدول تصاريح العمل
5. **employees** - جدول الموظفين
6. **locations** - جدول المواقع

#### الريليشنز:
- `unauthorized_areas.location_id` → `locations.id`
- `area_authorized_employees.area_id` → `unauthorized_areas.id`
- `area_authorized_employees.employee_id` → `employees.id`
- `area_authorized_employees.access_level_id` → `area_access_levels.id`
- `work_permits.area_id` → `unauthorized_areas.id`
- `work_permits.employee_id` → `employees.id`

#### البيانات المطلوبة:
```sql
-- قائمة المناطق غير المصرح بها
SELECT 
    ua.*,
    l.name as location_name,
    l.address,
    COUNT(DISTINCT aae.employee_id) as authorized_employees_count
FROM unauthorized_areas ua
LEFT JOIN locations l ON ua.location_id = l.id
LEFT JOIN area_authorized_employees aae ON ua.id = aae.area_id
WHERE ua.status = 'active'
GROUP BY ua.id
ORDER BY ua.name

-- الموظفين المصرح لهم بمنطقة معينة
SELECT 
    aae.*,
    e.name as employee_name,
    e.employee_number,
    aal.level_name,
    aal.required_training,
    aal.max_duration_hours
FROM area_authorized_employees aae
LEFT JOIN employees e ON aae.employee_id = e.id
LEFT JOIN area_access_levels aal ON aae.access_level_id = aal.id
WHERE aae.area_id = ?
    AND aae.status = 'active'
ORDER BY e.name

-- تصاريح العمل النشطة
SELECT 
    wp.*,
    ua.name as area_name,
    e.name as employee_name,
    e.employee_number,
    CASE 
        WHEN wp.end_time < CURRENT_TIMESTAMP THEN 'Expired'
        WHEN wp.end_time <= DATETIME('now', '+1 hour') THEN 'Expiring Soon'
        ELSE 'Active'
    END as permit_status
FROM work_permits wp
LEFT JOIN unauthorized_areas ua ON wp.area_id = ua.id
LEFT JOIN employees e ON wp.employee_id = e.id
WHERE wp.status = 'active'
    AND wp.start_time <= CURRENT_TIMESTAMP
    AND wp.end_time >= CURRENT_TIMESTAMP
ORDER BY wp.start_time
```

---

## 4. المخالفات حسب الشخص

### Route
```
GET /unauthorized/violations-by-person
```

### Function Name
```python
unauthorized_violations_by_person()
```

### Template Path
```
templates/unauthorized/violations-by-person.html
```

### الوصف
صفحة تحليل المخالفات حسب الموظف مع تقييم الخطورة والتدريب المطلوب.

### المحتوى
- أكثر الموظفين تسببًا في violations
- عدد مرات الدخول غير المصرح
- تقييم خطورة الشخص (Risk Assessment)
- هل هو شخص يحتاج تدريب إضافي؟
- سجل المخالفات الشخصي
- مقارنة بالأشخاص في نفس القسم
- Trends timeline (خط زمني للمخالفات)

### البيانات المطلوبة من الداتابيس

#### الجداول المطلوبة:
1. **violations** - جدول المخالفات
2. **employees** - جدول الموظفين
3. **departments** - جدول الأقسام
4. **employee_risk_assessment** - جدول تقييم خطورة الموظفين
5. **training_needs** - جدول احتياجات التدريب

#### الريليشنز:
- `violations.employee_id` → `employees.id`
- `employees.department_id` → `departments.id`
- `employee_risk_assessment.employee_id` → `employees.id`
- `training_needs.employee_id` → `employees.id`

#### البيانات المطلوبة:
```sql
-- أكثر الموظفين مخالفة
SELECT 
    e.id,
    e.name as employee_name,
    e.employee_number,
    d.name as department_name,
    COUNT(v.id) as total_violations,
    COUNT(CASE WHEN v.severity = 'Critical' THEN 1 END) as critical_count,
    COUNT(CASE WHEN v.severity = 'High' THEN 1 END) as high_count,
    MAX(v.incident_datetime) as last_violation_date
FROM employees e
LEFT JOIN departments d ON e.department_id = d.id
LEFT JOIN violations v ON e.id = v.employee_id
WHERE e.status = 'active'
GROUP BY e.id, e.name, e.employee_number, d.name
HAVING COUNT(v.id) > 0
ORDER BY total_violations DESC
LIMIT 10

-- تقييم خطورة الموظف
SELECT 
    era.*,
    e.name as employee_name,
    CASE 
        WHEN era.risk_score >= 80 THEN 'Critical'
        WHEN era.risk_score >= 60 THEN 'High'
        WHEN era.risk_score >= 40 THEN 'Medium'
        ELSE 'Low'
    END as risk_level
FROM employee_risk_assessment era
LEFT JOIN employees e ON era.employee_id = e.id
WHERE era.employee_id = ?
ORDER BY era.assessment_date DESC
LIMIT 1

-- سجل المخالفات الشخصي
SELECT 
    v.*,
    vt.name as violation_type_name,
    d.name as department_name,
    l.name as location_name
FROM violations v
LEFT JOIN violation_types vt ON v.violation_type_id = vt.id
LEFT JOIN departments d ON v.department_id = d.id
LEFT JOIN locations l ON v.location_id = l.id
WHERE v.employee_id = ?
ORDER BY v.incident_datetime DESC

-- مقارنة مع القسم
SELECT 
    d.name as department_name,
    AVG(emp_violations.violation_count) as avg_violations_per_person,
    COUNT(DISTINCT e.id) as total_employees
FROM departments d
LEFT JOIN employees e ON d.id = e.department_id AND e.status = 'active'
LEFT JOIN (
    SELECT 
        employee_id,
        COUNT(*) as violation_count
    FROM violations
    WHERE incident_datetime >= DATE('now', '-90 days')
    GROUP BY employee_id
) emp_violations ON e.id = emp_violations.employee_id
WHERE d.id = (SELECT department_id FROM employees WHERE id = ?)
GROUP BY d.id, d.name

-- Timeline للمخالفات
SELECT 
    DATE(incident_datetime) as date,
    COUNT(*) as violation_count
FROM violations
WHERE employee_id = ?
    AND incident_datetime >= DATE('now', '-6 months')
GROUP BY DATE(incident_datetime)
ORDER BY date
```

---

## 5. المخالفات حسب القسم

### Route
```
GET /unauthorized/violations-by-department
```

### Function Name
```python
unauthorized_violations_by_department()
```

### Template Path
```
templates/unauthorized/violations-by-department.html
```

### الوصف
صفحة تحليل شامل للمخالفات حسب الأقسام مع التوصيات التلقائية.

### المحتوى
- جدول بالأقسام وترتيبها حسب عدد المخالفات
- نوع المخالفة الأكثر انتشارًا في كل قسم
- المخالفات حسب الشفت (Morning / Night / On-call)
- معدلات الخطورة
- نسبة الالتزام بالسلامة
- Recommendations تلقائية للقسم

### البيانات المطلوبة من الداتابيس

#### الجداول المطلوبة:
1. **violations** - جدول المخالفات
2. **departments** - جدول الأقسام
3. **violation_types** - جدول أنواع المخالفات
4. **shifts** - جدول الورديات
5. **employees** - جدول الموظفين
6. **department_compliance** - جدول التزام الأقسام

#### الريليشنز:
- `violations.department_id` → `departments.id`
- `violations.violation_type_id` → `violation_types.id`
- `violations.shift_id` → `shifts.id`
- `employees.department_id` → `departments.id`
- `department_compliance.department_id` → `departments.id`

#### البيانات المطلوبة:
```sql
-- ترتيب الأقسام حسب المخالفات
SELECT 
    d.id,
    d.name as department_name,
    COUNT(v.id) as total_violations,
    COUNT(CASE WHEN v.severity = 'Critical' THEN 1 END) as critical_count,
    COUNT(CASE WHEN v.severity = 'High' THEN 1 END) as high_count,
    COUNT(DISTINCT v.employee_id) as violating_employees_count,
    COUNT(DISTINCT e.id) as total_employees,
    (COUNT(v.id) * 100.0 / COUNT(DISTINCT e.id)) as violations_per_employee
FROM departments d
LEFT JOIN employees e ON d.id = e.department_id AND e.status = 'active'
LEFT JOIN violations v ON d.id = v.department_id
    AND v.incident_datetime >= DATE('now', '-90 days')
GROUP BY d.id, d.name
HAVING COUNT(v.id) > 0
ORDER BY total_violations DESC

-- نوع المخالفة الأكثر في كل قسم
SELECT 
    d.name as department_name,
    vt.name as violation_type_name,
    COUNT(v.id) as violation_count
FROM violations v
LEFT JOIN departments d ON v.department_id = d.id
LEFT JOIN violation_types vt ON v.violation_type_id = vt.id
WHERE v.incident_datetime >= DATE('now', '-90 days')
GROUP BY d.id, d.name, vt.id, vt.name
HAVING (d.id, COUNT(v.id)) IN (
    SELECT department_id, MAX(cnt)
    FROM (
        SELECT 
            department_id,
            violation_type_id,
            COUNT(*) as cnt
        FROM violations
        WHERE incident_datetime >= DATE('now', '-90 days')
        GROUP BY department_id, violation_type_id
    )
    GROUP BY department_id
)

-- المخالفات حسب الشفت
SELECT 
    d.name as department_name,
    s.name as shift_name,
    s.shift_type,
    COUNT(v.id) as violation_count
FROM violations v
LEFT JOIN departments d ON v.department_id = d.id
LEFT JOIN shifts s ON v.shift_id = s.id
WHERE v.incident_datetime >= DATE('now', '-30 days')
GROUP BY d.id, d.name, s.id, s.name, s.shift_type
ORDER BY d.name, violation_count DESC

-- نسبة الالتزام بالسلامة
SELECT 
    d.id,
    d.name as department_name,
    dc.compliance_score,
    dc.last_updated,
    CASE 
        WHEN dc.compliance_score >= 90 THEN 'Excellent'
        WHEN dc.compliance_score >= 75 THEN 'Good'
        WHEN dc.compliance_score >= 60 THEN 'Fair'
        ELSE 'Poor'
    END as compliance_level
FROM departments d
LEFT JOIN department_compliance dc ON d.id = dc.department_id
    AND dc.period = DATE('now', 'start of month')
WHERE d.status = 'active'
ORDER BY dc.compliance_score DESC
```

---

## 6. المخالفات حسب الموقع

### Route
```
GET /unauthorized/violations-by-location
```

### Function Name
```python
unauthorized_violations_by_location()
```

### Template Path
```
templates/unauthorized/violations-by-location.html
```

### الوصف
صفحة تعرض خريطة حرارية للمواقع مع تحليل المخالفات في كل موقع.

### المحتوى
- خريطة حرارية Hot Zones
- أماكن تتكرر فيها المخالفات
- نسبة الخطورة لكل منطقة
- كاميرات مرتبطة بكل موقع (إن وجدت)
- صور ومرفقات سابقة للحوادث في المكان

### البيانات المطلوبة من الداتابيس

#### الجداول المطلوبة:
1. **violations** - جدول المخالفات
2. **locations** - جدول المواقع
3. **location_cameras** - جدول الكاميرات
4. **violation_attachments** - جدول المرفقات
5. **unauthorized_areas** - جدول المناطق غير المصرح بها

#### الريليشنز:
- `violations.location_id` → `locations.id`
- `location_cameras.location_id` → `locations.id`
- `violation_attachments.violation_id` → `violations.id`
- `unauthorized_areas.location_id` → `locations.id`

#### البيانات المطلوبة:
```sql
-- خريطة حرارية للمواقع
SELECT 
    l.id,
    l.name as location_name,
    l.latitude,
    l.longitude,
    COUNT(v.id) as violation_count,
    COUNT(DISTINCT DATE(v.incident_datetime)) as violation_days,
    AVG(CASE 
        WHEN v.severity = 'Critical' THEN 4
        WHEN v.severity = 'High' THEN 3
        WHEN v.severity = 'Medium' THEN 2
        ELSE 1
    END) as avg_severity_score,
    MAX(v.incident_datetime) as last_violation_date
FROM locations l
LEFT JOIN violations v ON l.id = v.location_id
    AND v.incident_datetime >= DATE('now', '-90 days')
GROUP BY l.id, l.name, l.latitude, l.longitude
ORDER BY violation_count DESC

-- أماكن تتكرر فيها المخالفات
SELECT 
    l.name as location_name,
    COUNT(v.id) as violation_count,
    COUNT(DISTINCT v.employee_id) as unique_violators,
    GROUP_CONCAT(DISTINCT vt.name) as violation_types
FROM violations v
LEFT JOIN locations l ON v.location_id = l.id
LEFT JOIN violation_types vt ON v.violation_type_id = vt.id
WHERE v.incident_datetime >= DATE('now', '-90 days')
GROUP BY l.id, l.name
HAVING COUNT(v.id) >= 3
ORDER BY violation_count DESC

-- الكاميرات المرتبطة
SELECT 
    lc.*,
    l.name as location_name
FROM location_cameras lc
LEFT JOIN locations l ON lc.location_id = l.id
WHERE lc.location_id = ?
    AND lc.status = 'active'

-- مرفقات الحوادث في موقع معين
SELECT 
    va.*,
    v.incident_datetime,
    v.severity
FROM violation_attachments va
LEFT JOIN violations v ON va.violation_id = v.id
WHERE v.location_id = ?
    AND va.file_type IN ('image', 'video')
ORDER BY v.incident_datetime DESC
LIMIT 20
```

---

## 7. تحليل المخاطر

### Route
```
GET /unauthorized/risk-analysis
```

### Function Name
```python
unauthorized_risk_analysis()
```

### Template Path
```
templates/unauthorized/risk-analysis.html
```

### الوصف
صفحة تحليل متقدم لأنواع المخاطر مع الرسوم البيانية والتوقعات.

### المحتوى
- تحليل أنواع المخاطر:
  - Unauthorized Entry
  - Unsafe Actions
  - Hazardous Material Access
  - Confined Space Entry
  - Working at Height violations

- Graphs:
  - Bar Chart: توزيع المخاطر
  - Pie Chart: نسبة كل نوع
  - Line Chart: اتجاهات المخاطر

- توقعات AI (اختياري):
  - توقع الأماكن التي قد تحدث فيها مخالفات قريبًا
  - تحليل السلوك المتكرر

### البيانات المطلوبة من الداتابيس

#### الجداول المطلوبة:
1. **violations** - جدول المخالفات
2. **violation_types** - جدول أنواع المخالفات
3. **risk_predictions** - جدول توقعات المخاطر (AI)
4. **locations** - جدول المواقع
5. **risk_patterns** - جدول أنماط المخاطر

#### الريليشنز:
- `violations.violation_type_id` → `violation_types.id`
- `violations.location_id` → `locations.id`
- `risk_predictions.location_id` → `locations.id`
- `risk_predictions.violation_type_id` → `violation_types.id`
- `risk_patterns.violation_type_id` → `violation_types.id`

#### البيانات المطلوبة:
```sql
-- تحليل أنواع المخاطر
SELECT 
    vt.id,
    vt.name as risk_type,
    vt.category,
    COUNT(v.id) as violation_count,
    AVG(CASE 
        WHEN v.severity = 'Critical' THEN 4
        WHEN v.severity = 'High' THEN 3
        WHEN v.severity = 'Medium' THEN 2
        ELSE 1
    END) as avg_severity,
    COUNT(DISTINCT v.location_id) as affected_locations,
    COUNT(DISTINCT v.employee_id) as affected_employees
FROM violation_types vt
LEFT JOIN violations v ON vt.id = v.violation_type_id
    AND v.incident_datetime >= DATE('now', '-90 days')
GROUP BY vt.id, vt.name, vt.category
ORDER BY violation_count DESC

-- اتجاهات المخاطر (Line Chart)
SELECT 
    DATE(incident_datetime) as date,
    vt.name as risk_type,
    COUNT(*) as violation_count
FROM violations v
LEFT JOIN violation_types vt ON v.violation_type_id = vt.id
WHERE v.incident_datetime >= DATE('now', '-30 days')
GROUP BY DATE(incident_datetime), vt.id, vt.name
ORDER BY date, violation_count DESC

-- توقعات AI
SELECT 
    rp.*,
    l.name as location_name,
    vt.name as risk_type_name,
    rp.probability,
    rp.predicted_date
FROM risk_predictions rp
LEFT JOIN locations l ON rp.location_id = l.id
LEFT JOIN violation_types vt ON rp.violation_type_id = vt.id
WHERE rp.status = 'active'
    AND rp.predicted_date >= CURRENT_DATE
ORDER BY rp.probability DESC, rp.predicted_date

-- أنماط المخاطر المتكررة
SELECT 
    rp.*,
    vt.name as violation_type_name,
    COUNT(DISTINCT v.id) as pattern_occurrences
FROM risk_patterns rp
LEFT JOIN violation_types vt ON rp.violation_type_id = vt.id
LEFT JOIN violations v ON v.violation_type_id = rp.violation_type_id
    AND v.incident_datetime >= DATE('now', '-90 days')
GROUP BY rp.id, rp.pattern_description, vt.name
ORDER BY pattern_occurrences DESC
```

---

## 8. السجل اليومي / سجل الورديات

### Route
```
GET /unauthorized/daily-log
```

### Function Name
```python
unauthorized_daily_log()
```

### Template Path
```
templates/unauthorized/daily-log.html
```

### الوصف
صفحة تعرض السجل اليومي للمخالفات مع تحليل الورديات.

### المحتوى
- عدد المخالفات اليوم
- تحليل حسب الشفت
- مقارنة الأيام السابقة
- شفت مين عمل أكبر violations
- تقارير PDF يومية جاهزة

### البيانات المطلوبة من الداتابيس

#### الجداول المطلوبة:
1. **violations** - جدول المخالفات
2. **shifts** - جدول الورديات
3. **employees** - جدول الموظفين
4. **daily_reports** - جدول التقارير اليومية

#### الريليشنز:
- `violations.shift_id` → `shifts.id`
- `violations.employee_id` → `employees.id`

#### البيانات المطلوبة:
```sql
-- المخالفات اليوم
SELECT 
    COUNT(*) as today_violations,
    COUNT(CASE WHEN severity = 'Critical' THEN 1 END) as critical_count,
    COUNT(CASE WHEN severity = 'High' THEN 1 END) as high_count,
    COUNT(DISTINCT employee_id) as unique_violators,
    COUNT(DISTINCT location_id) as affected_locations
FROM violations
WHERE DATE(incident_datetime) = CURRENT_DATE

-- تحليل حسب الشفت
SELECT 
    s.name as shift_name,
    s.shift_type,
    COUNT(v.id) as violation_count,
    COUNT(DISTINCT v.employee_id) as unique_violators
FROM violations v
LEFT JOIN shifts s ON v.shift_id = s.id
WHERE DATE(v.incident_datetime) = CURRENT_DATE
GROUP BY s.id, s.name, s.shift_type
ORDER BY violation_count DESC

-- مقارنة الأيام السابقة
SELECT 
    DATE(incident_datetime) as date,
    COUNT(*) as violation_count,
    COUNT(CASE WHEN severity = 'Critical' THEN 1 END) as critical_count
FROM violations
WHERE incident_datetime >= DATE('now', '-7 days')
GROUP BY DATE(incident_datetime)
ORDER BY date DESC

-- أكثر شفت مخالفة
SELECT 
    s.name as shift_name,
    s.shift_type,
    COUNT(v.id) as total_violations,
    AVG(CASE 
        WHEN v.severity = 'Critical' THEN 4
        WHEN v.severity = 'High' THEN 3
        WHEN v.severity = 'Medium' THEN 2
        ELSE 1
    END) as avg_severity
FROM shifts s
LEFT JOIN violations v ON s.id = v.shift_id
    AND v.incident_datetime >= DATE('now', '-30 days')
GROUP BY s.id, s.name, s.shift_type
ORDER BY total_violations DESC
```

---

## 9. الإبلاغ عن الحوادث

### Route
```
GET /unauthorized/incident-reporting
```

### Function Name
```python
unauthorized_incident_reporting()
```

### Template Path
```
templates/unauthorized/incident-reporting.html
```

### الوصف
صفحة لإضافة مخالفة جديدة مع جميع التفاصيل المطلوبة.

### المحتوى
- **نموذج إضافة مخالفة:**
  - اختيار نوع المخالفة
  - اختيار الشخص المسؤول
  - اختيار الموقع
  - رفع صور
  - تحديد مستوى الخطورة
  - إضافة وصف
  - إضافة الشهود
  - إضافة إجراء تصحيحي سريع

### البيانات المطلوبة من الداتابيس

#### الجداول المطلوبة:
1. **violations** - جدول المخالفات (INSERT)
2. **violation_types** - جدول أنواع المخالفات (SELECT)
3. **employees** - جدول الموظفين (SELECT)
4. **locations** - جدول المواقع (SELECT)
5. **departments** - جدول الأقسام (SELECT)
6. **violation_attachments** - جدول المرفقات (INSERT)
7. **violation_witnesses** - جدول الشهود (INSERT)
8. **corrective_actions** - جدول الإجراءات التصحيحية (INSERT)

#### الريليشنز:
- `violations.employee_id` → `employees.id`
- `violations.department_id` → `departments.id`
- `violations.location_id` → `locations.id`
- `violations.violation_type_id` → `violation_types.id`
- `violation_attachments.violation_id` → `violations.id`
- `violation_witnesses.violation_id` → `violations.id`
- `violation_witnesses.employee_id` → `employees.id`
- `corrective_actions.violation_id` → `violations.id`

#### البيانات المطلوبة:
```sql
-- قائمة أنواع المخالفات (للـ Dropdown)
SELECT 
    id,
    name,
    category,
    default_severity
FROM violation_types
WHERE status = 'active'
ORDER BY category, name

-- قائمة الموظفين (للـ Dropdown)
SELECT 
    id,
    name,
    employee_number,
    department_id
FROM employees
WHERE status = 'active'
ORDER BY name

-- قائمة المواقع (للـ Dropdown)
SELECT 
    id,
    name,
    address
FROM locations
WHERE status = 'active'
ORDER BY name

-- إدراج مخالفة جديدة
INSERT INTO violations (
    violation_type_id,
    employee_id,
    department_id,
    location_id,
    incident_datetime,
    severity,
    description,
    reported_by,
    status,
    created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', CURRENT_TIMESTAMP)

-- إدراج مرفقات
INSERT INTO violation_attachments (
    violation_id,
    file_path,
    file_type,
    file_name,
    uploaded_by,
    uploaded_at
) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)

-- إدراج شهود
INSERT INTO violation_witnesses (
    violation_id,
    employee_id,
    witness_statement,
    added_at
) VALUES (?, ?, ?, CURRENT_TIMESTAMP)

-- إدراج إجراء تصحيحي سريع
INSERT INTO corrective_actions (
    violation_id,
    action_description,
    responsible_person_id,
    due_date,
    status,
    created_at
) VALUES (?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP)
```

---

## 10. التحقيقات وسبب الجذر

### Route
```
GET /unauthorized/investigations
```

### Function Name
```python
unauthorized_investigations()
```

### Template Path
```
templates/unauthorized/investigations.html
```

### الوصف
صفحة إدارة التحقيقات في المخالفات مع تحليل 5 WHY وسبب الجذر.

### المحتوى
- قائمة التحقيقات
- من هو المسؤول عن التحقيق؟
- لماذا حدثت؟ (5 WHY Analysis)
- Root Cause
- خطة منع التكرار
- تاريخ الانتهاء
- مسؤول الإغلاق

### البيانات المطلوبة من الداتابيس

#### الجداول المطلوبة:
1. **investigations** - جدول التحقيقات
2. **violations** - جدول المخالفات
3. **investigation_5why** - جدول تحليل 5 WHY
4. **root_causes** - جدول أسباب الجذر
5. **prevention_plans** - جدول خطط المنع
6. **employees** - جدول الموظفين

#### الريليشنز:
- `investigations.violation_id` → `violations.id`
- `investigations.investigator_id` → `employees.id`
- `investigations.closed_by` → `employees.id`
- `investigation_5why.investigation_id` → `investigations.id`
- `root_causes.investigation_id` → `investigations.id`
- `prevention_plans.investigation_id` → `investigations.id`

#### البيانات المطلوبة:
```sql
-- قائمة التحقيقات
SELECT 
    i.*,
    v.incident_datetime,
    v.severity,
    vt.name as violation_type_name,
    investigator.name as investigator_name,
    closer.name as closer_name
FROM investigations i
LEFT JOIN violations v ON i.violation_id = v.id
LEFT JOIN violation_types vt ON v.violation_type_id = vt.id
LEFT JOIN employees investigator ON i.investigator_id = investigator.id
LEFT JOIN employees closer ON i.closed_by = closer.id
ORDER BY i.created_at DESC

-- تحليل 5 WHY
SELECT 
    i5w.*,
    i.violation_id
FROM investigation_5why i5w
LEFT JOIN investigations i ON i5w.investigation_id = i.id
WHERE i5w.investigation_id = ?
ORDER BY i5w.why_level

-- سبب الجذر
SELECT 
    rc.*,
    i.violation_id
FROM root_causes rc
LEFT JOIN investigations i ON rc.investigation_id = i.id
WHERE rc.investigation_id = ?

-- خطة المنع
SELECT 
    pp.*,
    e.name as responsible_name
FROM prevention_plans pp
LEFT JOIN investigations i ON pp.investigation_id = i.id
LEFT JOIN employees e ON pp.responsible_person_id = e.id
WHERE pp.investigation_id = ?
ORDER BY pp.priority
```

---

## 11. إدارة الإجراءات التصحيحية

### Route
```
GET /unauthorized/corrective-actions
```

### Function Name
```python
unauthorized_corrective_actions()
```

### Template Path
```
templates/unauthorized/corrective-actions.html
```

### الوصف
صفحة إدارة جميع الإجراءات التصحيحية مع متابعة الحالة والتنفيذ.

### المحتوى
- قائمة جميع الإجراءات التصحيحية
- حالتها (Pending / In progress / Done)
- المسؤول عنها
- تاريخ التنفيذ
- مرفقات
- علامات تذكير Reminder Notifications

### البيانات المطلوبة من الداتابيس

#### الجداول المطلوبة:
1. **corrective_actions** - جدول الإجراءات التصحيحية
2. **violations** - جدول المخالفات
3. **employees** - جدول الموظفين
4. **corrective_action_attachments** - جدول مرفقات الإجراءات
5. **action_reminders** - جدول التذكيرات

#### الريليشنز:
- `corrective_actions.violation_id` → `violations.id`
- `corrective_actions.responsible_person_id` → `employees.id`
- `corrective_action_attachments.action_id` → `corrective_actions.id`
- `action_reminders.action_id` → `corrective_actions.id`

#### البيانات المطلوبة:
```sql
-- قائمة الإجراءات التصحيحية
SELECT 
    ca.*,
    v.incident_datetime,
    v.severity,
    vt.name as violation_type_name,
    e.name as responsible_name,
    e.email as responsible_email,
    CASE 
        WHEN ca.due_date < CURRENT_DATE AND ca.status != 'completed' THEN 'Overdue'
        WHEN ca.due_date <= DATE('now', '+3 days') AND ca.status != 'completed' THEN 'Due Soon'
        ELSE ca.status
    END as status_with_overdue
FROM corrective_actions ca
LEFT JOIN violations v ON ca.violation_id = v.id
LEFT JOIN violation_types vt ON v.violation_type_id = vt.id
LEFT JOIN employees e ON ca.responsible_person_id = e.id
ORDER BY 
    CASE WHEN ca.due_date < CURRENT_DATE AND ca.status != 'completed' THEN 0 ELSE 1 END,
    ca.due_date ASC

-- مرفقات الإجراء
SELECT 
    caa.*
FROM corrective_action_attachments caa
WHERE caa.action_id = ?
ORDER BY caa.uploaded_at DESC

-- التذكيرات
SELECT 
    ar.*
FROM action_reminders ar
WHERE ar.action_id = ?
    AND ar.status = 'pending'
ORDER BY ar.reminder_date ASC
```

---

## 12. احتياجات التدريب

### Route
```
GET /unauthorized/training-needs
```

### Function Name
```python
unauthorized_training_needs()
```

### Template Path
```
templates/unauthorized/training-needs.html
```

### الوصف
صفحة تحليل احتياجات التدريب بناءً على المخالفات مع توصيات محددة.

### المحتوى
- تحليل الموظفين الأكثر مخالفة
- التصريح بحضور دورات معينة مثل:
  - Authorized area training
  - Confined space training
  - Fire safety
- متابعة حضور التدريب
- نسبة تحسن بعد التدريب

### البيانات المطلوبة من الداتابيس

#### الجداول المطلوبة:
1. **training_needs** - جدول احتياجات التدريب
2. **employees** - جدول الموظفين
3. **violations** - جدول المخالفات
4. **training_courses** - جدول الدورات
5. **employee_training** - جدول سجل تدريب الموظفين
6. **training_effectiveness** - جدول فعالية التدريب

#### الريليشنز:
- `training_needs.employee_id` → `employees.id`
- `training_needs.course_id` → `training_courses.id`
- `violations.employee_id` → `employees.id`
- `employee_training.employee_id` → `employees.id`
- `employee_training.course_id` → `training_courses.id`
- `training_effectiveness.employee_id` → `employees.id`
- `training_effectiveness.course_id` → `training_courses.id`

#### البيانات المطلوبة:
```sql
-- الموظفين الأكثر مخالفة (يحتاجون تدريب)
SELECT 
    e.id,
    e.name as employee_name,
    e.employee_number,
    COUNT(v.id) as violation_count,
    GROUP_CONCAT(DISTINCT vt.name) as violation_types,
    MAX(v.incident_datetime) as last_violation_date
FROM employees e
LEFT JOIN violations v ON e.id = v.employee_id
    AND v.incident_datetime >= DATE('now', '-90 days')
LEFT JOIN violation_types vt ON v.violation_type_id = vt.id
WHERE e.status = 'active'
GROUP BY e.id, e.name, e.employee_number
HAVING COUNT(v.id) >= 2
ORDER BY violation_count DESC

-- احتياجات التدريب الموصى بها
SELECT 
    tn.*,
    e.name as employee_name,
    tc.name as course_name,
    tc.duration,
    tc.category,
    CASE 
        WHEN tn.priority = 'high' THEN 'Critical'
        WHEN tn.priority = 'medium' THEN 'Important'
        ELSE 'Recommended'
    END as priority_level
FROM training_needs tn
LEFT JOIN employees e ON tn.employee_id = e.id
LEFT JOIN training_courses tc ON tn.course_id = tc.id
WHERE tn.status = 'pending'
ORDER BY 
    CASE tn.priority 
        WHEN 'high' THEN 1
        WHEN 'medium' THEN 2
        ELSE 3
    END,
    tn.created_at DESC

-- متابعة حضور التدريب
SELECT 
    et.*,
    e.name as employee_name,
    tc.name as course_name,
    tc.category,
    CASE 
        WHEN et.status = 'completed' THEN 'Completed'
        WHEN et.status = 'in_progress' THEN 'In Progress'
        WHEN et.enrollment_date < DATE('now', '-30 days') AND et.status != 'completed' THEN 'Overdue'
        ELSE 'Pending'
    END as training_status
FROM employee_training et
LEFT JOIN employees e ON et.employee_id = e.id
LEFT JOIN training_courses tc ON et.course_id = tc.id
WHERE et.employee_id IN (
    SELECT DISTINCT employee_id 
    FROM violations 
    WHERE incident_datetime >= DATE('now', '-90 days')
)
ORDER BY et.enrollment_date DESC

-- نسبة التحسن بعد التدريب
SELECT 
    te.*,
    e.name as employee_name,
    tc.name as course_name,
    COUNT(v_before.id) as violations_before,
    COUNT(v_after.id) as violations_after,
    CASE 
        WHEN COUNT(v_after.id) < COUNT(v_before.id) THEN 'Improved'
        WHEN COUNT(v_after.id) = COUNT(v_before.id) THEN 'No Change'
        ELSE 'Worsened'
    END as improvement_status
FROM training_effectiveness te
LEFT JOIN employees e ON te.employee_id = e.id
LEFT JOIN training_courses tc ON te.course_id = tc.id
LEFT JOIN violations v_before ON e.id = v_before.employee_id
    AND v_before.incident_datetime < te.training_completion_date
    AND v_before.incident_datetime >= DATE(te.training_completion_date, '-90 days')
LEFT JOIN violations v_after ON e.id = v_after.employee_id
    AND v_after.incident_datetime >= te.training_completion_date
    AND v_after.incident_datetime <= DATE(te.training_completion_date, '+90 days')
GROUP BY te.id, te.employee_id, te.course_id, e.name, tc.name
ORDER BY te.training_completion_date DESC
```

---

## 13. نقاط الالتزام

### Route
```
GET /unauthorized/compliance-score
```

### Function Name
```python
unauthorized_compliance_score()
```

### Template Path
```
templates/unauthorized/compliance-score.html
```

### الوصف
صفحة تعرض نقاط الالتزام لكل قسم وموقع وشخص مع تحليل الاتجاهات.

### المحتوى
- Score لكل قسم
- Score لكل موقع
- Score لكل شخص
- دوران score over time
- تحليلات لتحسين مستوى الأمان

### البيانات المطلوبة من الداتابيس

#### الجداول المطلوبة:
1. **compliance_scores** - جدول نقاط الالتزام
2. **departments** - جدول الأقسام
3. **locations** - جدول المواقع
4. **employees** - جدول الموظفين
5. **violations** - جدول المخالفات
6. **compliance_history** - جدول تاريخ الالتزام

#### الريليشنز:
- `compliance_scores.department_id` → `departments.id`
- `compliance_scores.location_id` → `locations.id`
- `compliance_scores.employee_id` → `employees.id`
- `compliance_history.department_id` → `departments.id`
- `compliance_history.location_id` → `locations.id`
- `compliance_history.employee_id` → `employees.id`

#### البيانات المطلوبة:
```sql
-- Score لكل قسم
SELECT 
    d.id,
    d.name as department_name,
    cs.score as current_score,
    cs.last_updated,
    COUNT(v.id) as violation_count,
    AVG(CASE 
        WHEN v.severity = 'Critical' THEN 0
        WHEN v.severity = 'High' THEN 25
        WHEN v.severity = 'Medium' THEN 50
        ELSE 75
    END) as calculated_score
FROM departments d
LEFT JOIN compliance_scores cs ON d.id = cs.department_id
    AND cs.score_type = 'department'
    AND cs.period = DATE('now', 'start of month')
LEFT JOIN violations v ON d.id = v.department_id
    AND v.incident_datetime >= DATE('now', 'start of month')
WHERE d.status = 'active'
GROUP BY d.id, d.name, cs.score, cs.last_updated
ORDER BY cs.score DESC

-- Score لكل موقع
SELECT 
    l.id,
    l.name as location_name,
    cs.score as current_score,
    cs.last_updated,
    COUNT(v.id) as violation_count
FROM locations l
LEFT JOIN compliance_scores cs ON l.id = cs.location_id
    AND cs.score_type = 'location'
    AND cs.period = DATE('now', 'start of month')
LEFT JOIN violations v ON l.id = v.location_id
    AND v.incident_datetime >= DATE('now', 'start of month')
WHERE l.status = 'active'
GROUP BY l.id, l.name, cs.score, cs.last_updated
ORDER BY cs.score DESC

-- Score لكل شخص
SELECT 
    e.id,
    e.name as employee_name,
    e.employee_number,
    cs.score as current_score,
    cs.last_updated,
    COUNT(v.id) as violation_count,
    MAX(v.incident_datetime) as last_violation_date
FROM employees e
LEFT JOIN compliance_scores cs ON e.id = cs.employee_id
    AND cs.score_type = 'employee'
    AND cs.period = DATE('now', 'start of month')
LEFT JOIN violations v ON e.id = v.employee_id
    AND v.incident_datetime >= DATE('now', 'start of month')
WHERE e.status = 'active'
GROUP BY e.id, e.name, e.employee_number, cs.score, cs.last_updated
ORDER BY cs.score DESC

-- اتجاهات Score over time
SELECT 
    ch.period,
    ch.score_type,
    ch.score,
    d.name as department_name,
    l.name as location_name,
    e.name as employee_name
FROM compliance_history ch
LEFT JOIN departments d ON ch.department_id = d.id AND ch.score_type = 'department'
LEFT JOIN locations l ON ch.location_id = l.id AND ch.score_type = 'location'
LEFT JOIN employees e ON ch.employee_id = e.id AND ch.score_type = 'employee'
WHERE ch.period >= DATE('now', '-12 months')
ORDER BY ch.period DESC, ch.score_type
```

---

## 14. السياسات وقواعد السلامة

### Route
```
GET /unauthorized/policies
```

### Function Name
```python
unauthorized_policies()
```

### Template Path
```
templates/unauthorized/policies.html
```

### الوصف
صفحة عرض السياسات واللوائح وقواعد السلامة مع الفيديوهات التعليمية.

### المحتوى
- سياسات الشركة
- اللوائح
- المناطق المحظورة
- تعليمات لكل منطقة
- فيديوهات تعليمية

### البيانات المطلوبة من الداتابيس

#### الجداول المطلوبة:
1. **safety_policies** - جدول السياسات
2. **safety_regulations** - جدول اللوائح
3. **area_safety_instructions** - جدول تعليمات المناطق
4. **safety_videos** - جدول الفيديوهات التعليمية
5. **unauthorized_areas** - جدول المناطق غير المصرح بها

#### الريليشنز:
- `area_safety_instructions.area_id` → `unauthorized_areas.id`

#### البيانات المطلوبة:
```sql
-- السياسات
SELECT 
    sp.*,
    sp.category,
    sp.effective_date,
    sp.last_updated
FROM safety_policies sp
WHERE sp.status = 'active'
ORDER BY sp.category, sp.title

-- اللوائح
SELECT 
    sr.*,
    sr.regulation_number,
    sr.issuing_authority
FROM safety_regulations sr
WHERE sr.status = 'active'
ORDER BY sr.regulation_number

-- تعليمات المناطق
SELECT 
    asi.*,
    ua.name as area_name,
    ua.description
FROM area_safety_instructions asi
LEFT JOIN unauthorized_areas ua ON asi.area_id = ua.id
WHERE asi.status = 'active'
ORDER BY ua.name, asi.priority

-- الفيديوهات التعليمية
SELECT 
    sv.*,
    sv.category,
    sv.duration_minutes
FROM safety_videos sv
WHERE sv.status = 'active'
ORDER BY sv.category, sv.title
```

---

## 15. تكامل سجل الأمان

### Route
```
GET /unauthorized/security-log
```

### Function Name
```python
unauthorized_security_log()
```

### Template Path
```
templates/unauthorized/security-log.html
```

### الوصف
صفحة عرض سجل الأمان مع محاولات الدخول والكاميرات المرتبطة.

### المحتوى
- سجل دخول الموظفين
- محاولات الدخول المرفوضة
- كاميرات مرتبطة
- إنذار عند دخول unauthorized person

### البيانات المطلوبة من الداتابيس

#### الجداول المطلوبة:
1. **security_logs** - جدول سجل الأمان
2. **access_attempts** - جدول محاولات الوصول
3. **location_cameras** - جدول الكاميرات
4. **employees** - جدول الموظفين
5. **locations** - جدول المواقع
6. **unauthorized_areas** - جدول المناطق غير المصرح بها

#### الريليشنز:
- `security_logs.employee_id` → `employees.id`
- `security_logs.location_id` → `locations.id`
- `access_attempts.employee_id` → `employees.id`
- `access_attempts.area_id` → `unauthorized_areas.id`
- `location_cameras.location_id` → `locations.id`

#### البيانات المطلوبة:
```sql
-- سجل دخول الموظفين
SELECT 
    sl.*,
    e.name as employee_name,
    e.employee_number,
    l.name as location_name,
    CASE 
        WHEN sl.access_granted = 1 THEN 'Granted'
        ELSE 'Denied'
    END as access_status
FROM security_logs sl
LEFT JOIN employees e ON sl.employee_id = e.id
LEFT JOIN locations l ON sl.location_id = l.id
ORDER BY sl.access_time DESC
LIMIT 100

-- محاولات الدخول المرفوضة
SELECT 
    aa.*,
    e.name as employee_name,
    e.employee_number,
    ua.name as area_name,
    aa.reason as denial_reason
FROM access_attempts aa
LEFT JOIN employees e ON aa.employee_id = e.id
LEFT JOIN unauthorized_areas ua ON aa.area_id = ua.id
WHERE aa.access_granted = 0
ORDER BY aa.attempt_time DESC
LIMIT 50

-- الكاميرات المرتبطة
SELECT 
    lc.*,
    l.name as location_name,
    ua.name as area_name
FROM location_cameras lc
LEFT JOIN locations l ON lc.location_id = l.id
LEFT JOIN unauthorized_areas ua ON lc.area_id = ua.id
WHERE lc.status = 'active'
ORDER BY l.name, lc.camera_name

-- إنذارات الدخول غير المصرح
SELECT 
    aa.*,
    e.name as employee_name,
    e.employee_number,
    ua.name as area_name,
    aa.alert_sent,
    aa.alert_time
FROM access_attempts aa
LEFT JOIN employees e ON aa.employee_id = e.id
LEFT JOIN unauthorized_areas ua ON aa.area_id = ua.id
WHERE aa.access_granted = 0
    AND aa.alert_sent = 1
ORDER BY aa.attempt_time DESC
```

---

## 16. الأدوار والصلاحيات

### Route
```
GET /unauthorized/roles-permissions
```

### Function Name
```python
unauthorized_roles_permissions()
```

### Template Path
```
templates/unauthorized/roles-permissions.html
```

### الوصف
صفحة إدارة الأدوار والصلاحيات مع Dashboards مختلفة لكل دور.

### المحتوى
- Manager Dashboard
- HSE Officer Dashboard
- Security Dashboard
- Employee view
- Role-based access

### البيانات المطلوبة من الداتابيس

#### الجداول المطلوبة:
1. **user_roles** - جدول أدوار المستخدمين
2. **role_permissions** - جدول صلاحيات الأدوار
3. **permissions** - جدول الصلاحيات
4. **users** - جدول المستخدمين
5. **employees** - جدول الموظفين

#### الريليشنز:
- `user_roles.user_id` → `users.id`
- `user_roles.role_id` → `roles.id`
- `role_permissions.role_id` → `roles.id`
- `role_permissions.permission_id` → `permissions.id`
- `users.employee_id` → `employees.id`

#### البيانات المطلوبة:
```sql
-- أدوار المستخدمين
SELECT 
    ur.*,
    u.username,
    e.name as employee_name,
    r.role_name,
    r.description
FROM user_roles ur
LEFT JOIN users u ON ur.user_id = u.id
LEFT JOIN employees e ON u.employee_id = e.id
LEFT JOIN roles r ON ur.role_id = r.id
WHERE u.status = 'active'
ORDER BY r.role_name, e.name

-- صلاحيات الدور
SELECT 
    rp.*,
    r.role_name,
    p.permission_name,
    p.module,
    p.action
FROM role_permissions rp
LEFT JOIN roles r ON rp.role_id = r.id
LEFT JOIN permissions p ON rp.permission_id = p.id
WHERE r.role_name = ?
ORDER BY p.module, p.action

-- صلاحيات المستخدم
SELECT 
    p.*,
    r.role_name
FROM permissions p
INNER JOIN role_permissions rp ON p.id = rp.permission_id
INNER JOIN user_roles ur ON rp.role_id = ur.role_id
INNER JOIN users u ON ur.user_id = u.id
WHERE u.id = ?
ORDER BY p.module, p.action
```

---

## 17. تصدير التقارير

### Route
```
GET /unauthorized/reports
```

### Function Name
```python
unauthorized_reports()
```

### Template Path
```
templates/unauthorized/reports.html
```

### الوصف
صفحة التقارير الجاهزة مع إمكانية التصدير.

### المحتوى
- PDF يومي
- Excel أسبوعي
- Monthly KPIs
- Violations summary
- Risk Matrix

### البيانات المطلوبة من الداتابيس

#### الجداول المطلوبة:
جميع الجداول السابقة حسب نوع التقرير.

#### البيانات المطلوبة:
```sql
-- تقرير يومي (PDF)
SELECT 
    v.*,
    vt.name as violation_type_name,
    e.name as employee_name,
    d.name as department_name,
    l.name as location_name
FROM violations v
LEFT JOIN violation_types vt ON v.violation_type_id = vt.id
LEFT JOIN employees e ON v.employee_id = e.id
LEFT JOIN departments d ON v.department_id = d.id
LEFT JOIN locations l ON v.location_id = l.id
WHERE DATE(v.incident_datetime) = CURRENT_DATE
ORDER BY v.incident_datetime

-- تقرير أسبوعي (Excel)
SELECT 
    DATE(v.incident_datetime) as date,
    COUNT(*) as violation_count,
    COUNT(CASE WHEN v.severity = 'Critical' THEN 1 END) as critical_count,
    COUNT(DISTINCT v.employee_id) as unique_violators,
    COUNT(DISTINCT v.location_id) as affected_locations
FROM violations v
WHERE v.incident_datetime >= DATE('now', '-7 days')
GROUP BY DATE(v.incident_datetime)
ORDER BY date

-- Monthly KPIs
SELECT 
    COUNT(*) as total_violations,
    COUNT(CASE WHEN severity = 'Critical' THEN 1 END) as critical_violations,
    COUNT(DISTINCT employee_id) as unique_violators,
    COUNT(DISTINCT location_id) as affected_locations,
    AVG(CASE 
        WHEN severity = 'Critical' THEN 4
        WHEN severity = 'High' THEN 3
        WHEN severity = 'Medium' THEN 2
        ELSE 1
    END) as avg_severity
FROM violations
WHERE YEAR(incident_datetime) = YEAR(CURRENT_DATE)
    AND MONTH(incident_datetime) = MONTH(CURRENT_DATE)

-- Risk Matrix
SELECT 
    vt.name as risk_type,
    l.name as location_name,
    COUNT(v.id) as occurrence_count,
    AVG(CASE 
        WHEN v.severity = 'Critical' THEN 4
        WHEN v.severity = 'High' THEN 3
        WHEN v.severity = 'Medium' THEN 2
        ELSE 1
    END) as avg_severity,
    (COUNT(v.id) * AVG(CASE 
        WHEN v.severity = 'Critical' THEN 4
        WHEN v.severity = 'High' THEN 3
        WHEN v.severity = 'Medium' THEN 2
        ELSE 1
    END)) as risk_score
FROM violations v
LEFT JOIN violation_types vt ON v.violation_type_id = vt.id
LEFT JOIN locations l ON v.location_id = l.id
WHERE v.incident_datetime >= DATE('now', '-90 days')
GROUP BY vt.id, vt.name, l.id, l.name
ORDER BY risk_score DESC
```

---

## 18. الإعدادات

### Route
```
GET /unauthorized/settings
```

### Function Name
```python
unauthorized_settings()
```

### Template Path
```
templates/unauthorized/settings.html
```

### الوصف
صفحة إعدادات النظام مع إدارة المواقع وأنواع المخالفات والصلاحيات.

### المحتوى
- إضافة مواقع جديدة
- إضافة أنواع مخالفات جديدة
- إدارة المستخدمين
- إدارة الصلاحيات
- تخصيص التنبيهات

### البيانات المطلوبة من الداتابيس

#### الجداول المطلوبة:
1. **locations** - جدول المواقع (CRUD)
2. **violation_types** - جدول أنواع المخالفات (CRUD)
3. **users** - جدول المستخدمين (CRUD)
4. **roles** - جدول الأدوار (CRUD)
5. **permissions** - جدول الصلاحيات (CRUD)
6. **notification_settings** - جدول إعدادات التنبيهات

#### البيانات المطلوبة:
```sql
-- قائمة المواقع
SELECT 
    id,
    name,
    address,
    latitude,
    longitude,
    status
FROM locations
ORDER BY name

-- قائمة أنواع المخالفات
SELECT 
    id,
    name,
    category,
    default_severity,
    description,
    status
FROM violation_types
ORDER BY category, name

-- إعدادات التنبيهات
SELECT 
    ns.*,
    u.username
FROM notification_settings ns
LEFT JOIN users u ON ns.user_id = u.id
WHERE u.id = ?
```

---

## 📊 هيكل قاعدة البيانات المقترح

### الجداول الرئيسية:

```sql
-- المخالفات
CREATE TABLE violations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    violation_type_id INTEGER,
    employee_id INTEGER,
    department_id INTEGER,
    location_id INTEGER,
    incident_datetime DATETIME,
    severity TEXT, -- 'Low', 'Medium', 'High', 'Critical'
    description TEXT,
    status TEXT, -- 'open', 'under_investigation', 'closed'
    reported_by INTEGER,
    investigation_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (violation_type_id) REFERENCES violation_types(id),
    FOREIGN KEY (employee_id) REFERENCES employees(id),
    FOREIGN KEY (department_id) REFERENCES departments(id),
    FOREIGN KEY (location_id) REFERENCES locations(id),
    FOREIGN KEY (reported_by) REFERENCES employees(id),
    FOREIGN KEY (investigation_id) REFERENCES investigations(id)
);

-- أنواع المخالفات
CREATE TABLE violation_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT,
    default_severity TEXT,
    description TEXT,
    status TEXT DEFAULT 'active'
);

-- المواقع
CREATE TABLE locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    address TEXT,
    latitude DECIMAL(10,8),
    longitude DECIMAL(11,8),
    status TEXT DEFAULT 'active'
);

-- التحقيقات
CREATE TABLE investigations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    violation_id INTEGER,
    investigator_id INTEGER,
    start_date DATE,
    completion_date DATE,
    status TEXT, -- 'pending', 'in_progress', 'completed', 'closed'
    closed_by INTEGER,
    FOREIGN KEY (violation_id) REFERENCES violations(id),
    FOREIGN KEY (investigator_id) REFERENCES employees(id),
    FOREIGN KEY (closed_by) REFERENCES employees(id)
);

-- الإجراءات التصحيحية
CREATE TABLE corrective_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    violation_id INTEGER,
    action_description TEXT,
    responsible_person_id INTEGER,
    due_date DATE,
    completion_date DATE,
    status TEXT, -- 'pending', 'in_progress', 'completed'
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (violation_id) REFERENCES violations(id),
    FOREIGN KEY (responsible_person_id) REFERENCES employees(id)
);

-- المناطق غير المصرح بها
CREATE TABLE unauthorized_areas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    location_id INTEGER,
    description TEXT,
    status TEXT DEFAULT 'active',
    FOREIGN KEY (location_id) REFERENCES locations(id)
);
```

---

## 🔐 الصلاحيات

جميع صفحات Unauthorized Area Dashboard تتطلب:
- تسجيل الدخول (`@login_required`)
- صلاحية Admin فقط (`current_user.username == "admin"`)

---

## 📝 ملاحظات

- جميع الصفحات حالياً تعرض بيانات تجريبية (Mock Data)
- يجب ربط الصفحات بقاعدة البيانات الفعلية عند التنفيذ
- يمكن إضافة API endpoints منفصلة للـ AJAX calls
- يجب إضافة Pagination للجداول الكبيرة
- يجب إضافة Search و Filtering متقدم
- يمكن إضافة Real-time notifications للإنذارات
- يمكن إضافة Integration مع أنظمة الكاميرات

