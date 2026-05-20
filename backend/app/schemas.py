from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, time
from typing import Optional, List, Any
from enum import Enum

# Enums
class PersonType(str, Enum):
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"

class LessonType(str, Enum):
    LECTURE = "lecture"
    PRACTICE = "practice"
    LAB = "lab"
    EXAM = "exam"

# Department schemas
class DepartmentBase(BaseModel):
    name: str
    code: str
    parent_id: Optional[int] = None

class DepartmentCreate(DepartmentBase):
    pass

class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[int] = None

class DepartmentResponse(DepartmentBase):
    id: int
    path: Optional[str] = None
    level: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_deleted: bool
    children: List['DepartmentResponse'] = []
    
    model_config = ConfigDict(from_attributes=True)

# Person schemas
class PersonBase(BaseModel):
    full_name: str
    email: str
    phone: Optional[str] = None
    person_type: PersonType

class StudentCreate(PersonBase):
    student_card_number: str
    group_name: str
    enrollment_year: int
    average_grade: Optional[float] = None

class TeacherCreate(PersonBase):
    employee_number: str
    academic_degree: Optional[str] = None
    position: Optional[str] = None
    department_id: Optional[int] = None

class PersonResponse(PersonBase):
    id: int
    created_at: datetime
    is_active: bool
    
    model_config = ConfigDict(from_attributes=True)

class StudentResponse(PersonResponse):
    student_card_number: str
    group_name: str
    enrollment_year: int
    average_grade: Optional[float] = None

class TeacherResponse(PersonResponse):
    employee_number: str
    academic_degree: Optional[str] = None
    position: Optional[str] = None
    department_id: Optional[int] = None

# Course schemas with versioning
class CourseVersionBase(BaseModel):
    title: str
    description: Optional[str] = None
    credits: int
    hours_total: int
    hours_lecture: int = 0
    hours_practice: int = 0
    hours_lab: int = 0
    status: str = "draft"

class CourseVersionCreate(CourseVersionBase):
    pass

class CourseVersionResponse(CourseVersionBase):
    id: int
    version_number: int
    created_at: datetime
    is_current: bool
    created_by: Optional[int] = None

class CourseResponse(BaseModel):
    id: int
    code: str
    current_version: Optional[CourseVersionResponse] = None
    all_versions: List[CourseVersionResponse] = []
    
    model_config = ConfigDict(from_attributes=True)

class CourseUpdate(CourseVersionBase):
    change_reason: Optional[str] = None

# Schedule schemas
class ScheduleEntryBase(BaseModel):
    course_version_id: int
    teacher_id: int
    semester: int
    academic_year: str
    day_of_week: int = Field(ge=1, le=7)
    start_time: time
    end_time: time
    room: str
    lesson_type: LessonType
    student_group: str

class ScheduleEntryCreate(ScheduleEntryBase):
    pass

class ScheduleEntryResponse(ScheduleEntryBase):
    id: int
    is_cancelled: bool
    created_at: datetime
    course_title: Optional[str] = None
    teacher_name: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

# Hierarchy response
class TreeNode(BaseModel):
    id: int
    name: str
    code: str
    level: int
    children: List['TreeNode'] = []

# Version history response
class VersionHistory(BaseModel):
    version_number: int
    snapshot: dict
    changed_at: datetime
    change_reason: Optional[str] = None
    is_current: bool

# Обновляем ссылки на рекурсивные модели
DepartmentResponse.model_rebuild()
TreeNode.model_rebuild()