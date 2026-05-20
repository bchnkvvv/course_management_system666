from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, get_async_pool
from app.orm_crud import ORMCrud
from app.native_crud import NativeSQLCrud
from app.schemas import (
    CourseResponse, CourseVersionCreate, CourseUpdate,
    CourseVersionResponse, VersionHistory
)
from app.dependencies import get_use_native_sql

router = APIRouter(prefix="/courses", tags=["Courses"])

@router.post("/", response_model=CourseResponse)
async def create_course(
    code: str,
    version_data: CourseVersionCreate,
    created_by: int = 1,
    db: AsyncSession = Depends(get_db),
    use_native: bool = Depends(get_use_native_sql)
):
    """Создание нового курса с первой версией"""
    if use_native:
        pool = await get_async_pool()
        crud = NativeSQLCrud(pool)
        result = await crud.create_course(code, version_data.model_dump(), created_by)
        return result
    else:
        crud = ORMCrud(db)
        course = await crud.create_course(code, version_data, created_by)
        await db.refresh(course, ['versions', 'current_version'])
        return course

@router.put("/{course_id}", response_model=CourseVersionResponse)
async def update_course(
    course_id: int,
    update_data: CourseUpdate,
    changed_by: int = 1,
    db: AsyncSession = Depends(get_db),
    use_native: bool = Depends(get_use_native_sql)
):
    """Обновление курса с созданием новой версии"""
    if use_native:
        pool = await get_async_pool()
        crud = NativeSQLCrud(pool)
        result = await crud.update_course(
            course_id, 
            update_data.model_dump(exclude_unset=True), 
            changed_by,
            update_data.change_reason or ""
        )
        return result
    else:
        crud = ORMCrud(db)
        version = await crud.update_course(
            course_id,
            update_data.model_dump(exclude_unset=True),
            changed_by,
            update_data.change_reason or ""
        )
        return version

@router.get("/{course_id}/versions", response_model=List[CourseVersionResponse])
async def get_course_versions(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    use_native: bool = Depends(get_use_native_sql)
):
    """Получение всех версий курса"""
    if use_native:
        pool = await get_async_pool()
        crud = NativeSQLCrud(pool)
        versions = await crud.get_course_versions(course_id)
        return versions
    else:
        crud = ORMCrud(db)
        versions = await crud.get_course_versions(course_id)
        return versions

@router.get("/{course_id}/versions/{version_number}", response_model=VersionHistory)
async def get_version_snapshot(
    course_id: int,
    version_number: int,
    db: AsyncSession = Depends(get_db),
    use_native: bool = Depends(get_use_native_sql)
):
    """Получение данных конкретной версии курса"""
    if use_native:
        pool = await get_async_pool()
        crud = NativeSQLCrud(pool)
        snapshot = await crud.get_version_snapshot("course", course_id, version_number)
    else:
        crud = ORMCrud(db)
        snapshot = await crud.get_version_snapshot("course", course_id, version_number)
    
    if not snapshot:
        raise HTTPException(status_code=404, detail="Version not found")
    
    return VersionHistory(
        version_number=version_number,
        snapshot=snapshot,
        changed_at=snapshot.get("changed_at", ""),
        change_reason=snapshot.get("change_reason"),
        is_current=(version_number == snapshot.get("version_number"))
    )

@router.delete("/{course_id}")
async def soft_delete_course(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    use_native: bool = Depends(get_use_native_sql)
):
    """Логическое удаление курса"""
    if use_native:
        pool = await get_async_pool()
        crud = NativeSQLCrud(pool)
        success = await crud.soft_delete_course(course_id)
    else:
        crud = ORMCrud(db)
        success = await crud.soft_delete_course(course_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Course not found")
    
    return {"message": "Course deleted successfully"}

@router.get("/list", response_model=List[CourseResponse])
async def get_courses_list(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    use_native: bool = Depends(get_use_native_sql)
):
    """Получение списка всех курсов"""
    try:
        if use_native:
            pool = await get_async_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT 
                        c.id, c.code, c.created_at,
                        cv.id as version_id, cv.version_number, cv.title, 
                        cv.description, cv.credits, cv.hours_total, cv.status,
                        cv.created_at as version_created_at
                    FROM courses c
                    LEFT JOIN course_versions cv ON c.current_version_id = cv.id
                    WHERE c.is_deleted = FALSE
                    ORDER BY c.id DESC
                    LIMIT $1 OFFSET $2
                """, limit, offset)
                
                courses = []
                for row in rows:
                    course: dict = {
                        "id": row["id"],
                        "code": row["code"],
                        "created_at": row["created_at"],
                        "is_deleted": False,
                        "current_version": None,
                        "all_versions": []
                    }
                    
                    if row["version_id"]:
                        course["current_version"] = {
                            "id": row["version_id"],
                            "version_number": row["version_number"],
                            "title": row["title"],
                            "description": row["description"],
                            "credits": row["credits"],
                            "hours_total": row["hours_total"],
                            "hours_lecture": 0,
                            "hours_practice": 0,
                            "hours_lab": 0,
                            "status": row["status"],
                            "created_at": row["version_created_at"],
                            "is_current": True,
                            "created_by": None
                        }
                    
                    courses.append(course)
                
                return courses
        else:
            crud = ORMCrud(db)
            courses = await crud.get_courses_list(limit, offset)
            return courses
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{course_id}", response_model=CourseResponse)
async def get_course(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    use_native: bool = Depends(get_use_native_sql)
):
    """Получение курса по ID"""
    try:
        if use_native:
            pool = await get_async_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT 
                        c.id, c.code, c.created_at,
                        cv.id as version_id, cv.version_number, cv.title, 
                        cv.description, cv.credits, cv.hours_total, cv.status
                    FROM courses c
                    LEFT JOIN course_versions cv ON c.current_version_id = cv.id
                    WHERE c.id = $1 AND c.is_deleted = FALSE
                """, course_id)
                
                if not row:
                    raise HTTPException(status_code=404, detail="Course not found")
                
                course = {
                    "id": row["id"],
                    "code": row["code"],
                    "created_at": row["created_at"],
                    "is_deleted": False,
                    "current_version": None,
                    "all_versions": []
                }
                
                if row["version_id"]:
                    course["current_version"] = {
                        "id": row["version_id"],
                        "version_number": row["version_number"],
                        "title": row["title"],
                        "description": row["description"],
                        "credits": row["credits"],
                        "hours_total": row["hours_total"],
                        "hours_lecture": 0,
                        "hours_practice": 0,
                        "hours_lab": 0,
                        "status": row["status"],
                        "created_at": row["created_at"],
                        "is_current": True,
                        "created_by": None
                    }
                
                return course
        else:
            crud = ORMCrud(db)
            course = await crud.get_course_by_id(course_id)
            if not course:
                raise HTTPException(status_code=404, detail="Course not found")
            return course
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))