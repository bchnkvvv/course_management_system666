from typing import Optional, List, Dict, Any, cast
import asyncpg
import json
from datetime import datetime

class NativeSQLCrud:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
    
    # ============= ИЕРАРХИЯ =============
    async def create_department(self, name: str, code: str, parent_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            query = """
            WITH inserted AS (
                INSERT INTO departments (name, code, parent_id)
                VALUES ($1, $2, $3)
                RETURNING id, name, code, parent_id, path, level, created_at
            )
            SELECT * FROM inserted
            """
            row = await conn.fetchrow(query, name, code, parent_id)
            if row:
                # Преобразуем bytes ключи в str
                return {str(k): v for k, v in row.items()}
            return None
    
    async def get_department_tree(self, root_id: Optional[int] = None) -> List[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            if root_id:
                query = """
                WITH RECURSIVE dept_tree AS (
                    SELECT id, name, code, parent_id, path, level, created_at
                    FROM departments
                    WHERE id = $1 AND is_deleted = FALSE
                    
                    UNION ALL
                    
                    SELECT d.id, d.name, d.code, d.parent_id, d.path, d.level, d.created_at
                    FROM departments d
                    INNER JOIN dept_tree dt ON d.parent_id = dt.id
                    WHERE d.is_deleted = FALSE
                )
                SELECT * FROM dept_tree ORDER BY path
                """
                rows = await conn.fetch(query, root_id)
            else:
                query = """
                WITH RECURSIVE dept_tree AS (
                    SELECT id, name, code, parent_id, path, level, created_at
                    FROM departments
                    WHERE parent_id IS NULL AND is_deleted = FALSE
                    
                    UNION ALL
                    
                    SELECT d.id, d.name, d.code, d.parent_id, d.path, d.level, d.created_at
                    FROM departments d
                    INNER JOIN dept_tree dt ON d.parent_id = dt.id
                    WHERE d.is_deleted = FALSE
                )
                SELECT * FROM dept_tree ORDER BY path
                """
                rows = await conn.fetch(query)
            
            # Преобразуем все строки в dict со строковыми ключами
            departments = {}
            for row in rows:
                dept = {str(k): v for k, v in row.items()}
                dept['children'] = []
                departments[dept['id']] = dept
            
            tree = []
            for dept in departments.values():
                if dept['parent_id'] is None:
                    tree.append(dept)
                else:
                    if dept['parent_id'] in departments:
                        departments[dept['parent_id']]['children'].append(dept)
            
            return tree
    
    # ============= НАСЛЕДОВАНИЕ =============
    async def create_student(self, student_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                person_query = """
                INSERT INTO persons (full_name, email, phone, person_type)
                VALUES ($1, $2, $3, 'student')
                RETURNING id, full_name, email, phone, created_at, is_active
                """
                person = await conn.fetchrow(
                    person_query,
                    student_data['full_name'],
                    student_data['email'],
                    student_data.get('phone')
                )
                
                if not person:
                    return None
                
                student_query = """
                INSERT INTO students (person_id, student_card_number, group_name, enrollment_year, average_grade)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING *
                """
                student = await conn.fetchrow(
                    student_query,
                    person['id'],
                    student_data['student_card_number'],
                    student_data['group_name'],
                    student_data['enrollment_year'],
                    student_data.get('average_grade')
                )
                
                if not student:
                    return None
                
                result = {str(k): v for k, v in person.items()}
                result.update({str(k): v for k, v in student.items()})
                return result
    
    async def create_teacher(self, teacher_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                person_query = """
                INSERT INTO persons (full_name, email, phone, person_type)
                VALUES ($1, $2, $3, 'teacher')
                RETURNING id, full_name, email, phone, created_at, is_active
                """
                person = await conn.fetchrow(
                    person_query,
                    teacher_data['full_name'],
                    teacher_data['email'],
                    teacher_data.get('phone')
                )
                
                if not person:
                    return None
                
                teacher_query = """
                INSERT INTO teachers (person_id, employee_number, academic_degree, position, department_id)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING *
                """
                teacher = await conn.fetchrow(
                    teacher_query,
                    person['id'],
                    teacher_data['employee_number'],
                    teacher_data.get('academic_degree'),
                    teacher_data.get('position'),
                    teacher_data.get('department_id')
                )
                
                if not teacher:
                    return None
                
                result = {str(k): v for k, v in person.items()}
                result.update({str(k): v for k, v in teacher.items()})
                return result
    
    async def get_person_by_id(self, person_id: int, person_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            if person_type == "student":
                query = """
                SELECT p.*, s.student_card_number, s.group_name, s.enrollment_year, s.average_grade
                FROM persons p
                JOIN students s ON p.id = s.person_id
                WHERE p.id = $1 AND p.is_deleted = FALSE
                """
            elif person_type == "teacher":
                query = """
                SELECT p.*, t.employee_number, t.academic_degree, t.position, t.department_id
                FROM persons p
                JOIN teachers t ON p.id = t.person_id
                WHERE p.id = $1 AND p.is_deleted = FALSE
                """
            else:
                query = "SELECT * FROM persons WHERE id = $1 AND is_deleted = FALSE"
            
            row = await conn.fetchrow(query, person_id)
            if row:
                return {str(k): v for k, v in row.items()}
            return None
    
    # ============= ВЕРСИОНИРОВАНИЕ =============
    async def create_course(self, code: str, version_data: Dict[str, Any], created_by: int) -> Optional[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                course_query = """
                INSERT INTO courses (code)
                VALUES ($1)
                RETURNING id, code, created_at
                """
                course = await conn.fetchrow(course_query, code)
                
                if not course:
                    return None
                
                version_query = """
                SELECT create_new_course_version(
                    $1, $2, $3, $4, $5, $6, $7, $8, $9
                ) as version_id
                """
                version_id = await conn.fetchval(
                    version_query,
                    course['id'],
                    version_data['title'],
                    version_data.get('description', ''),
                    version_data['credits'],
                    version_data['hours_total'],
                    version_data.get('hours_lecture', 0),
                    version_data.get('hours_practice', 0),
                    version_data.get('hours_lab', 0),
                    created_by
                )
                
                version_info_query = """
                SELECT cv.*, c.code as course_code
                FROM course_versions cv
                JOIN courses c ON cv.course_id = c.id
                WHERE cv.id = $1
                """
                version = await conn.fetchrow(version_info_query, version_id)
                
                if not version:
                    return None
                
                return {
                    "course": {str(k): v for k, v in course.items()},
                    "version": {str(k): v for k, v in version.items()}
                }
    
    async def update_course(
        self, 
        course_id: int, 
        update_data: Dict[str, Any], 
        changed_by: int, 
        change_reason: str = ""  # Изменено: None -> ""
    ) -> Optional[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                current_query = """
                SELECT * FROM course_versions 
                WHERE course_id = $1 AND is_current = TRUE
                """
                current = await conn.fetchrow(current_query, course_id)
                
                if not current:
                    raise ValueError(f"Course {course_id} not found")
                
                next_version_query = """
                SELECT COALESCE(MAX(version_number), 0) + 1
                FROM course_versions
                WHERE course_id = $1
                """
                next_version = await conn.fetchval(next_version_query, course_id)
                
                new_version_query = """
                INSERT INTO course_versions (
                    course_id, version_number, title, description, credits,
                    hours_total, hours_lecture, hours_practice, hours_lab,
                    status, created_by, is_current
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, TRUE)
                RETURNING id, version_number, title, description, credits, hours_total, created_at
                """
                
                new_version_data = {
                    "title": update_data.get("title", current['title']),
                    "description": update_data.get("description", current['description']),
                    "credits": update_data.get("credits", current['credits']),
                    "hours_total": update_data.get("hours_total", current['hours_total']),
                    "hours_lecture": update_data.get("hours_lecture", current['hours_lecture']),
                    "hours_practice": update_data.get("hours_practice", current['hours_practice']),
                    "hours_lab": update_data.get("hours_lab", current['hours_lab']),
                    "status": update_data.get("status", current['status'])
                }
                
                new_version = await conn.fetchrow(
                    new_version_query,
                    course_id, next_version,
                    new_version_data['title'],
                    new_version_data['description'],
                    new_version_data['credits'],
                    new_version_data['hours_total'],
                    new_version_data['hours_lecture'],
                    new_version_data['hours_practice'],
                    new_version_data['hours_lab'],
                    new_version_data['status'],
                    changed_by
                )
                
                if not new_version:
                    return None
                
                await conn.execute(
                    "UPDATE course_versions SET is_current = FALSE WHERE id = $1",
                    current['id']
                )
                
                await conn.execute(
                    "UPDATE courses SET current_version_id = $1 WHERE id = $2",
                    new_version['id'], course_id
                )
                
                snapshot = {
                    "course_id": course_id,
                    "version_number": next_version,
                    "data": new_version_data,
                    "previous_version": current['version_number']
                }
                
                await conn.execute("""
                    UPDATE versions SET is_current = FALSE
                    WHERE entity_type = 'course' AND entity_id = $1 AND is_current = TRUE
                """, course_id)
                
                await conn.execute("""
                    INSERT INTO versions (entity_type, entity_id, version_number, snapshot, changed_by, change_reason, is_current)
                    VALUES ('course', $1, $2, $3, $4, $5, TRUE)
                """, course_id, next_version, json.dumps(snapshot), changed_by, change_reason)
                
                return {str(k): v for k, v in new_version.items()}
    
    async def get_course_versions(self, course_id: int) -> List[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            query = """
            SELECT * FROM course_versions
            WHERE course_id = $1
            ORDER BY version_number DESC
            """
            rows = await conn.fetch(query, course_id)
            return [{str(k): v for k, v in row.items()} for row in rows]
    
    async def get_version_snapshot(self, entity_type: str, entity_id: int, version_number: int) -> Optional[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            query = """
            SELECT snapshot FROM versions
            WHERE entity_type = $1 AND entity_id = $2 AND version_number = $3
            """
            snapshot = await conn.fetchval(query, entity_type, entity_id, version_number)
            if snapshot:
                # snapshot уже должен быть dict, но если это строка - парсим
                if isinstance(snapshot, str):
                    return json.loads(snapshot)
                return dict(snapshot) if snapshot else None
            return None
    
    async def get_courses_list(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Получение списка курсов"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    c.id, c.code, c.created_at,
                    cv.id as version_id, cv.version_number, cv.title, 
                    cv.description, cv.credits, cv.hours_total, cv.status
                FROM courses c
                LEFT JOIN course_versions cv ON c.current_version_id = cv.id
                WHERE c.is_deleted = FALSE
                ORDER BY c.id DESC
                LIMIT $1 OFFSET $2
            """, limit, offset)
            
            courses = []
            for row in rows:
                course = {str(k): v for k, v in row.items() if k != 'version_id'}
                course['current_version'] = None
                course['all_versions'] = []
                
                if row['version_id']:
                    course['current_version'] = {
                        'id': row['version_id'],
                        'version_number': row['version_number'],
                        'title': row['title'],
                        'description': row['description'],
                        'credits': row['credits'],
                        'hours_total': row['hours_total'],
                        'status': row['status']
                    }
                
                courses.append(course)
            
            return courses
    
    # ============= РАСПИСАНИЕ =============
    async def create_schedule_entry(self, entry_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            query = """
            INSERT INTO schedule_entries (
                course_version_id, teacher_id, semester, academic_year,
                day_of_week, start_time, end_time, room, lesson_type, student_group
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING *
            """
            row = await conn.fetchrow(
                query,
                entry_data['course_version_id'],
                entry_data['teacher_id'],
                entry_data['semester'],
                entry_data['academic_year'],
                entry_data['day_of_week'],
                entry_data['start_time'],
                entry_data['end_time'],
                entry_data['room'],
                entry_data['lesson_type'],
                entry_data['student_group']
            )
            if row:
                return {str(k): v for k, v in row.items()}
            return None
    
    async def get_schedule_by_group(self, group_name: str, semester: Optional[int] = None) -> List[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            query = """
            SELECT 
                se.*,
                cv.title as course_title,
                p.full_name as teacher_name
            FROM schedule_entries se
            JOIN course_versions cv ON se.course_version_id = cv.id
            JOIN teachers t ON se.teacher_id = t.person_id
            JOIN persons p ON t.person_id = p.id
            WHERE se.student_group = $1 AND se.is_cancelled = FALSE
            """
            params: List[Any] = [group_name]
            
            if semester is not None:  # Изменено: проверка на None
                query += " AND se.semester = $2"
                params.append(semester)
            
            query += " ORDER BY se.day_of_week, se.start_time"
            
            rows = await conn.fetch(query, *params)
            return [{str(k): v for k, v in row.items()} for row in rows]
    
    # ============= ЛОГИЧЕСКОЕ УДАЛЕНИЕ =============
    async def soft_delete_course(self, course_id: int) -> bool:
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE courses SET is_deleted = TRUE WHERE id = $1",
                course_id
            )
            return result == "UPDATE 1"