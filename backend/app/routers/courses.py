from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.database import get_db, get_async_pool
from app.models_orm import Course, CourseVersion, Version
from app.schemas import CourseResponse, CourseVersionCreate, CourseUpdate, CourseVersionResponse
from app.dependencies import get_data_source

router = APIRouter(prefix="/courses", tags=["Courses"])

@router.post("/", response_model=CourseResponse)
async def create_course(
    code: str,
    version_data: CourseVersionCreate,
    created_by: int = 1,
    db: AsyncSession = Depends(get_db),
    data_source: str = Depends(get_data_source)
):
    """Создание курса - поддерживает ORM и Native SQL"""
    
    if data_source == "native":
        # Native SQL реализация
        from app.native_crud import NativeSQLCrud
        pool = await get_async_pool()
        crud = NativeSQLCrud(pool)
        result = await crud.create_course(code, version_data.model_dump(), created_by)
        if result:
            return result.get("course")
        raise HTTPException(status_code=500, detail="Failed to create course")
    
    else:
        # ORM реализация
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

@router.put("/{course_id}", response_model=CourseVersionResponse)
async def update_course(
    course_id: int,
    update_data: CourseUpdate,
    changed_by: int = 1,
    db: AsyncSession = Depends(get_db),
    data_source: str = Depends(get_data_source)
):
    """Обновление курса с созданием новой версии"""
    
    if data_source == "native":
        from app.native_crud import NativeSQLCrud
        pool = await get_async_pool()
        crud = NativeSQLCrud(pool)
        result = await crud.update_course(
            course_id,
            update_data.model_dump(exclude_unset=True),
            changed_by,
            update_data.change_reason or ""
        )
        if not result:
            raise HTTPException(status_code=404, detail="Course not found")
        return result
    
    else:
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
        
        snapshot_record = Version(
            entity_type="course",
            entity_id=course_id,
            version_number=next_version,
            snapshot={
                "title": new_version.title,
                "description": new_version.description,
                "credits": new_version.credits,
                "hours_total": new_version.hours_total
            },
            changed_by=changed_by,
            change_reason=update_data.change_reason,
            is_current=True
        )
        db.add(snapshot_record)
        
        await db.execute(
            update(Version)
            .where(
                Version.entity_type == "course",
                Version.entity_id == course_id,
                Version.is_current == True,
                Version.version_number != next_version
            )
            .values(is_current=False)
        )
        
        await db.flush()
        await db.refresh(new_version)
        
        return new_version

@router.get("/list", response_model=List[CourseResponse])
async def get_courses_list(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    min_credits: Optional[int] = Query(None),
    max_credits: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    data_source: str = Depends(get_data_source)
):
    """Получение списка курсов с фильтрацией"""
    
    if data_source == "native":
        from app.native_crud import NativeSQLCrud
        pool = await get_async_pool()
        crud = NativeSQLCrud(pool)
        return await crud.get_courses_list(limit, offset)
    
    else:
        query = select(Course).where(Course.is_deleted == False)
        
        if status or search or min_credits or max_credits:
            query = query.join(Course.current_version)
            
            if status:
                query = query.where(CourseVersion.status == status)
            if search:
                query = query.where(
                    (Course.code.ilike(f"%{search}%")) |
                    (CourseVersion.title.ilike(f"%{search}%"))
                )
            if min_credits:
                query = query.where(CourseVersion.credits >= min_credits)
            if max_credits:
                query = query.where(CourseVersion.credits <= max_credits)
        
        query = query.options(
            selectinload(Course.current_version),
            selectinload(Course.versions)
        ).limit(limit).offset(offset).order_by(Course.id.desc())
        
        result = await db.execute(query)
        return list(result.scalars().all())

@router.get("/{course_id}/versions", response_model=List[CourseVersionResponse])
async def get_course_versions(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    data_source: str = Depends(get_data_source)
):
    if data_source == "native":
        from app.native_crud import NativeSQLCrud
        pool = await get_async_pool()
        crud = NativeSQLCrud(pool)
        return await crud.get_course_versions(course_id)
    else:
        query = select(CourseVersion).where(
            CourseVersion.course_id == course_id
        ).order_by(CourseVersion.version_number.desc())
        result = await db.execute(query)
        return list(result.scalars().all())

@router.get("/{course_id}/versions/{version_number}")
async def get_version_snapshot(
    course_id: int,
    version_number: int,
    db: AsyncSession = Depends(get_db),
    data_source: str = Depends(get_data_source)
):
    if data_source == "native":
        from app.native_crud import NativeSQLCrud
        pool = await get_async_pool()
        crud = NativeSQLCrud(pool)
        snapshot = await crud.get_version_snapshot("course", course_id, version_number)
        if not snapshot:
            raise HTTPException(status_code=404, detail="Version not found")
        return {"snapshot": snapshot, "version_number": version_number}
    else:
        version_query = select(CourseVersion).where(
            CourseVersion.course_id == course_id,
            CourseVersion.version_number == version_number
        )
        result = await db.execute(version_query)
        version = result.scalar_one_or_none()
        
        if not version:
            raise HTTPException(status_code=404, detail="Version not found")
        
        snapshot_query = select(Version).where(
            Version.entity_type == "course",
            Version.entity_id == course_id,
            Version.version_number == version_number
        )
        result = await db.execute(snapshot_query)
        version_record = result.scalar_one_or_none()
        
        return {
            "id": version.id,
            "version_number": version.version_number,
            "title": version.title,
            "description": version.description,
            "credits": version.credits,
            "hours_total": version.hours_total,
            "status": version.status,
            "created_at": version.created_at,
            "is_current": version.is_current,
            "snapshot": version_record.snapshot if version_record else None,
            "change_reason": version_record.change_reason if version_record else None
        }

@router.delete("/{course_id}")
async def soft_delete_course(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    data_source: str = Depends(get_data_source)
):
    if data_source == "native":
        from app.native_crud import NativeSQLCrud
        pool = await get_async_pool()
        crud = NativeSQLCrud(pool)
        success = await crud.soft_delete_course(course_id)
        if not success:
            raise HTTPException(status_code=404, detail="Course not found")
        return {"message": "Course deleted successfully"}
    else:
        result = await db.execute(
            update(Course)
            .where(Course.id == course_id, Course.is_deleted == False)
            .values(is_deleted=True)
        )
        await db.flush()
        
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Course not found")
        
        return {"message": "Course deleted successfully"}

@router.post("/{course_id}/restore")
async def restore_course(
    course_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        update(Course)
        .where(Course.id == course_id, Course.is_deleted == True)
        .values(is_deleted=False)
    )
    await db.flush()
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Course not found or not deleted")
    
    return {"message": "Course restored successfully"}