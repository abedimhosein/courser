# database.py

import enum
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime, Enum as SAEnum
from sqlalchemy.orm import relationship, sessionmaker, declarative_base

# Base class for declarative models
Base = declarative_base()


# Enum for video watch status
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

    # Relationship to chapters, ordered by their order in the course
    chapters = relationship("Chapter", back_populates="course", cascade="all, delete-orphan", order_by="Chapter.order_in_course")

    def __repr__(self):
        return f"<Course(name='{self.name}')>"


class Chapter(Base):
    __tablename__ = 'chapters'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    path = Column(String, nullable=False)  # Full path to the chapter directory
    order_in_course = Column(Integer, nullable=False)  # Order of this chapter within the course
    total_duration_seconds = Column(Float, default=0.0)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)

    course = relationship("Course", back_populates="chapters")
    # Relationship to videos, ordered by their order in the chapter
    videos = relationship("Video", back_populates="chapter", cascade="all, delete-orphan", order_by="Video.order_in_chapter")

    def __repr__(self):
        return f"<Chapter(name='{self.name}', course_id={self.course_id})>"


class Video(Base):
    __tablename__ = 'videos'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # Video file name
    file_path = Column(String, unique=True, nullable=False)  # Full path to the video file
    duration_seconds = Column(Float, nullable=False)
    order_in_chapter = Column(Integer, nullable=False)  # Order of this video within the chapter
    watched_status = Column(SAEnum(WatchedStatusEnum), default=WatchedStatusEnum.UNWATCHED, nullable=False)
    watched_seconds = Column(Float, default=0.0, nullable=False)  # How much of the video has been watched
    subtitle_path = Column(String, nullable=True)  # Optional path to subtitle file
    chapter_id = Column(Integer, ForeignKey('chapters.id'), nullable=False)

    chapter = relationship("Chapter", back_populates="videos")

    def __repr__(self):
        return f"<Video(name='{self.name}', chapter_id={self.chapter_id})>"


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
