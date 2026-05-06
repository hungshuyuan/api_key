from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

COURSE_DATABASE_URL = "sqlite:///./course.db"  

# 👉 production 建議換 PostgreSQL

courseEngine = create_engine(
    COURSE_DATABASE_URL,
    connect_args={"check_same_thread": False}  # SQLite only
)

courseSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=courseEngine
)

courseBase = declarative_base()


# FastAPI dependency
def get_course_db():
    db = courseSessionLocal()
    try:
        yield db
    finally:
        db.close()