from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, JSON, Time, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Department(Base):
    __tablename__ = "departments"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    code = Column(String(20), unique=True, nullable=False)
    parent_id = Column(Integer, ForeignKey("departments.id"))
    path = Column(String(500))
    level = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    is_deleted = Column(Boolean, default=False)
    
    parent = relationship("Department", remote_side=[id], backref="children")
    teachers = relationship("Teacher", back_populates="department")

class Person(Base):
    __tablename__ = "persons"
    
    id = Column(Integer, primary_key=True)
    full_name = Column(String(200), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    phone = Column(String(20))
    person_type = Column(String(50), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    is_active = Column(Boolean, default=True)
    is_deleted = Column(Boolean, default=False)
    
    __mapper_args__ = {
        "polymorphic_on": "person_type",
        "polymorphic_identity": "person"
    }

class Student(Person):
    __tablename__ = "students"
    __mapper_args__ = {"polymorphic_identity": "student"}
    
    person_id = Column(Integer, ForeignKey("persons.id"), primary_key=True)
    student_card_number = Column(String(50), unique=True)
    group_name = Column(String(100))
    enrollment_year = Column(Integer)
    average_grade = Column(Float)
    
    assignments = relationship("CourseAssignment", back_populates="student")

class Teacher(Person):
    __tablename__ = "teachers"
    __mapper_args__ = {"polymorphic_identity": "teacher"}
    
    person_id = Column(Integer, ForeignKey("persons.id"), primary_key=True)
    employee_number = Column(String(50), unique=True)
    academic_degree = Column(String(100))
    position = Column(String(100))
    department_id = Column(Integer, ForeignKey("departments.id"))
    
    department = relationship("Department", back_populates="teachers")
    schedule_entries = relationship("ScheduleEntry", back_populates="teacher")

class Course(Base):
    __tablename__ = "courses"
    
    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False)
    current_version_id = Column(Integer, ForeignKey("course_versions.id"))
    created_at = Column(DateTime, server_default=func.now())
    is_deleted = Column(Boolean, default=False)
    
    versions = relationship("CourseVersion", back_populates="course")
    current_version = relationship("CourseVersion", foreign_keys=[current_version_id])

class CourseVersion(Base):
    __tablename__ = "course_versions"
    
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    title = Column(String(300), nullable=False)
    description = Column(Text)
    credits = Column(Integer)
    hours_total = Column(Integer)
    hours_lecture = Column(Integer, default=0)
    hours_practice = Column(Integer, default=0)
    hours_lab = Column(Integer, default=0)
    status = Column(String(50), default="draft")
    created_by = Column(Integer, ForeignKey("persons.id"))
    created_at = Column(DateTime, server_default=func.now())
    is_current = Column(Boolean, default=False)
    
    course = relationship("Course", back_populates="versions", foreign_keys=[course_id])
    schedule_entries = relationship("ScheduleEntry", back_populates="course_version")
    assignments = relationship("CourseAssignment", back_populates="course_version")

class ScheduleEntry(Base):
    __tablename__ = "schedule_entries"
    
    id = Column(Integer, primary_key=True)
    course_version_id = Column(Integer, ForeignKey("course_versions.id"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("teachers.person_id"), nullable=False)
    semester = Column(Integer, nullable=False)
    academic_year = Column(String(9))
    day_of_week = Column(Integer)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    room = Column(String(50))
    lesson_type = Column(String(50))
    student_group = Column(String(100))
    is_cancelled = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    course_version = relationship("CourseVersion", back_populates="schedule_entries")
    teacher = relationship("Teacher", back_populates="schedule_entries")

class CourseAssignment(Base):
    __tablename__ = "course_assignments"
    
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.person_id"), nullable=False)
    course_version_id = Column(Integer, ForeignKey("course_versions.id"), nullable=False)
    enrollment_date = Column(DateTime, server_default=func.now())
    grade = Column(Float)
    status = Column(String(50), default="enrolled")
    
    student = relationship("Student", back_populates="assignments")
    course_version = relationship("CourseVersion", back_populates="assignments")

class Version(Base):
    __tablename__ = "versions"
    
    id = Column(Integer, primary_key=True)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Integer, nullable=False)
    version_number = Column(Integer, nullable=False)
    snapshot = Column(JSON, nullable=False)
    changed_by = Column(Integer, ForeignKey("persons.id"))
    changed_at = Column(DateTime, server_default=func.now())
    change_reason = Column(Text)
    is_current = Column(Boolean, default=False)