from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models_orm import Student, Teacher
from app.schemas import StudentResponse, TeacherResponse

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/students", response_model=List[StudentResponse])
async def get_all_students(
    db: AsyncSession = Depends(get_db)
):
    """Получение всех студентов"""
    try:
        query = select(Student)
        result = await db.execute(query)
        students = list(result.scalars().all())
        return students
    except Exception as e:
        print(f"Error loading students: {e}")
        return []

@router.get("/teachers", response_model=List[TeacherResponse])
async def get_all_teachers(
    db: AsyncSession = Depends(get_db)
):
    """Получение всех преподавателей"""
    try:
        query = select(Teacher)
        result = await db.execute(query)
        teachers = list(result.scalars().all())
        return teachers
    except Exception as e:
        print(f"Error loading teachers: {e}")
        return []

@router.get("/students/{student_id}", response_model=StudentResponse)
async def get_student(
    student_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Получение студента по ID"""
    try:
        query = select(Student).where(Student.person_id == student_id)
        result = await db.execute(query)
        student = result.scalar_one_or_none()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        return student
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/teachers/{teacher_id}", response_model=TeacherResponse)
async def get_teacher(
    teacher_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Получение преподавателя по ID"""
    try:
        query = select(Teacher).where(Teacher.person_id == teacher_id)
        result = await db.execute(query)
        teacher = result.scalar_one_or_none()
        if not teacher:
            raise HTTPException(status_code=404, detail="Teacher not found")
        return teacher
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))