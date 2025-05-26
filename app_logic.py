import os
import traceback
from tkinter import filedialog

from moviepy import VideoFileClip

from database import (
    get_db_session,
    Course,
    Chapter,
    Video,
    WatchedStatusEnum,
)

# Supported video file extensions (case-insensitive)
VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv')


class VideoSchedulerAppLogic:
    def __init__(self):
        self.db_session = get_db_session()
        self.current_course = None
        self.gui_callbacks = {}  # To call GUI update functions

    def register_gui_callbacks(self, **callbacks):
        """Registers callback functions for updating the GUI."""
        self.gui_callbacks = callbacks

    def _call_gui_callback(self, callback_name, *args):
        """Calls a specific GUI callback if it exists."""
        if callback_name in self.gui_callbacks and callable(self.gui_callbacks[callback_name]):
            self.gui_callbacks[callback_name](*args)

    @staticmethod
    def get_video_duration(video_path):
        """
        Extracts video duration using MoviePy.
        Returns duration in seconds (float) or None on error.
        """
        try:
            print(f"Attempting to get duration for: {video_path}")
            # Using a context manager for VideoFileClip is good practice
            with VideoFileClip(video_path) as clip:
                duration = clip.duration

            if duration is not None and duration > 0:
                print(f"Duration found for {video_path}: {duration} seconds")
                return float(duration)
            else:
                print(f"MoviePy Warning: Invalid duration (zero, None, or negative) for video {video_path}. Duration: {duration}")
                return None
        except Exception as e:
            print(f"MoviePy Error: Could not read duration for video {video_path}. Error: {e}")
            # traceback.print_exc() # Uncomment for full stack trace during debugging
            return None

    @staticmethod
    def find_subtitle(video_path):
        """Finds a subtitle file with the same base name as the video."""
        base, _ = os.path.splitext(video_path)
        for sub_ext in ['.srt', '.vtt', '.ass']:  # Common subtitle extensions
            subtitle_file = base + sub_ext
            if os.path.exists(subtitle_file):
                return subtitle_file
        return None

    def select_and_load_course(self):
        """Handles course selection via dialog and loads or creates it."""
        directory_path = filedialog.askdirectory(title="Select Main Course Folder")
        if not directory_path:
            return  # User cancelled

        # Check if this directory path is already a registered course
        course = self.db_session.query(Course).filter(Course.base_directory_path == directory_path).first()

        if course:
            self.current_course = course
            self._call_gui_callback("show_message", f"Course '{course.name}' loaded from database.", "info")
        else:
            # New course: get name (for now, from folder name, ideally from user input)
            course_name_suggestion = os.path.basename(directory_path)
            # In a real app, use simpledialog.askstring or a CTkInputDialog for the name
            course_name = course_name_suggestion

            # Check if a course with this name (but different path) already exists
            existing_course_with_name = self.db_session.query(Course).filter(Course.name == course_name).first()
            if existing_course_with_name:
                self._call_gui_callback("show_message",
                                        f"A course named '{course_name}' already exists with a different path. "
                                        f"Please choose a different name or load the existing course by its folder.", "error")
                return

            new_course = Course(name=course_name, base_directory_path=directory_path)
            self.db_session.add(new_course)
            try:
                self.db_session.flush()  # Get new_course.id before full commit
                self._scan_and_save_course_content(new_course, directory_path, is_new_course=True)
                self.db_session.commit()  # Commit all changes for the new course
                self.current_course = new_course
                self._call_gui_callback("show_message", f"New course '{new_course.name}' created and scanned.", "info")
            except Exception as e:
                self.db_session.rollback()  # Rollback on error
                print(f"Error creating new course '{course_name}': {e}")
                traceback.print_exc()
                self._call_gui_callback("show_message", f"Error creating course: {e}", "error")
                self.current_course = None  # Ensure no partially set course
                return

        self._call_gui_callback("display_course_info", self.current_course)
        self._call_gui_callback("update_course_list_display")  # Refresh the list of all courses in GUI

    def _scan_and_save_course_content(self, course_obj, directory_path, is_new_course=False):
        """
        Scans the course directory for chapters and videos, then saves/updates them in the database.
        - If subdirectories exist, they are chapters. Videos in root are ignored.
        - If no subdirectories, the root directory is the single chapter.
        """
        print(f"Scanning content for course '{course_obj.name}' at path: {directory_path}")
        overall_course_duration = 0.0

        # Show progress dialog
        self._call_gui_callback("show_progress_dialog", "Scanning course...")
        self._call_gui_callback("update_progress", 0, "Initializing scan...")

        # Sets to keep track of items found on disk during this scan
        current_disk_chapter_paths = set()

        # 1. Determine potential chapters (subdirectories or the root itself)
        potential_chapters_info = []

        if not os.path.isdir(directory_path):
            self._call_gui_callback("hide_progress_dialog")
            raise FileNotFoundError(f"Course base path '{directory_path}' not found or is not a directory.")

        # Find actual subdirectories to be treated as chapters
        actual_subdirectories = []
        try:
            self._call_gui_callback("update_progress", 0.05, "Scanning directories...")
            for item_name in os.listdir(directory_path):
                item_full_path = os.path.join(directory_path, item_name)
                if os.path.isdir(item_full_path):
                    actual_subdirectories.append(item_name)
        except PermissionError:
            self._call_gui_callback("hide_progress_dialog")
            print(f"Permission denied to read directory: {directory_path}")
            raise  # Re-raise to be caught by the caller

        if actual_subdirectories:
            print(f"Found subdirectories (chapters): {actual_subdirectories}")
            for subdir_name in sorted(actual_subdirectories):  # Sort for consistent ordering
                potential_chapters_info.append({
                    'name': subdir_name,
                    'path': os.path.join(directory_path, subdir_name)
                })
        else:
            # No subdirectories found, the root directory itself is the single chapter
            print("No subdirectories found. Treating root directory as a single chapter.")
            potential_chapters_info.append({
                'name': course_obj.name,  # Chapter name will be the course name
                'path': directory_path
            })

        if not potential_chapters_info:
            print(f"Warning: No chapters found to process in '{directory_path}'.")
            course_obj.total_duration_seconds = 0.0
            self._call_gui_callback("hide_progress_dialog")
            return

        # 2. Process each identified chapter
        total_chapters = len(potential_chapters_info)
        for chapter_index, chap_info in enumerate(potential_chapters_info, 1):
            # Update progress
            progress = (chapter_index - 1) / total_chapters
            self._call_gui_callback("update_progress", progress, f"Processing chapter {chapter_index} of {total_chapters}...")

            disk_chapter_order = chapter_index
            chapter_path_on_disk = chap_info['path']
            chapter_name_on_disk = chap_info['name']
            current_disk_chapter_paths.add(chapter_path_on_disk)

            db_chapter = None
            if not is_new_course:  # For existing courses, try to find the chapter by its path
                db_chapter = self.db_session.query(Chapter).filter_by(
                    course_id=course_obj.id,
                    path=chapter_path_on_disk
                ).first()

            if not db_chapter:  # Chapter is new to the database for this course
                print(f"  Creating new chapter entry: '{chapter_name_on_disk}' (Order: {disk_chapter_order})")
                db_chapter = Chapter(
                    name=chapter_name_on_disk,
                    path=chapter_path_on_disk,
                    order_in_course=disk_chapter_order,
                    course_id=course_obj.id
                )
                self.db_session.add(db_chapter)
                self.db_session.flush()
            else:  # Chapter already exists, update its info
                print(f"  Updating existing chapter: '{chapter_name_on_disk}' (New Order: {disk_chapter_order})")
                db_chapter.name = chapter_name_on_disk
                db_chapter.order_in_course = disk_chapter_order

            # 3. Scan for videos within the current chapter path
            chapter_total_duration = 0.0
            disk_video_order = 0
            current_disk_video_paths_in_chapter = set()

            # Get all files in the chapter directory
            try:
                chapter_files = os.listdir(chapter_path_on_disk)
            except PermissionError:
                print(f"Permission denied to read chapter directory: {chapter_path_on_disk}")
                continue

            # Filter for video files
            video_files = [f for f in chapter_files if os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS]
            total_videos = len(video_files)

            for video_index, video_filename in enumerate(sorted(video_files), 1):
                # Update progress for videos
                video_progress = (chapter_index - 1 + video_index / total_videos) / total_chapters
                self._call_gui_callback("update_progress", video_progress, 
                    f"Processing chapter {chapter_index} of {total_chapters} - video {video_index} of {total_videos}...")

                disk_video_order += 1
                video_path = os.path.join(chapter_path_on_disk, video_filename)
                current_disk_video_paths_in_chapter.add(video_path)

                # Get video duration
                video_duration = self.get_video_duration(video_path)
                if video_duration is None:
                    print(f"Warning: Could not get duration for video: {video_path}")
                    video_duration = 0.0

                # Find subtitle if exists
                subtitle_path = self.find_subtitle(video_path)

                # Check if video already exists in database
                db_video = None
                if not is_new_course:
                    db_video = self.db_session.query(Video).filter_by(
                        chapter_id=db_chapter.id,
                        file_path=video_path
                    ).first()

                if not db_video:  # New video
                    print(f"    Adding new video: '{video_filename}' (Order: {disk_video_order})")
                    db_video = Video(
                        name=video_filename,
                        file_path=video_path,
                        duration_seconds=video_duration,
                        order_in_chapter=disk_video_order,
                        chapter_id=db_chapter.id,
                        subtitle_path=subtitle_path
                    )
                    self.db_session.add(db_video)
                else:  # Update existing video
                    print(f"    Updating existing video: '{video_filename}' (New Order: {disk_video_order})")
                    db_video.name = video_filename
                    db_video.file_path = video_path
                    db_video.duration_seconds = video_duration
                    db_video.order_in_chapter = disk_video_order
                    db_video.subtitle_path = subtitle_path

                chapter_total_duration += video_duration

            # Update chapter duration
            db_chapter.total_duration_seconds = chapter_total_duration
            overall_course_duration += chapter_total_duration

        # Update course total duration
        course_obj.total_duration_seconds = overall_course_duration

        # Final progress update
        self._call_gui_callback("update_progress", 1.0, "Scan completed!")
        # Hide progress dialog
        self._call_gui_callback("hide_progress_dialog")

    def rescan_current_course(self):
        """Rescans the currently loaded course for file changes."""
        if not self.current_course:
            self._call_gui_callback("show_message", "No course selected to rescan.", "warning")
            return

        self._call_gui_callback("show_message", f"Rescanning course: {self.current_course.name}...", "info")
        try:
            # Refresh the course object from DB to get latest state before scan
            self.db_session.refresh(self.current_course)
            self._scan_and_save_course_content(self.current_course,
                                               self.current_course.base_directory_path,
                                               is_new_course=False)
            self.db_session.commit()  # Commit all changes from the rescan
            self._call_gui_callback("show_message", "Course rescan completed successfully.", "info")
        except Exception as e:
            self.db_session.rollback()
            print(f"Error during course rescan: {e}")
            traceback.print_exc()
            self._call_gui_callback("show_message", f"Error during rescan: {e}", "error")

        # Refresh current_course object and GUI display after potential changes
        if self.current_course:
            self.db_session.refresh(self.current_course)
        self._call_gui_callback("display_course_info", self.current_course)

    def generate_schedule(self, num_days_str, max_daily_hours_str):
        """Generates a viewing schedule for the current course."""
        if not self.current_course:
            self._call_gui_callback("show_message", "Please load a course first to generate a schedule.", "warning")
            return []
        try:
            num_days = int(num_days_str)
            max_daily_minutes_input = int(float(max_daily_hours_str.replace(",", ".")) * 60)
        except ValueError:
            self._call_gui_callback("show_message",
                                    "Number of days and max daily hours must be valid numbers "
                                    "(e.g., for hours: 1 or 1.5).", "error")
            return []

        if num_days <= 0 or max_daily_minutes_input <= 0:
            self._call_gui_callback("show_message", "Number of days and max daily hours must be positive.", "error")
            return []

        # Expire all data in session to ensure fresh data from DB for schedule generation
        self.db_session.expire_all()
        refreshed_course = self.db_session.query(Course).filter_by(id=self.current_course.id).first()
        if not refreshed_course:
            self._call_gui_callback("show_message", "Error: Current course not found in database for scheduling.", "error")
            return []
        self.current_course = refreshed_course  # Use the refreshed object

        all_videos_flat = []
        for chapter in self.current_course.chapters:  # Assumes chapters are ordered by relationship
            for video in chapter.videos:  # Assumes videos are ordered by relationship
                if video.watched_status != WatchedStatusEnum.WATCHED:
                    all_videos_flat.append({
                        "id": video.id,
                        "name": video.name,
                        "total_duration_seconds": video.duration_seconds,
                        "remaining_seconds": video.duration_seconds - video.watched_seconds,
                        "chapter_name": chapter.name,
                        "current_offset_seconds": video.watched_seconds  # Where to start watching from
                    })

        if not all_videos_flat:
            self._call_gui_callback("show_message", "All videos in this course have been watched, or no videos to schedule.", "info")
            return []

        total_remaining_course_duration_seconds = sum(v["remaining_seconds"] for v in all_videos_flat)

        # Check if completion is possible with given constraints
        if (total_remaining_course_duration_seconds / 60) > (num_days * max_daily_minutes_input) and total_remaining_course_duration_seconds > 0.1:
            min_daily_needed = (total_remaining_course_duration_seconds / 60) / num_days if num_days > 0 else float('inf')
            message = (f"Warning: Completing the course in {num_days} days with {max_daily_minutes_input} minutes/day is not possible.\n"
                       f"You need at least {min_daily_needed:.2f} minutes/day.")
            self._call_gui_callback("show_message", message, "warning")
            # Continue to generate schedule anyway, it will show what's possible

        schedule_output_for_gui = []
        current_video_idx = 0

        for day_num in range(1, num_days + 1):
            daily_tasks_text = []
            time_allocated_for_day_seconds = 0.0

            while time_allocated_for_day_seconds < max_daily_minutes_input and current_video_idx < len(all_videos_flat):
                video_to_watch = all_videos_flat[current_video_idx]

                if video_to_watch["remaining_seconds"] < 0.1:  # Already watched or negligible remaining
                    current_video_idx += 1
                    continue

                time_can_spend_on_this_video_today = float(max_daily_minutes_input) - time_allocated_for_day_seconds
                watch_duration_this_session = min(video_to_watch["remaining_seconds"], time_can_spend_on_this_video_today)

                if watch_duration_this_session < 0.1:  # Not enough time left today for a meaningful chunk
                    break

                start_offset_s = video_to_watch["current_offset_seconds"]
                end_offset_s = video_to_watch["current_offset_seconds"] + watch_duration_this_session

                task_description = (
                    f"Chapter: {video_to_watch['chapter_name']}, Video: {video_to_watch['name']}\n"
                    f"  Watch from {start_offset_s // 60:.0f}m{start_offset_s % 60:02.0f}s "
                    f"to {end_offset_s // 60:.0f}m{end_offset_s % 60:02.0f}s "
                    f"(Duration this session: {watch_duration_this_session // 60:.0f}m{watch_duration_this_session % 60:02.0f}s)"
                )
                daily_tasks_text.append(task_description)

                time_allocated_for_day_seconds += watch_duration_this_session
                video_to_watch["remaining_seconds"] -= watch_duration_this_session
                video_to_watch["current_offset_seconds"] += watch_duration_this_session  # Update for next potential session

                if video_to_watch["remaining_seconds"] < 0.1:  # Video finished in this session
                    current_video_idx += 1

            if daily_tasks_text:
                schedule_output_for_gui.append({
                    "day": day_num,
                    "tasks_text": daily_tasks_text,
                    "total_time_minutes": time_allocated_for_day_seconds / 60
                })

            if current_video_idx >= len(all_videos_flat):  # All videos scheduled
                break

        if current_video_idx < len(all_videos_flat) and schedule_output_for_gui:
            # Count videos that still have significant time remaining
            remaining_videos_with_time = sum(1 for i in range(current_video_idx, len(all_videos_flat))
                                             if all_videos_flat[i]["remaining_seconds"] > 0.1)
            if remaining_videos_with_time > 0:
                self._call_gui_callback("show_message",
                                        f"Warning: With this plan, {remaining_videos_with_time} video(s) (or parts) will remain.",
                                        "warning")
        elif schedule_output_for_gui:
            self._call_gui_callback("show_message", "Viewing schedule generated successfully.", "info")

        return schedule_output_for_gui

    def update_video_progress(self, video_id_str, new_watched_status_str, watched_seconds_str="0"):
        """Updates the watched status and progress of a video."""
        try:
            video_id = int(video_id_str.replace("vid_", ""))  # Assuming vid_ prefix from Treeview iid
            video = self.db_session.query(Video).filter(Video.id == video_id).first()
            if not video:
                self._call_gui_callback("show_message", f"Error: Video with ID {video_id} not found.", "error")
                return

            new_status = WatchedStatusEnum(new_watched_status_str)  # Convert string to Enum member

            if new_status == WatchedStatusEnum.WATCHED:
                video.watched_seconds = video.duration_seconds
            elif new_status == WatchedStatusEnum.UNWATCHED:
                video.watched_seconds = 0.0
            elif new_status == WatchedStatusEnum.PARTIALLY_WATCHED:
                try:
                    # Allow for float input, replace comma with dot for European locales
                    ws = float(watched_seconds_str.replace(",", "."))
                    if 0 < ws < video.duration_seconds:
                        video.watched_seconds = ws
                    elif ws >= video.duration_seconds:  # If user enters more than duration, mark as watched
                        video.watched_seconds = video.duration_seconds
                        new_status = WatchedStatusEnum.WATCHED
                    else:  # If 0 or negative, mark as unwatched
                        video.watched_seconds = 0.0
                        new_status = WatchedStatusEnum.UNWATCHED
                except ValueError:
                    self._call_gui_callback("show_message",
                                            f"Invalid value for watched time: '{watched_seconds_str}'. Must be a number.",
                                            "error")
                    return  # Do not proceed if value is invalid

            video.watched_status = new_status
            self.db_session.commit()
            self._call_gui_callback("show_message", f"Video '{video.name}' status updated.", "info")
            # Refresh GUI to show updated status
            self._call_gui_callback("display_course_info", self.current_course)

        except ValueError as ve:  # Handles errors from int() or WatchedStatusEnum() conversion
            self._call_gui_callback("show_message", f"Error in input value: {ve}", "error")
        except Exception as e:
            self.db_session.rollback()
            self._call_gui_callback("show_message", f"Error updating video status: {e}", "error")
            traceback.print_exc()

    def get_all_courses(self):
        """Retrieves all courses from the database, ordered by name."""
        return self.db_session.query(Course).order_by(Course.name).all()

    def load_course_by_id(self, course_id):
        """Loads a specific course by its ID and updates the GUI."""
        course = self.db_session.query(Course).filter(Course.id == course_id).first()
        if course:
            self.current_course = course
            self._call_gui_callback("display_course_info", self.current_course)
            self._call_gui_callback("show_message", f"Course '{course.name}' loaded.", "info")
        else:  # Should not happen if ID comes from a valid list
            self.current_course = None
            self._call_gui_callback("display_course_info", None)
            self._call_gui_callback("show_message", f"Error: Course with ID {course_id} not found.", "error")

    def delete_course(self, course_id):
        """Deletes a course (and its chapters/videos via cascade) from the database."""
        course_to_delete = self.db_session.query(Course).filter(Course.id == course_id).first()
        if course_to_delete:
            course_name = course_to_delete.name
            self.db_session.delete(course_to_delete)
            self.db_session.commit()

            # If the deleted course was the current one, clear current_course
            if self.current_course and self.current_course.id == course_id:
                self.current_course = None
                self._call_gui_callback("display_course_info", None)  # Clear details view

            self._call_gui_callback("show_message", f"Course '{course_name}' deleted successfully.", "info")
            # Refresh the list of courses in the GUI
            if "update_course_list_display" in self.gui_callbacks:
                self.gui_callbacks["update_course_list_display"]()
        else:
            self._call_gui_callback("show_message", f"Error: Course with ID {course_id} not found for deletion.", "error")

    def close_db_session(self):
        """Closes the database session when the application exits."""
        if self.db_session:
            self.db_session.close()
            print("Database session closed.")
