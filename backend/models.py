from sqlalchemy import Column, String, TIMESTAMP, ForeignKey, Integer
from sqlalchemy.orm import relationship
from datetime import datetime

from db import courseBase as Base


class Course(Base):
    __tablename__ = "course"

    courseID = Column(String, primary_key=True, index=True)
    courseName = Column(String, nullable=False)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    # 關聯
    students = relationship("CourseStudent", back_populates="course")


class Student(Base):
    __tablename__ = "student"

    studentID = Column(String, primary_key=True, index=True)
    studentName = Column(String, nullable=False)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    courses = relationship("CourseStudent", back_populates="student")


class CourseStudent(Base):
    __tablename__ = "course_student"

    courseID = Column(String, ForeignKey("course.courseID"), primary_key=True)
    studentID = Column(String, ForeignKey("student.studentID"), primary_key=True)

    # 關聯
    course = relationship("Course", back_populates="students")
    student = relationship("Student", back_populates="courses")

class ApiKeyRecord(Base):
    __tablename__ = "api_keys"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String, index=True)
    key_alias = Column(String, index=True)
    encrypted_raw_key = Column(String)