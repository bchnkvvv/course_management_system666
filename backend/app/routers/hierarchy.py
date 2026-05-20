from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select  # ← ДОБАВИТЬ ЭТУ СТРОКУ!
from sqlalchemy.orm import selectinload

from app.database import get_db, get_async_pool
from app.schemas import DepartmentResponse, TreeNode
from app.dependencies import get_use_native_sql

router = APIRouter(prefix="/hierarchy", tags=["Hierarchy"])

# ... остальной код без изменений