# database.py

import enum
from datetime import datetime

from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, Enum as SAEnum
from sqlalchemy.orm import relationship, sessionmaker, declarative_base

# تعریف پایه برای مدل‌ها
Base = declarative_base()


# Enum برای وضعیت مشاهده ویدیو
class WatchedStatusEnum(enum.Enum):
    UNWATCHED = "unwatched"
    PARTIALLY_WATCHED = "partially_watched"
    WATCHED = "watched"


class Course(Base):
    __tablename__ = 'courses'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    base_directory_path = Column(String, unique=True, nullable=False)
    total_duration_seconds = Column(Float, default=0.0)
    date_added = Column(DateTime, default=datetime.utcnow)

    chapters = relationship("Chapter", back_populates="course", cascade="all, delete-orphan", order_by="Chapter.order_in_course")

    def __repr__(self):
        return f"<Course(name='{self.name}')>"


class Chapter(Base):
    __tablename__ = 'chapters'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    path = Column(String, nullable=False)  # مسیر کامل به پوشه فصل
    order_in_course = Column(Integer, nullable=False)
    total_duration_seconds = Column(Float, default=0.0)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)

    course = relationship("Course", back_populates="chapters")
    videos = relationship("Video", back_populates="chapter", cascade="all, delete-orphan", order_by="Video.order_in_chapter")

    def __repr__(self):
        return f"<Chapter(name='{self.name}', course_id={self.course_id})>"


class Video(Base):
    __tablename__ = 'videos'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    file_path = Column(String, unique=True, nullable=False)
    duration_seconds = Column(Float, nullable=False)
    order_in_chapter = Column(Integer, nullable=False)
    watched_status = Column(SAEnum(WatchedStatusEnum), default=WatchedStatusEnum.UNWATCHED, nullable=False)
    watched_seconds = Column(Float, default=0.0, nullable=False)
    subtitle_path = Column(String, nullable=True)
    chapter_id = Column(Integer, ForeignKey('chapters.id'), nullable=False)

    chapter = relationship("Chapter", back_populates="videos")

    def __repr__(self):
        return f"<Video(name='{self.name}', chapter_id={self.chapter_id})>"


# --- راه‌اندازی پایگاه داده ---
DATABASE_FILE = "course_scheduler.db"
DATABASE_URL = f"sqlite:///./{DATABASE_FILE}"
# `check_same_thread=False` برای استفاده از SQLite با ترد اصلی GUI (مانند Tkinter/CustomTkinter) لازم است.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_db_and_tables():
    """جداول پایگاه داده را در صورت عدم وجود ایجاد می‌کند."""
    Base.metadata.create_all(bind=engine)


def get_db_session():
    """یک session جدید پایگاه داده برمی‌گرداند."""
    return SessionLocal()
