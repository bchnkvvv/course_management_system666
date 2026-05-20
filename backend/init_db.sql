-- =====================================================
-- СИСТЕМА УПРАВЛЕНИЯ УЧЕБНЫМИ КУРСАМИ
-- Схема базы данных с иерархией, наследованием и версионированием
-- =====================================================

-- Удаление старых таблиц (для чистой установки)
DROP TABLE IF EXISTS schedule_entries CASCADE;
DROP TABLE IF EXISTS versions CASCADE;
DROP TABLE IF EXISTS course_versions CASCADE;
DROP TABLE IF EXISTS person_versions CASCADE;
DROP TABLE IF EXISTS course_assignments CASCADE;
DROP TABLE IF EXISTS courses CASCADE;
DROP TABLE IF EXISTS persons CASCADE;
DROP TABLE IF EXISTS departments CASCADE;

-- =====================================================
-- 1. ИЕРАРХИЯ (департаменты/кафедры - древовидная структура)
-- =====================================================
-- Выбрана стратегия: Materialized Path + Adjacency List
-- Обоснование: простота получения поддеревьев и быстрый поиск предков

CREATE TABLE departments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    code VARCHAR(20) UNIQUE NOT NULL,
    parent_id INTEGER REFERENCES departments(id) ON DELETE CASCADE,
    path VARCHAR(500),  -- материализованный путь для быстрого получения иерархии
    level INTEGER DEFAULT 0,  -- уровень вложенности
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE
);

-- Индексы для иерархических запросов
CREATE INDEX idx_departments_parent ON departments(parent_id);
CREATE INDEX idx_departments_path ON departments(path);
CREATE INDEX idx_departments_level ON departments(level);
CREATE INDEX idx_departments_is_deleted ON departments(is_deleted);

-- Функция автоматического обновления path и level
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

-- =====================================================
-- 2. НАСЛЕДОВАНИЕ (Table per Type - TPT стратегия)
-- =====================================================
-- Обоснование: минимальная избыточность, полное использование типов,
-- лучшая поддержка внешних ключей и индексов

-- Базовая таблица Person
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

-- Таблица-наследник: Student
CREATE TABLE students (
    person_id INTEGER PRIMARY KEY REFERENCES persons(id) ON DELETE CASCADE,
    student_card_number VARCHAR(50) UNIQUE,
    group_name VARCHAR(100),
    enrollment_year INTEGER,
    average_grade DECIMAL(3,2) CHECK (average_grade >= 0 AND average_grade <= 5)
);

-- Таблица-наследник: Teacher
CREATE TABLE teachers (
    person_id INTEGER PRIMARY KEY REFERENCES persons(id) ON DELETE CASCADE,
    employee_number VARCHAR(50) UNIQUE,
    academic_degree VARCHAR(100),  -- кандидат наук, доктор наук
    position VARCHAR(100),  -- профессор, доцент, старший преподаватель
    department_id INTEGER REFERENCES departments(id)
);

-- Таблица-наследник: Admin (для полноты)
CREATE TABLE admins (
    person_id INTEGER PRIMARY KEY REFERENCES persons(id) ON DELETE CASCADE,
    admin_level INTEGER DEFAULT 1,
    access_rights TEXT[]
);

-- =====================================================
-- 3. ВЕРСИОНИРОВАНИЕ (для Course)
-- =====================================================
-- Стратегия: отдельная таблица версий + основная таблица ссылается на актуальную версию

-- Основная таблица курсов (хранит ссылки на текущую версию)
CREATE TABLE courses (
    id SERIAL PRIMARY KEY,
    code VARCHAR(20) UNIQUE NOT NULL,
    current_version_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE
);

-- Таблица версий курсов
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
    status VARCHAR(50) DEFAULT 'draft', -- draft, published, archived
    created_by INTEGER REFERENCES persons(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_current BOOLEAN DEFAULT FALSE,
    UNIQUE(course_id, version_number)
);

-- Добавление внешнего ключа после создания course_versions
ALTER TABLE courses 
ADD CONSTRAINT fk_current_version 
FOREIGN KEY (current_version_id) REFERENCES course_versions(id);

-- Индексы для версионирования
CREATE INDEX idx_course_versions_course ON course_versions(course_id);
CREATE INDEX idx_course_versions_current ON course_versions(is_current);
CREATE INDEX idx_course_versions_status ON course_versions(status);
CREATE INDEX idx_course_versions_created ON course_versions(created_at);

-- Универсальная таблица версионирования для любых сущностей (расширяемость)
CREATE TABLE versions (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    entity_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    snapshot JSONB NOT NULL,  -- полная копия состояния сущности
    changed_by INTEGER REFERENCES persons(id),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    change_reason TEXT,
    is_current BOOLEAN DEFAULT FALSE,
    UNIQUE(entity_type, entity_id, version_number)
);

CREATE INDEX idx_versions_entity ON versions(entity_type, entity_id);
CREATE INDEX idx_versions_current ON versions(entity_type, entity_id, is_current);
CREATE INDEX idx_versions_snapshot ON versions USING GIN (snapshot);

-- =====================================================
-- 4. РАСПИСАНИЕ (связующая таблица)
-- =====================================================

CREATE TABLE schedule_entries (
    id SERIAL PRIMARY KEY,
    course_version_id INTEGER NOT NULL REFERENCES course_versions(id) ON DELETE CASCADE,
    teacher_id INTEGER NOT NULL REFERENCES teachers(person_id) ON DELETE CASCADE,
    semester INTEGER NOT NULL CHECK (semester BETWEEN 1 AND 8),
    academic_year VARCHAR(9), -- 2024-2025
    day_of_week INTEGER CHECK (day_of_week BETWEEN 1 AND 7), -- 1=Monday, 7=Sunday
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

-- Индексы для расписания
CREATE INDEX idx_schedule_course ON schedule_entries(course_version_id);
CREATE INDEX idx_schedule_teacher ON schedule_entries(teacher_id);
CREATE INDEX idx_schedule_datetime ON schedule_entries(day_of_week, start_time);
CREATE INDEX idx_schedule_group ON schedule_entries(student_group);
CREATE INDEX idx_schedule_semester ON schedule_entries(semester);

-- =====================================================
-- 5. СВЯЗЬ СТУДЕНТ-КУРС (многие ко многим)
-- =====================================================

CREATE TABLE course_assignments (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(person_id) ON DELETE CASCADE,
    course_version_id INTEGER NOT NULL REFERENCES course_versions(id) ON DELETE CASCADE,
    enrollment_date DATE DEFAULT CURRENT_DATE,
    grade DECIMAL(3,2),
    status VARCHAR(50) DEFAULT 'enrolled', -- enrolled, completed, dropped
    UNIQUE(student_id, course_version_id)
);

CREATE INDEX idx_assignments_student ON course_assignments(student_id);
CREATE INDEX idx_assignments_course ON course_assignments(course_version_id);
CREATE INDEX idx_assignments_status ON course_assignments(status);

-- =====================================================
-- 6. ФУНКЦИИ ДЛЯ ВЕРСИОНИРОВАНИЯ
-- =====================================================

-- Функция создания новой версии курса (UPDATE не перезаписывает, а создаёт новую)
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
    -- Получаем следующий номер версии
    SELECT COALESCE(MAX(version_number), 0) + 1 
    INTO v_new_version_number
    FROM course_versions
    WHERE course_id = p_course_id;
    
    -- Создаём новую версию
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
    
    -- Помечаем старые версии как неактуальные
    UPDATE course_versions 
    SET is_current = FALSE 
    WHERE course_id = p_course_id AND id != v_new_version_id;
    
    -- Обновляем ссылку на текущую версию в основной таблице
    UPDATE courses 
    SET current_version_id = v_new_version_id 
    WHERE id = p_course_id;
    
    RETURN v_new_version_id;
END;
$$ LANGUAGE plpgsql;

-- Триггер для автоматического версионирования при UPDATE (пример для departments)
CREATE OR REPLACE FUNCTION version_department_update()
RETURNS TRIGGER AS $$
BEGIN
    -- Сохраняем старую версию в таблицу versions
    INSERT INTO versions (entity_type, entity_id, version_number, snapshot, changed_at, is_current)
    VALUES (
        'department',
        OLD.id,
        (SELECT COALESCE(MAX(version_number), 0) + 1 FROM versions WHERE entity_type = 'department' AND entity_id = OLD.id),
        row_to_json(OLD),
        CURRENT_TIMESTAMP,
        FALSE
    );
    
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_version_department
    BEFORE UPDATE ON departments
    FOR EACH ROW
    EXECUTE FUNCTION version_department_update();

-- =====================================================
-- 7. ТЕСТОВЫЕ ДАННЫЕ
-- =====================================================

-- Добавляем департаменты (иерархия)
INSERT INTO departments (name, code, parent_id) VALUES 
('Институт информационных технологий', 'IIT', NULL),
('Факультет программной инженерии', 'PI', 1),
('Кафедра разработки ПО', 'RPO', 2),
('Кафедра баз данных', 'BD', 2),
('Факультет системного анализа', 'SA', 1);

-- Добавляем персон
INSERT INTO persons (full_name, email, phone, person_type) VALUES
('Иванов Иван Иванович', 'ivan.ivanov@college.ru', '+7-999-123-4567', 'teacher'),
('Петрова Мария Сергеевна', 'maria.petrova@college.ru', '+7-999-234-5678', 'teacher'),
('Сидоров Алексей Владимирович', 'alexey.sidorov@college.ru', '+7-999-345-6789', 'student'),
('Кузнецова Елена Андреевна', 'elena.kuznetsova@college.ru', '+7-999-456-7890', 'student');

-- Добавляем учителей
INSERT INTO teachers (person_id, employee_number, academic_degree, position, department_id) VALUES
(1, 'TCH001', 'Кандидат технических наук', 'Доцент', 3),
(2, 'TCH002', 'Доктор наук', 'Профессор', 4);

-- Добавляем студентов
INSERT INTO students (person_id, student_card_number, group_name, enrollment_year, average_grade) VALUES
(3, 'ST001', 'ПИ-31', 2023, 4.5),
(4, 'ST002', 'ПИ-31', 2023, 4.8);

-- Добавляем курсы
INSERT INTO courses (code) VALUES ('CS101'), ('CS102');

-- Добавляем версии курсов (первая версия)
SELECT create_new_course_version(1, 'Основы программирования', 'Введение в алгоритмы и структуры данных', 4, 64, 32, 16, 16, 1);
SELECT create_new_course_version(2, 'Базы данных', 'SQL и проектирование БД', 5, 80, 40, 20, 20, 2);

-- Добавляем расписание
INSERT INTO schedule_entries (course_version_id, teacher_id, semester, academic_year, day_of_week, start_time, end_time, room, lesson_type, student_group) VALUES
(1, 1, 1, '2024-2025', 1, '09:00', '10:30', 'А-201', 'lecture', 'ПИ-31'),
(2, 2, 2, '2024-2025', 3, '11:00', '12:30', 'А-305', 'practice', 'ПИ-31');

-- Добавляем назначения курсов студентам
INSERT INTO course_assignments (student_id, course_version_id, status) VALUES
(1, 1, 'enrolled'),
(1, 2, 'enrolled');

COMMIT;