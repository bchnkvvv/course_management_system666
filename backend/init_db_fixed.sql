-- =====================================================
-- COURSE MANAGEMENT SYSTEM - FIXED VERSION
-- =====================================================

DROP TABLE IF EXISTS schedule_entries CASCADE;
DROP TABLE IF EXISTS versions CASCADE;
DROP TABLE IF EXISTS course_versions CASCADE;
DROP TABLE IF EXISTS course_assignments CASCADE;
DROP TABLE IF EXISTS courses CASCADE;
DROP TABLE IF EXISTS teachers CASCADE;
DROP TABLE IF EXISTS students CASCADE;
DROP TABLE IF EXISTS persons CASCADE;
DROP TABLE IF EXISTS departments CASCADE;

-- 1. DEPARTMENTS HIERARCHY
CREATE TABLE departments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    code VARCHAR(20) UNIQUE NOT NULL,
    parent_id INTEGER REFERENCES departments(id) ON DELETE CASCADE,
    path VARCHAR(500),
    level INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_departments_parent ON departments(parent_id);
CREATE INDEX idx_departments_path ON departments(path);
CREATE INDEX idx_departments_level ON departments(level);
CREATE INDEX idx_departments_is_deleted ON departments(is_deleted);

CREATE OR REPLACE FUNCTION update_department_path()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.parent_id IS NULL THEN
        NEW.path = CAST(NEW.id AS TEXT);
        NEW.level = 0;
    ELSE
        SELECT path || '.' || NEW.id INTO NEW.path 
        FROM departments WHERE id = NEW.parent_id;
        NEW.level = (SELECT level + 1 FROM departments WHERE id = NEW.parent_id);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_department_path
    BEFORE INSERT ON departments
    FOR EACH ROW
    EXECUTE FUNCTION update_department_path();

-- 2. INHERITANCE
CREATE TABLE persons (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(200) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    phone VARCHAR(20),
    person_type VARCHAR(50) NOT NULL CHECK (person_type IN ('student', 'teacher', 'admin')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    is_deleted BOOLEAN DEFAULT FALSE
);

CREATE TABLE students (
    person_id INTEGER PRIMARY KEY REFERENCES persons(id) ON DELETE CASCADE,
    student_card_number VARCHAR(50) UNIQUE,
    group_name VARCHAR(100),
    enrollment_year INTEGER,
    average_grade DECIMAL(3,2) CHECK (average_grade >= 0 AND average_grade <= 5)
);

CREATE TABLE teachers (
    person_id INTEGER PRIMARY KEY REFERENCES persons(id) ON DELETE CASCADE,
    employee_number VARCHAR(50) UNIQUE,
    academic_degree VARCHAR(100),
    position VARCHAR(100),
    department_id INTEGER REFERENCES departments(id)
);

CREATE TABLE admins (
    person_id INTEGER PRIMARY KEY REFERENCES persons(id) ON DELETE CASCADE,
    admin_level INTEGER DEFAULT 1,
    access_rights TEXT[]
);

-- 3. VERSIONING
CREATE TABLE courses (
    id SERIAL PRIMARY KEY,
    code VARCHAR(20) UNIQUE NOT NULL,
    current_version_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE
);

CREATE TABLE course_versions (
    id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    title VARCHAR(300) NOT NULL,
    description TEXT,
    credits INTEGER CHECK (credits > 0),
    hours_total INTEGER CHECK (hours_total > 0),
    hours_lecture INTEGER DEFAULT 0,
    hours_practice INTEGER DEFAULT 0,
    hours_lab INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'draft',
    created_by INTEGER REFERENCES persons(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_current BOOLEAN DEFAULT FALSE,
    UNIQUE(course_id, version_number)
);

CREATE TABLE versions (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    entity_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    snapshot JSONB NOT NULL,
    changed_by INTEGER REFERENCES persons(id),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    change_reason TEXT,
    is_current BOOLEAN DEFAULT FALSE,
    UNIQUE(entity_type, entity_id, version_number)
);

-- 4. SCHEDULE
CREATE TABLE schedule_entries (
    id SERIAL PRIMARY KEY,
    course_version_id INTEGER NOT NULL REFERENCES course_versions(id) ON DELETE CASCADE,
    teacher_id INTEGER NOT NULL REFERENCES teachers(person_id) ON DELETE CASCADE,
    semester INTEGER NOT NULL CHECK (semester BETWEEN 1 AND 8),
    academic_year VARCHAR(9),
    day_of_week INTEGER CHECK (day_of_week BETWEEN 1 AND 7),
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    room VARCHAR(50),
    lesson_type VARCHAR(50) CHECK (lesson_type IN ('lecture', 'practice', 'lab', 'exam')),
    student_group VARCHAR(100),
    is_cancelled BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(course_version_id, teacher_id, day_of_week, start_time, room)
);

CREATE INDEX idx_schedule_course ON schedule_entries(course_version_id);
CREATE INDEX idx_schedule_teacher ON schedule_entries(teacher_id);
CREATE INDEX idx_schedule_datetime ON schedule_entries(day_of_week, start_time);
CREATE INDEX idx_schedule_group ON schedule_entries(student_group);

-- 5. COURSE ASSIGNMENTS
CREATE TABLE course_assignments (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(person_id) ON DELETE CASCADE,
    course_version_id INTEGER NOT NULL REFERENCES course_versions(id) ON DELETE CASCADE,
    enrollment_date DATE DEFAULT CURRENT_DATE,
    grade DECIMAL(3,2),
    status VARCHAR(50) DEFAULT 'enrolled',
    UNIQUE(student_id, course_version_id)
);

CREATE INDEX idx_assignments_student ON course_assignments(student_id);
CREATE INDEX idx_assignments_course ON course_assignments(course_version_id);
CREATE INDEX idx_assignments_status ON course_assignments(status);

-- 6. VERSIONING FUNCTION
CREATE OR REPLACE FUNCTION create_new_course_version(
    p_course_id INTEGER,
    p_title VARCHAR,
    p_description TEXT,
    p_credits INTEGER,
    p_hours_total INTEGER,
    p_hours_lecture INTEGER,
    p_hours_practice INTEGER,
    p_hours_lab INTEGER,
    p_created_by INTEGER
)
RETURNS INTEGER AS $$
DECLARE
    v_new_version_number INTEGER;
    v_new_version_id INTEGER;
BEGIN
    SELECT COALESCE(MAX(version_number), 0) + 1 
    INTO v_new_version_number
    FROM course_versions
    WHERE course_id = p_course_id;
    
    INSERT INTO course_versions (
        course_id, version_number, title, description, credits,
        hours_total, hours_lecture, hours_practice, hours_lab,
        created_by, is_current
    ) VALUES (
        p_course_id, v_new_version_number, p_title, p_description, p_credits,
        p_hours_total, p_hours_lecture, p_hours_practice, p_hours_lab,
        p_created_by, TRUE
    )
    RETURNING id INTO v_new_version_id;
    
    UPDATE course_versions 
    SET is_current = FALSE 
    WHERE course_id = p_course_id AND id != v_new_version_id;
    
    UPDATE courses 
    SET current_version_id = v_new_version_id 
    WHERE id = p_course_id;
    
    RETURN v_new_version_id;
END;
$$ LANGUAGE plpgsql;

-- 7. TEST DATA (ENGLISH ONLY)
INSERT INTO departments (name, code, parent_id) VALUES 
('Institute of Information Technologies', 'IIT', NULL),
('Software Engineering Faculty', 'SEF', 1),
('Software Development Department', 'SDD', 2),
('Database Department', 'DBD', 2),
('System Analysis Faculty', 'SAF', 1);

INSERT INTO persons (full_name, email, phone, person_type) VALUES
('Ivan Ivanov', 'ivan.ivanov@college.ru', '+7-999-123-4567', 'teacher'),
('Maria Petrova', 'maria.petrova@college.ru', '+7-999-234-5678', 'teacher'),
('Alexey Sidorov', 'alexey.sidorov@college.ru', '+7-999-345-6789', 'student'),
('Elena Kuznetsova', 'elena.kuznetsova@college.ru', '+7-999-456-7890', 'student');

INSERT INTO teachers (person_id, employee_number, academic_degree, position, department_id) VALUES
(1, 'TCH001', 'PhD', 'Associate Professor', 3),
(2, 'TCH002', 'Dr.Sc.', 'Professor', 4);

INSERT INTO students (person_id, student_card_number, group_name, enrollment_year, average_grade) VALUES
(3, 'ST001', 'PI-31', 2023, 4.5),
(4, 'ST002', 'PI-31', 2023, 4.8);

INSERT INTO courses (code) VALUES ('CS101'), ('CS102');

SELECT create_new_course_version(1, 'Programming Basics', 'Introduction to algorithms', 4, 64, 32, 16, 16, 1);
SELECT create_new_course_version(2, 'Databases', 'SQL and DB design', 5, 80, 40, 20, 20, 2);

INSERT INTO schedule_entries (course_version_id, teacher_id, semester, academic_year, day_of_week, start_time, end_time, room, lesson_type, student_group) VALUES
(1, 1, 1, '2024-2025', 1, '09:00', '10:30', 'A-201', 'lecture', 'PI-31'),
(2, 2, 2, '2024-2025', 3, '11:00', '12:30', 'A-305', 'practice', 'PI-31');

INSERT INTO course_assignments (student_id, course_version_id, status) VALUES
(3, 1, 'enrolled'),
(3, 2, 'enrolled');

COMMIT;