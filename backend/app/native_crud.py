from typing import Optional, List, Dict, Any
import asyncpg
import json

class NativeSQLCrud:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
    
    async def get_courses_list(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
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
                        "created_at": row["version_created_at"],
                        "is_current": True,
                        "created_by": None
                    }
                
                courses.append(course)
            
            return courses
    
    async def get_course_versions(self, course_id: int) -> List[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM course_versions
                WHERE course_id = $1
                ORDER BY version_number DESC
            """, course_id)
            return [dict(row) for row in rows]
    
    async def get_version_snapshot(self, entity_type: str, entity_id: int, version_number: int) -> Optional[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT snapshot, change_reason, changed_at
                FROM versions
                WHERE entity_type = $1 AND entity_id = $2 AND version_number = $3
            """, entity_type, entity_id, version_number)
            if row:
                return {
                    "snapshot": row["snapshot"],
                    "change_reason": row["change_reason"],
                    "changed_at": row["changed_at"]
                }
            return None
    
    async def create_course(self, code: str, version_data: Dict[str, Any], created_by: int) -> Optional[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                course = await conn.fetchrow("""
                    INSERT INTO courses (code) VALUES ($1) RETURNING id, code, created_at
                """, code)
                
                if not course:
                    return None
                
                version_id = await conn.fetchval("""
                    SELECT create_new_course_version($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """, course["id"], version_data["title"], version_data.get("description", ""),
                    version_data["credits"], version_data["hours_total"],
                    version_data.get("hours_lecture", 0), version_data.get("hours_practice", 0),
                    version_data.get("hours_lab", 0), created_by)
                
                return {"course": dict(course), "version_id": version_id}
    
    async def update_course(self, course_id: int, update_data: Dict[str, Any], changed_by: int, change_reason: str = "") -> Optional[Dict[str, Any]]:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                current = await conn.fetchrow("""
                    SELECT * FROM course_versions WHERE course_id = $1 AND is_current = TRUE
                """, course_id)
                
                if not current:
                    return None
                
                next_version = await conn.fetchval("""
                    SELECT COALESCE(MAX(version_number), 0) + 1 FROM course_versions WHERE course_id = $1
                """, course_id)
                
                new_version = await conn.fetchrow("""
                    INSERT INTO course_versions (
                        course_id, version_number, title, description, credits,
                        hours_total, hours_lecture, hours_practice, hours_lab,
                        status, created_by, is_current
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, TRUE)
                    RETURNING *
                """, course_id, next_version,
                    update_data.get("title", current["title"]),
                    update_data.get("description", current["description"]),
                    update_data.get("credits", current["credits"]),
                    update_data.get("hours_total", current["hours_total"]),
                    update_data.get("hours_lecture", current["hours_lecture"]),
                    update_data.get("hours_practice", current["hours_practice"]),
                    update_data.get("hours_lab", current["hours_lab"]),
                    update_data.get("status", current["status"]),
                    changed_by)
                
                await conn.execute("UPDATE course_versions SET is_current = FALSE WHERE id = $1", current["id"])
                await conn.execute("UPDATE courses SET current_version_id = $1 WHERE id = $2", new_version["id"], course_id)
                
                return dict(new_version)
    
    async def soft_delete_course(self, course_id: int) -> bool:
        async with self.pool.acquire() as conn:
            result = await conn.execute("UPDATE courses SET is_deleted = TRUE WHERE id = $1", course_id)
            return result == "UPDATE 1"