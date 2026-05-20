from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models_orm import Course, CourseVersion
from app.schemas import CourseResponse, CourseVersionCreate, CourseUpdate, CourseVersionResponse

router = APIRouter(prefix="/courses", tags=["Courses"])

@router.post("/", response_model=CourseResponse)
async def create_course(
    code: str,
    version_data: CourseVersionCreate,
    created_by: int = 1,
    db: AsyncSession = Depends(get_db)
):
    """Создание нового курса с первой версией"""
    try:
        course = Course(code=code, is_deleted=False)
        db.add(course)
        await db.flush()
        
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
        db.add(version)
        await db.flush()
        
        course.current_version_id = version.id
        await db.flush()
        await db.refresh(course)
        
        return course
    except Exception as e:
        print(f"Error creating course: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{course_id}", response_model=CourseVersionResponse)
async def update_course(
    course_id: int,
    update_data: CourseUpdate,
    changed_by: int = 1,
    db: AsyncSession = Depends(get_db)
):
    """Обновление курса с созданием новой версии"""
    try:
        from sqlalchemy import func
        
        current_query = select(CourseVersion).where(
            CourseVersion.course_id == course_id,
            CourseVersion.is_current == True
        )
        result = await db.execute(current_query)
        current_version = result.scalar_one_or_none()
        
        if not current_version:
            raise HTTPException(status_code=404, detail="Course not found")
        
        max_version_query = select(func.max(CourseVersion.version_number)).where(
            CourseVersion.course_id == course_id
        )
        result = await db.execute(max_version_query)
        max_version = result.scalar() or 0
        next_version = max_version + 1
        
        new_version = CourseVersion(
            course_id=course_id,
            version_number=next_version,
            title=update_data.title if update_data.title else current_version.title,
            description=update_data.description if update_data.description else current_version.description,
            credits=update_data.credits if update_data.credits else current_version.credits,
            hours_total=update_data.hours_total if update_data.hours_total else current_version.hours_total,
            hours_lecture=update_data.hours_lecture if update_data.hours_lecture else current_version.hours_lecture,
            hours_practice=update_data.hours_practice if update_data.hours_practice else current_version.hours_practice,
            hours_lab=update_data.hours_lab if update_data.hours_lab else current_version.hours_lab,
            status=update_data.status if update_data.status else current_version.status,
            created_by=changed_by,
            is_current=True
        )
        db.add(new_version)
        await db.flush()
        
        current_version.is_current = False
        
        course_query = select(Course).where(Course.id == course_id)
        result = await db.execute(course_query)
        course = result.scalar_one()
        course.current_version_id = new_version.id
        
        await db.flush()
        await db.refresh(new_version)
        
        return new_version
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating course: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{course_id}/versions", response_model=List[CourseVersionResponse])
async def get_course_versions(
    course_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Получение всех версий курса"""
    try:
        query = select(CourseVersion).where(
            CourseVersion.course_id == course_id
        ).order_by(CourseVersion.version_number.desc())
        
        result = await db.execute(query)
        return list(result.scalars().all())
    except Exception as e:
        print(f"Error: {e}")
        return []

@router.get("/list", response_model=List[CourseResponse])
async def get_courses_list(
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """Получение списка курсов"""
    try:
        query = select(Course).where(
            Course.is_deleted == False
        ).options(
            selectinload(Course.current_version),
            selectinload(Course.versions)
        ).limit(limit).offset(offset).order_by(Course.id.desc())
        
        result = await db.execute(query)
        return list(result.scalars().all())
    except Exception as e:
        print(f"Error loading courses: {e}")
        return []

@router.delete("/{course_id}")
async def soft_delete_course(
    course_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Логическое удаление курса"""
    try:
        from sqlalchemy import update
        
        result = await db.execute(
            update(Course)
            .where(Course.id == course_id)
            .values(is_deleted=True)
        )
        await db.flush()
        return {"message": "Course deleted successfully"}
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))