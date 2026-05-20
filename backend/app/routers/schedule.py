from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select  # ← ДОБАВИТЬ

from app.database import get_db, get_async_pool
from app.schemas import ScheduleEntryResponse, ScheduleEntryCreate
from app.dependencies import get_use_native_sql

router = APIRouter(prefix="/schedule", tags=["Schedule"])

@router.get("/group/{group_name}", response_model=List[ScheduleEntryResponse])
async def get_schedule_by_group(
    group_name: str,
    semester: Optional[int] = Query(None, description="Номер семестра"),
    db: AsyncSession = Depends(get_db),
    use_native: bool = Depends(get_use_native_sql)
):
    """Получение расписания для группы"""
    try:
        if use_native:
            pool = await get_async_pool()
            async with pool.acquire() as conn:
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
                params: List[str] = [group_name]  # ← ИСПРАВЛЕНО: указываем тип List[str]
                
                if semester is not None:  # ← ИСПРАВЛЕНО: проверка на None
                    query += " AND se.semester = $2"
                    params.append(str(semester))  # ← ИСПРАВЛЕНО: преобразуем int в str
                
                query += " ORDER BY se.day_of_week, se.start_time"
                
                rows = await conn.fetch(query, *params)
                return [dict(row) for row in rows]
        else:
            # ORM код
            from app.models_orm import ScheduleEntry
            
            query = select(ScheduleEntry).where(
                ScheduleEntry.student_group == group_name,
                ScheduleEntry.is_cancelled == False
            )
            
            if semester is not None:  # ← ИСПРАВЛЕНО
                query = query.where(ScheduleEntry.semester == semester)
            
            query = query.order_by(ScheduleEntry.day_of_week, ScheduleEntry.start_time)
            
            result = await db.execute(query)
            entries = result.scalars().all()
            return entries
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ... остальные эндпоинты