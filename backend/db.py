import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session


def _build_engine(database_url: str) -> Engine:
    """Build a SQLAlchemy engine for the provided database URL.

    Args:
        database_url: Database connection URL.

    Returns:
        A configured SQLAlchemy engine.
    """
    engine_kwargs = {"pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(database_url, **engine_kwargs)


KEY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./keys.db")
COURSE_DATABASE_URL = os.getenv("COURSE_DATABASE_URL", "sqlite:///./course.db")

keyEngine = _build_engine(KEY_DATABASE_URL)
courseEngine = _build_engine(COURSE_DATABASE_URL)

keySessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=keyEngine)
courseSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=courseEngine)

KeyBase = declarative_base()
courseBase = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Yield a session bound to the key database.

    Yields:
        A SQLAlchemy session for key records.
    """
    db = keySessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_course_db() -> Generator[Session, None, None]:
    """Yield a session bound to the course database.

    Yields:
        A SQLAlchemy session for course records.
    """
    db = courseSessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all database tables for the application.

    Imports the model modules so SQLAlchemy can register their tables before
    calling ``create_all`` on the shared metadata objects.
    """
    import course_models  # noqa: F401
    import key_models  # noqa: F401

    KeyBase.metadata.create_all(bind=keyEngine)
    courseBase.metadata.create_all(bind=courseEngine)


def create_api_key_record(
    db: Session,
    student_id: str,
    key_alias: str,
    encrypted_raw_key: str,
):
    """Create a persisted API key record.

    Args:
        db: Active key database session.
        student_id: Student identifier that owns the key.
        key_alias: External key alias returned by LiteLLM.
        encrypted_raw_key: Encrypted raw key payload.

    Returns:
        The created API key record.
    """
    from key_models import ApiKeyRecord

    new_key_record = ApiKeyRecord(
        student_id=student_id,
        key_alias=key_alias,
        encrypted_raw_key=encrypted_raw_key,
    )
    db.add(new_key_record)
    db.commit()
    db.refresh(new_key_record)
    return new_key_record


def list_api_key_records(db: Session, student_id: str):
    """List API key records for a student.

    Args:
        db: Active key database session.
        student_id: Student identifier to filter by.

    Returns:
        A list of API key records for the student.
    """
    from key_models import ApiKeyRecord

    return db.query(ApiKeyRecord).filter(ApiKeyRecord.student_id == student_id).all()


def get_api_key_record(db: Session, key_id: int, student_id: str):
    """Get a single API key record owned by a student.

    Args:
        db: Active key database session.
        key_id: Primary key of the API key record.
        student_id: Student identifier that must own the record.

    Returns:
        The matching API key record or ``None``.
    """
    from key_models import ApiKeyRecord

    return db.query(ApiKeyRecord).filter(
        ApiKeyRecord.id == key_id,
        ApiKeyRecord.student_id == student_id,
    ).first()


def delete_api_key_record(db: Session, record):
    """Delete an API key record and commit the change.

    Args:
        db: Active key database session.
        record: The API key record to remove.
    """
    db.delete(record)
    db.commit()


def create_course_record(db: Session, course_id: str, course_name: str, created_at):
    """Create a course record.

    Args:
        db: Active course database session.
        course_id: Course identifier.
        course_name: Course display name.
        created_at: Timestamp for the new course.

    Returns:
        The created course record.
    """
    from course_models import Course

    new_course = Course(
        courseID=course_id,
        courseName=course_name,
        created_at=created_at,
    )
    db.add(new_course)
    return new_course


def get_course_record(db: Session, course_id: str):
    """Fetch a course record by course ID.

    Args:
        db: Active course database session.
        course_id: Course identifier.

    Returns:
        The matching course record or ``None``.
    """
    from course_models import Course

    return db.query(Course).filter_by(courseID=course_id).first()


def list_courses_for_student(db: Session, student_id: str):
    """List courses associated with a student.

    Args:
        db: Active course database session.
        student_id: Student identifier.

    Returns:
        A list of course records.
    """
    from course_models import Course, CourseStudent

    return db.query(Course).join(CourseStudent).filter(CourseStudent.studentID == student_id).all()


def get_student_record(db: Session, student_id: str):
    """Fetch a student record by student ID.

    Args:
        db: Active course database session.
        student_id: Student identifier.

    Returns:
        The matching student record or ``None``.
    """
    from course_models import Student

    return db.query(Student).filter_by(studentID=student_id).first()


def create_student_record(db: Session, student_id: str, student_name: str):
    """Create a student record.

    Args:
        db: Active course database session.
        student_id: Student identifier.
        student_name: Student display name.

    Returns:
        The created student record.
    """
    from course_models import Student

    student = Student(studentID=student_id, studentName=student_name)
    db.add(student)
    return student


def get_course_student_relation(db: Session, course_id: str, student_id: str):
    """Fetch a course-student relation if it already exists.

    Args:
        db: Active course database session.
        course_id: Course identifier.
        student_id: Student identifier.

    Returns:
        The matching relation or ``None``.
    """
    from course_models import CourseStudent

    return db.query(CourseStudent).filter_by(courseID=course_id, studentID=student_id).first()


def create_course_student_relation(db: Session, course_id: str, student_id: str):
    """Create a course-student association.

    Args:
        db: Active course database session.
        course_id: Course identifier.
        student_id: Student identifier.

    Returns:
        The created relation record.
    """
    from course_models import CourseStudent

    relation = CourseStudent(courseID=course_id, studentID=student_id)
    db.add(relation)
    return relation


def commit_session(db: Session):
    """Commit the current transaction for a session.

    Args:
        db: Active SQLAlchemy session.
    """
    db.commit()


def rollback_session(db: Session):
    """Rollback the current transaction for a session.

    Args:
        db: Active SQLAlchemy session.
    """
    db.rollback()