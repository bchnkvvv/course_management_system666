from fastapi import APIRouter, Depends
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models_orm import Department
from app.schemas import DepartmentResponse

router = APIRouter(prefix="/hierarchy", tags=["Hierarchy"])

@router.get("/departments/tree", response_model=List[DepartmentResponse])
async def get_department_tree(
    db: AsyncSession = Depends(get_db)
):
    """Получение иерархического дерева департаментов"""
    try:
        query = select(Department).where(
            Department.parent_id.is_(None),
            Department.is_deleted == False
        )
        result = await db.execute(query)
        roots = list(result.scalars().all())
        
        async def load_children(dept: Department):
            child_query = select(Department).where(
                Department.parent_id == dept.id,
                Department.is_deleted == False
            )
            child_result = await db.execute(child_query)
            children = list(child_result.scalars().all())
            dept.children = children
            for child in children:
                await load_children(child)
            return dept
        
        for root in roots:
            await load_children(root)
        
        return roots
    except Exception as e:
        print(f"Error loading departments: {e}")
        return []