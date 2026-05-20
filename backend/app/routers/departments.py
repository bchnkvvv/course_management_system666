from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update, select

from app.database import get_db
from app.models_orm import Department
from app.schemas import DepartmentResponse

router = APIRouter(prefix="/departments", tags=["Departments"])

@router.get("/", response_model=list[DepartmentResponse])
async def get_all_departments(
    db: AsyncSession = Depends(get_db)
):
    try:
        query = select(Department).where(Department.is_deleted == False)
        result = await db.execute(query)
        return list(result.scalars().all())
    except Exception as e:
        return []

@router.delete("/{department_id}")
async def soft_delete_department(
    department_id: int,
    db: AsyncSession = Depends(get_db)
):
    try:
        result = await db.execute(
            update(Department)
            .where(Department.id == department_id, Department.is_deleted == False)
            .values(is_deleted=True)
        )
        await db.flush()
        
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Department not found")
        
        return {"message": "Department deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{department_id}/restore")
async def restore_department(
    department_id: int,
    db: AsyncSession = Depends(get_db)
):
    try:
        result = await db.execute(
            update(Department)
            .where(Department.id == department_id, Department.is_deleted == True)
            .values(is_deleted=False)
        )
        await db.flush()
        
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Department not found")
        
        return {"message": "Department restored successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))