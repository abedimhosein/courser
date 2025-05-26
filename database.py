# database.py

import enum
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, Enum as SAEnum
from sqlalchemy.orm import relationship, sessionmaker, declarative_base

# Base class for declarative models
Base = declarative_base()


# Enum for video watch status
class WatchedStatusEnum(enum.Enum):
    UNWATCHED = "Unwatched"
    PARTIALLY_WATCHED = "Partially Watched"
    WATCHED = "Watched"


class Course(Base):
    __tablename__ = 'courses'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    path = Column(String, nullable=False)
    total_duration_seconds = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to chapters, ordered by their order in the course
    chapters = relationship("Chapter", back_populates="course", cascade="all, delete-orphan")
    schedules = relationship("Schedule", back_populates="course", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Course(name='{self.name}')>"


class Chapter(Base):
    __tablename__ = 'chapters'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    path = Column(String, nullable=False)  # Full path to the chapter directory
    order_in_course = Column(Integer, nullable=False)  # Order of this chapter within the course
    total_duration_seconds = Column(Float, default=0)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)

    course = relationship("Course", back_populates="chapters")
    # Relationship to videos, ordered by their order in the chapter
    videos = relationship("Video", back_populates="chapter", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Chapter(name='{self.name}', course_id={self.course_id})>"


class Video(Base):
    __tablename__ = 'videos'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)  # Video file name
    path = Column(String, nullable=False)
    duration_seconds = Column(Float, nullable=False)
    watched_seconds = Column(Float, default=0)
    watched_status = Column(SAEnum(WatchedStatusEnum), default=WatchedStatusEnum.UNWATCHED)
    order_in_chapter = Column(Integer, nullable=False)  # Order of this video within the chapter
    chapter_id = Column(Integer, ForeignKey('chapters.id'), nullable=False)
    subtitle_path = Column(String, nullable=True)  # Path to subtitle file if exists

    chapter = relationship("Chapter", back_populates="videos")
    schedule_tasks = relationship("ScheduleTask", back_populates="video")

    def __repr__(self):
        return f"<Video(name='{self.name}', chapter_id={self.chapter_id})>"


class Schedule(Base):
    __tablename__ = 'schedules'

    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    num_days = Column(Integer, nullable=False)
    max_daily_minutes = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    course = relationship("Course", back_populates="schedules")
    daily_schedules = relationship("DailySchedule", back_populates="schedule", cascade="all, delete-orphan")


class DailySchedule(Base):
    __tablename__ = 'daily_schedules'

    id = Column(Integer, primary_key=True)
    schedule_id = Column(Integer, ForeignKey('schedules.id'), nullable=False)
    day_number = Column(Integer, nullable=False)
    total_time_minutes = Column(Float, nullable=False)
    
    # Relationships
    schedule = relationship("Schedule", back_populates="daily_schedules")
    tasks = relationship("ScheduleTask", back_populates="daily_schedule", cascade="all, delete-orphan")


class ScheduleTask(Base):
    __tablename__ = 'schedule_tasks'

    id = Column(Integer, primary_key=True)
    daily_schedule_id = Column(Integer, ForeignKey('daily_schedules.id'), nullable=False)
    video_id = Column(Integer, ForeignKey('videos.id'), nullable=False)
    chapter_name = Column(String, nullable=False)
    video_name = Column(String, nullable=False)
    start_time_seconds = Column(Float, nullable=False)
    end_time_seconds = Column(Float, nullable=False)
    duration_seconds = Column(Float, nullable=False)
    
    # Relationships
    daily_schedule = relationship("DailySchedule", back_populates="tasks")
    video = relationship("Video", back_populates="schedule_tasks")


# --- Database Setup ---
DATABASE_FILE = "course_scheduler.db"  # Database file will be in the same directory as the script
DATABASE_URL = f"sqlite:///./{DATABASE_FILE}"

# `check_same_thread=False` is needed for SQLite when used with a GUI thread (like Tkinter/CustomTkinter).
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# SessionLocal is a factory for creating database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_db_and_tables():
    """Creates database tables if they don't already exist."""
    Base.metadata.create_all(bind=engine)


def get_db_session():
    """Returns a new database session."""
    return SessionLocal()
