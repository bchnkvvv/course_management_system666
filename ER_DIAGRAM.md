# ER-диаграмма системы управления учебными курсами

## Таблицы и связи

### departments (иерархия департаментов)
- id (PK)
- name (название)
- code (код, уникальный)
- parent_id (FK -> departments.id)
- path (материализованный путь)
- level (уровень вложенности)
- is_deleted (логическое удаление)

### persons (базовая таблица наследования)
- id (PK)
- full_name (ФИО)
- email (уникальный)
- phone (телефон)
- person_type (student/teacher/admin)

### students (наследник persons)
- person_id (PK, FK -> persons.id)
- student_card_number (номер студенческого)
- group_name (группа)
- enrollment_year (год поступления)
- average_grade (средний балл)

### teachers (наследник persons)
- person_id (PK, FK -> persons.id)
- employee_number (табельный номер)
- academic_degree (ученая степень)
- position (должность)
- department_id (FK -> departments.id)

### courses
- id (PK)
- code (код курса, уникальный)
- current_version_id (FK -> course_versions.id)
- is_deleted (логическое удаление)

### course_versions (версионирование)
- id (PK)
- course_id (FK -> courses.id)
- version_number (номер версии)
- title (название)
- credits (кредиты)
- hours_total (часов всего)
- is_current (актуальная версия)

### versions (универсальное версионирование)
- id (PK)
- entity_type (тип сущности: course, department)
- entity_id (ID сущности)
- version_number (номер версии)
- snapshot (JSONB снимок данных)
- change_reason (причина изменения)

### schedule_entries (расписание)
- id (PK)
- course_version_id (FK -> course_versions.id)
- teacher_id (FK -> teachers.person_id)
- semester (семестр)
- day_of_week (день недели)
- start_time (время начала)
- student_group (группа)

## Связи (отношения)

departments 1───* teachers
departments *───1 departments (самореференция для иерархии)

persons 1───1 students
persons 1───1 teachers

courses 1───* course_versions
course_versions 1───1 courses (через current_version_id)

course_versions 1───* schedule_entries
teachers 1───* schedule_entries

course_versions 1───* versions (для сущности course)