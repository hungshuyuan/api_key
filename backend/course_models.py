from datetime import datetime

from sqlalchemy import Column, ForeignKey, String, TIMESTAMP
from sqlalchemy.orm import relationship

from db import courseBase as Base


class Course(Base):
    __tablename__ = "course"

    courseID = Column(String, primary_key=True, index=True)
    courseName = Column(String, nullable=False)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

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

    course = relationship("Course", back_populates="students")
    student = relationship("Student", back_populates="courses")