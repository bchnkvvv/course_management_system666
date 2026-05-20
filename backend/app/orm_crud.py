from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.orm import selectinload
from typing import Optional, List, Dict, Any
from datetime import datetime
import json

from app.models_orm import (
    Department, Person, Student, Teacher, Course, 
    CourseVersion, ScheduleEntry, CourseAssignment, Version
)
from app.schemas import DepartmentCreate, StudentCreate, TeacherCreate, CourseVersionCreate

class ORMCrud:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # ============= ИЕРАРХИЯ =============
    async def create_department(self, dept_data: DepartmentCreate) -> Department:
        dept = Department(**dept_data.model_dump())
        self.db.add(dept)
        await self.db.flush()
        await self.db.refresh(dept)
        return dept
    
    async def get_department_tree(self, root_id: Optional[int] = None) -> List[Department]:
        """Получение иерархического дерева департаментов"""
        if root_id:
            query = select(Department).where(
                Department.id == root_id,
                Department.is_deleted == False
            )
        else:
            query = select(Department).where(
                Department.parent_id.is_(None),
                Department.is_deleted == False
            )
        
        result = await self.db.execute(query)
        roots = list(result.scalars().all())
        
        async def load_children(dept: Department) -> Department:
            child_query = select(Department).where(
                Department.parent_id == dept.id,
                Department.is_deleted == False
            )
            child_result = await self.db.execute(child_query)
            children = list(child_result.scalars().all())
            dept.children = children
            for child in children:
                await load_children(child)
            return dept
        
        for root in roots:
            await load_children(root)
        
        return roots
    
    # ============= НАСЛЕДОВАНИЕ =============
    async def create_student(self, student_data: StudentCreate) -> Student:
        # Сначала создаем базовую запись Person
        person = Person(
            full_name=student_data.full_name,
            email=student_data.email,
            phone=student_data.phone,
            person_type="student",
            is_active=True,
            is_deleted=False
        )
        self.db.add(person)
        await self.db.flush()
        
        # Затем создаем студента
        student = Student(
            person_id=person.id,
            student_card_number=student_data.student_card_number,
            group_name=student_data.group_name,
            enrollment_year=student_data.enrollment_year,
            average_grade=student_data.average_grade
        )
        self.db.add(student)
        await self.db.flush()
        await self.db.refresh(student)
        
        return student
    
    async def create_teacher(self, teacher_data: TeacherCreate) -> Teacher:
        person = Person(
            full_name=teacher_data.full_name,
            email=teacher_data.email,
            phone=teacher_data.phone,
            person_type="teacher",
            is_active=True,
            is_deleted=False
        )
        self.db.add(person)
        await self.db.flush()
        
        teacher = Teacher(
            person_id=person.id,
            employee_number=teacher_data.employee_number,
            academic_degree=teacher_data.academic_degree,
            position=teacher_data.position,
            department_id=teacher_data.department_id
        )
        self.db.add(teacher)
        await self.db.flush()
        await self.db.refresh(teacher)
        
        return teacher
    
    async def get_person_by_id(self, person_id: int, person_type: Optional[str] = None) -> Optional[Person]:
        if person_type == "student":
            query = select(Student).where(Student.person_id == person_id, Student.is_deleted == False)
        elif person_type == "teacher":
            query = select(Teacher).where(Teacher.person_id == person_id, Teacher.is_deleted == False)
        else:
            query = select(Person).where(Person.id == person_id, Person.is_deleted == False)
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_all_students(self) -> List[Student]:
        """Получение всех студентов"""
        query = select(Student).where(Student.is_deleted == False)
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_all_teachers(self) -> List[Teacher]:
        """Получение всех преподавателей"""
        query = select(Teacher).where(Teacher.is_deleted == False)
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    # ============= ВЕРСИОНИРОВАНИЕ =============
    async def create_course(self, code: str, version_data: CourseVersionCreate, created_by: int) -> Course:
        # Создаем курс
        course = Course(code=code, is_deleted=False)
        self.db.add(course)
        await self.db.flush()
        
        # Создаем первую версию
        version = CourseVersion(
            course_id=course.id,
            version_number=1,
            title=version_data.title,
            description=version_data.description,
            credits=version_data.credits,
            hours_total=version_data.hours_total,
            hours_lecture=version_data.hours_lecture,
            hours_practice=version_data.hours_practice,
            hours_lab=version_data.hours_lab,
            status=version_data.status,
            created_by=created_by,
            is_current=True
        )
        self.db.add(version)
        await self.db.flush()
        
        # Обновляем ссылку на текущую версию
        course.current_version_id = version.id
        await self.db.flush()
        await self.db.refresh(course, ['versions', 'current_version'])
        
        return course
    
    async def update_course(
        self, 
        course_id: int, 
        update_data: Dict[str, Any], 
        changed_by: int, 
        change_reason: str = ""
    ) -> CourseVersion:
        """Создание новой версии курса при обновлении"""
        # Получаем текущую версию
        current_version_query = select(CourseVersion).where(
            CourseVersion.course_id == course_id,
            CourseVersion.is_current == True
        )
        result = await self.db.execute(current_version_query)
        current_version = result.scalar_one_or_none()
        
        if not current_version:
            raise ValueError(f"Course {course_id} not found")
        
        # Получаем следующий номер версии
        max_version_query = select(func.max(CourseVersion.version_number)).where(
            CourseVersion.course_id == course_id
        )
        result = await self.db.execute(max_version_query)
        max_version = result.scalar() or 0
        next_version = max_version + 1
        
        # Создаем новую версию на основе текущей + обновления
        new_version_data = {
            "title": update_data.get("title", current_version.title),
            "description": update_data.get("description", current_version.description),
            "credits": update_data.get("credits", current_version.credits),
            "hours_total": update_data.get("hours_total", current_version.hours_total),
            "hours_lecture": update_data.get("hours_lecture", current_version.hours_lecture),
            "hours_practice": update_data.get("hours_practice", current_version.hours_practice),
            "hours_lab": update_data.get("hours_lab", current_version.hours_lab),
            "status": update_data.get("status", current_version.status)
        }
        
        # Сохраняем старую версию как неактуальную
        current_version.is_current = False  # type: ignore
        
        # Создаем новую версию
        new_version = CourseVersion(
            course_id=course_id,
            version_number=next_version,
            title=new_version_data["title"],
            description=new_version_data["description"],
            credits=new_version_data["credits"],
            hours_total=new_version_data["hours_total"],
            hours_lecture=new_version_data["hours_lecture"],
            hours_practice=new_version_data["hours_practice"],
            hours_lab=new_version_data["hours_lab"],
            status=new_version_data["status"],
            created_by=changed_by,
            is_current=True
        )
        self.db.add(new_version)
        await self.db.flush()
        
        # Обновляем ссылку на текущую версию в курсе
        course_query = select(Course).where(Course.id == course_id)
        result = await self.db.execute(course_query)
        course = result.scalar_one()
        course.current_version_id = new_version.id
        
        # Сохраняем в универсальную таблицу версий
        version_snapshot = {
            "course_id": course_id,
            "version_number": next_version,
            "data": new_version_data,
            "previous_version": current_version.version_number
        }
        
        # Помечаем предыдущую универсальную версию как неактуальную
        await self.db.execute(
            update(Version)
            .where(
                Version.entity_type == "course",
                Version.entity_id == course_id,
                Version.is_current == True
            )
            .values(is_current=False)
        )
        
        version_record = Version(
            entity_type="course",
            entity_id=course_id,
            version_number=next_version,
            snapshot=version_snapshot,
            changed_by=changed_by,
            change_reason=change_reason if change_reason else None,
            is_current=True
        )
        self.db.add(version_record)
        
        await self.db.flush()
        await self.db.refresh(new_version)
        
        return new_version
    
    async def get_course_versions(self, course_id: int) -> List[CourseVersion]:
        query = select(CourseVersion).where(
            CourseVersion.course_id == course_id
        ).order_by(CourseVersion.version_number.desc())
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_version_snapshot(self, entity_type: str, entity_id: int, version_number: int) -> Optional[Dict[str, Any]]:
        query = select(Version).where(
            Version.entity_type == entity_type,
            Version.entity_id == entity_id,
            Version.version_number == version_number
        )
        result = await self.db.execute(query)
        version = result.scalar_one_or_none()
        
        if version and version.snapshot:
            # Проверяем тип snapshot
            snapshot_data = version.snapshot
            if isinstance(snapshot_data, dict):
                return snapshot_data
            elif isinstance(snapshot_data, str):
                try:
                    return json.loads(snapshot_data)
                except json.JSONDecodeError:
                    return {"raw": snapshot_data}
        return None
    
    async def get_courses_list(self, limit: int = 100, offset: int = 0) -> List[Course]:
        """Получение списка курсов"""
        query = select(Course).where(
            Course.is_deleted == False
        ).options(
            selectinload(Course.current_version),
            selectinload(Course.versions)
        ).limit(limit).offset(offset).order_by(Course.id.desc())
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_course_by_id(self, course_id: int) -> Optional[Course]:
        """Получение курса по ID"""
        query = select(Course).where(
            Course.id == course_id,
            Course.is_deleted == False
        ).options(
            selectinload(Course.current_version),
            selectinload(Course.versions)
        )
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    # ============= РАСПИСАНИЕ =============
    async def create_schedule_entry(self, entry_data: Dict[str, Any]) -> ScheduleEntry:
        entry = ScheduleEntry(**entry_data)
        self.db.add(entry)
        await self.db.flush()
        await self.db.refresh(entry)
        return entry
    
    async def get_schedule_by_group(self, group_name: str, semester: Optional[int] = None) -> List[ScheduleEntry]:
        query = select(ScheduleEntry).where(
            ScheduleEntry.student_group == group_name,
            ScheduleEntry.is_cancelled == False
        )
        
        if semester is not None:
            query = query.where(ScheduleEntry.semester == semester)
        
        query = query.order_by(ScheduleEntry.day_of_week, ScheduleEntry.start_time)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_schedule_by_teacher(self, teacher_id: int) -> List[ScheduleEntry]:
        """Получение расписания преподавателя"""
        query = select(ScheduleEntry).where(
            ScheduleEntry.teacher_id == teacher_id,
            ScheduleEntry.is_cancelled == False
        ).order_by(ScheduleEntry.day_of_week, ScheduleEntry.start_time)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    # ============= ЛОГИЧЕСКОЕ УДАЛЕНИЕ =============
    async def soft_delete_course(self, course_id: int) -> bool:
        result = await self.db.execute(
            update(Course)
            .where(Course.id == course_id)
            .values(is_deleted=True)
        )
        await self.db.flush()
        
        # Получаем количество затронутых строк
        result_count = result.rowcount if hasattr(result, 'rowcount') else 0
        return result_count > 0
    
    async def soft_delete_department(self, department_id: int) -> bool:
        """Логическое удаление департамента"""
        result = await self.db.execute(
            update(Department)
            .where(Department.id == department_id)
            .values(is_deleted=True)
        )
        await self.db.flush()
        
        result_count = result.rowcount if hasattr(result, 'rowcount') else 0
        return result_count > 0