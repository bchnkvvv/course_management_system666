from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, get_async_pool
from app.orm_crud import ORMCrud
from app.native_crud import NativeSQLCrud
from app.schemas import StudentResponse, TeacherResponse
from app.dependencies import get_use_native_sql

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/students", response_model=List[StudentResponse])
async def get_all_students(
    db: AsyncSession = Depends(get_db),
    use_native: bool = Depends(get_use_native_sql)
):
    """Получение всех студентов"""
    try:
        if use_native:
            pool = await get_async_pool()
            crud = NativeSQLCrud(pool)
            async with pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT p.*, s.student_card_number, s.group_name, s.enrollment_year, s.average_grade
                    FROM persons p
                    JOIN students s ON p.id = s.person_id
                    WHERE p.person_type = 'student' AND p.is_deleted = FALSE
                """)
                return [dict(row) for row in rows]
        else:
            from sqlalchemy import select
            from app.models_orm import Student
            
            result = await db.execute(
                select(Student).where(Student.is_deleted == False)
            )
            students = result.scalars().all()
            return students
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/teachers", response_model=List[TeacherResponse])
async def get_all_teachers(
    db: AsyncSession = Depends(get_db),
    use_native: bool = Depends(get_use_native_sql)
):
    """Получение всех преподавателей"""
    try:
        if use_native:
            pool = await get_async_pool()
            crud = NativeSQLCrud(pool)
            async with pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT p.*, t.employee_number, t.academic_degree, t.position, t.department_id
                    FROM persons p
                    JOIN teachers t ON p.id = t.person_id
                    WHERE p.person_type = 'teacher' AND p.is_deleted = FALSE
                """)
                return [dict(row) for row in rows]
        else:
            from sqlalchemy import select
            from app.models_orm import Teacher
            
            result = await db.execute(
                select(Teacher).where(Teacher.is_deleted == False)
            )
            teachers = result.scalars().all()
            return teachers
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/students/{student_id}", response_model=StudentResponse)
async def get_student(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    use_native: bool = Depends(get_use_native_sql)
):
    """Получение студента по ID"""
    try:
        if use_native:
            pool = await get_async_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT p.*, s.student_card_number, s.group_name, s.enrollment_year, s.average_grade
                    FROM persons p
                    JOIN students s ON p.id = s.person_id
                    WHERE p.id = $1 AND p.is_deleted = FALSE
                """, student_id)
                if not row:
                    raise HTTPException(status_code=404, detail="Student not found")
                return dict(row)
        else:
            from sqlalchemy import select
            from app.models_orm import Student
            
            result = await db.execute(
                select(Student).where(Student.person_id == student_id, Student.is_deleted == False)
            )
            student = result.scalar_one_or_none()
            if not student:
                raise HTTPException(status_code=404, detail="Student not found")
            return student
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))