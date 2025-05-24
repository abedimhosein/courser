import os
import subprocess
import json
from tkinter import filedialog
from moviepy import VideoFileClip
from database import (
    get_db_session,
    Course,
    Chapter,
    Video,
    WatchedStatusEnum,
)


class VideoSchedulerAppLogic:
    def __init__(self):
        self.db_session = get_db_session()
        self.current_course = None
        self.gui_callbacks = {}  # برای فراخوانی توابع به‌روزرسانی GUI

    def register_gui_callbacks(self, **callbacks):
        """توابع callback برای به‌روزرسانی GUI را ثبت می‌کند."""
        self.gui_callbacks = callbacks

    def _call_gui_callback(self, callback_name, *args):
        """یک callback خاص GUI را در صورت وجود فراخوانی می‌کند."""
        if callback_name in self.gui_callbacks and callable(self.gui_callbacks[callback_name]):
            self.gui_callbacks[callback_name](*args)

    @staticmethod
    def get_video_duration(video_path):
        """
        مدت زمان ویدیو را با استفاده از ffprobe (و یا MoviePy به عنوان fallback) استخراج می‌کند.
        مدت زمان را به ثانیه برمی‌گرداند یا None در صورت خطا.
        """
        # تلاش با ffprobe
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', '-show_streams', video_path
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            if result.returncode == 0 and result.stdout:
                metadata = json.loads(result.stdout)
                if 'format' in metadata and 'duration' in metadata['format']:
                    dur_str = metadata['format']['duration']
                    if dur_str: return float(dur_str)
                if 'streams' in metadata and metadata['streams']:
                    for stream in metadata['streams']:  # جستجو در استریم‌های ویدیو
                        if stream.get('codec_type') == 'video' and 'duration' in stream:
                            dur_str = stream['duration']
                            if dur_str: return float(dur_str)
                # اگر در فرمت یا استریم ویدیو نبود، اولین استریم با duration را امتحان کن
                if 'streams' in metadata and metadata['streams'] and 'duration' in metadata['streams'][0]:
                    dur_str = metadata['streams'][0]['duration']
                    if dur_str: return float(dur_str)

            print(f"هشدار ffprobe: مدت زمان نامعتبر یا عدم یافتن برای {video_path}. خطای احتمالی: {result.stderr}")
            return None
        except FileNotFoundError:
            try:
                with VideoFileClip(video_path) as clip:
                    duration = clip.duration
                return duration if duration and duration > 0 else None
            except Exception as e_moviepy:
                print(f"خطا در MoviePy برای {video_path}: {e_moviepy}")
                return None
        except Exception as e_ff:
            print(f"خطا در اجرای ffprobe برای {video_path}: {e_ff}")
            return None

    @staticmethod
    def find_subtitle(video_path):
        base, _ = os.path.splitext(video_path)
        for sub_ext in ['.srt', '.vtt', '.ass']:
            subtitle_file = base + sub_ext
            if os.path.exists(subtitle_file):
                return subtitle_file
        return None

    def select_and_load_course(self):  # بدون تغییر نسبت به نسخه کامل قبلی
        directory_path = filedialog.askdirectory(title="انتخاب پوشه اصلی دوره")
        if not directory_path:
            return

        course = self.db_session.query(Course).filter(Course.base_directory_path == directory_path).first()

        if course:
            self.current_course = course
            self._call_gui_callback("show_message", f"دوره '{course.name}' از پایگاه داده بارگذاری شد.", "info")
        else:
            course_name_suggestion = os.path.basename(directory_path)
            course_name = course_name_suggestion  # در یک برنامه واقعی از کاربر پرسیده شود

            existing_course_with_name = self.db_session.query(Course).filter(Course.name == course_name).first()
            if existing_course_with_name:
                self._call_gui_callback("show_message", f"دوره‌ای با نام '{course_name}' قبلاً با مسیر دیگری ثبت شده.", "error")
                return

            new_course = Course(name=course_name, base_directory_path=directory_path)
            self.db_session.add(new_course)
            try:
                self.db_session.flush()
                # حالا _scan_and_save_course_content را فراخوانی می‌کنیم
                self._scan_and_save_course_content(new_course, directory_path, is_new_course=True)
                self.db_session.commit()
                self.current_course = new_course
                self._call_gui_callback("show_message", f"دوره جدید '{new_course.name}' ایجاد شد.", "info")
            except Exception as e:
                self.db_session.rollback()
                print(f"خطا در ایجاد دوره جدید: {e}")  # برای دیباگ بهتر، traceback را هم لاگ کنید
                import traceback
                traceback.print_exc()
                self._call_gui_callback("show_message", f"خطا در ایجاد دوره: {e}", "error")
                self.current_course = None
                return

        self._call_gui_callback("display_course_info", self.current_course)
        self._call_gui_callback("update_course_list_display")

    def _scan_and_save_course_content(self, course_obj, directory_path, is_new_course=False):
        """
        محتوای دوره (فصل‌ها و ویدیوها) را اسکن و در پایگاه داده ذخیره/به‌روز می‌کند.
        این نسخه اصلاح شده تا ساب‌دایرکتوری‌ها را به درستی به عنوان فصل شناسایی کند.
        """
        print(f"شروع اسکن محتوای دوره: {course_obj.name} در مسیر: {directory_path}")
        overall_course_duration = 0.0

        # برای نگهداری مسیرهای فصل‌ها و ویدیوهایی که در این اسکن در دیسک یافت می‌شوند
        current_disk_chapter_paths = set()

        # 1. تعیین فصل‌های بالقوه (ساب‌دایرکتوری‌ها یا خود پوشه اصلی)
        potential_chapters_info = []

        if not os.path.isdir(directory_path):
            raise FileNotFoundError(f"مسیر اصلی دوره '{directory_path}' یافت نشد یا یک فایل است.")

        # ابتدا ساب‌دایرکتوری‌های واقعی را پیدا کن
        actual_subdirectories = []
        for item_name in os.listdir(directory_path):
            item_full_path = os.path.join(directory_path, item_name)
            if os.path.isdir(item_full_path):
                actual_subdirectories.append(item_name)

        if actual_subdirectories:
            # اگر ساب‌دایرکتوری وجود دارد، آن‌ها فصل‌ها هستند
            print(f"ساب‌دایرکتوری‌ها یافت شدند: {actual_subdirectories}")
            for subdir_name in sorted(actual_subdirectories):
                potential_chapters_info.append({
                    'name': subdir_name,
                    'path': os.path.join(directory_path, subdir_name)
                })
        else:
            # اگر ساب‌دایرکتوری وجود ندارد، خود پوشه اصلی دوره، تنها فصل است
            print("هیچ ساب‌دایرکتوری یافت نشد. پوشه اصلی به عنوان فصل در نظر گرفته می‌شود.")
            potential_chapters_info.append({
                'name': course_obj.name,  # نام فصل همان نام دوره خواهد بود
                'path': directory_path
            })

        if not potential_chapters_info:
            print(f"هشدار: هیچ فصل یا ویدیویی در مسیر '{directory_path}' برای پردازش یافت نشد.")
            course_obj.total_duration_seconds = 0.0  # اگر هیچ محتوایی نبود
            return  # اگر هیچ فصلی برای پردازش وجود ندارد خارج شو

        # 2. پردازش هر فصل شناسایی شده
        disk_chapter_order = 0
        for chap_info in potential_chapters_info:
            disk_chapter_order += 1

            chapter_path_on_disk = chap_info['path']
            chapter_name_on_disk = chap_info['name']
            current_disk_chapter_paths.add(chapter_path_on_disk)

            db_chapter = None
            if not is_new_course:  # برای دوره‌های موجود، سعی کن فصل را پیدا کنی
                db_chapter = self.db_session.query(Chapter).filter_by(
                    course_id=course_obj.id,
                    path=chapter_path_on_disk
                ).first()

            if not db_chapter:  # فصل جدید است
                print(f"  ایجاد فصل جدید: {chapter_name_on_disk} با مسیر: {chapter_path_on_disk}")
                db_chapter = Chapter(
                    name=chapter_name_on_disk,
                    path=chapter_path_on_disk,
                    order_in_course=disk_chapter_order,  # مقداردهی اولیه ترتیب
                    course_id=course_obj.id
                )
                self.db_session.add(db_chapter)
                self.db_session.flush()  # برای گرفتن ID و امکان افزودن ویدیو
            else:  # فصل موجود است، اطلاعاتش را به‌روز کن
                print(f"  به‌روزرسانی فصل موجود: {chapter_name_on_disk}")
                db_chapter.name = chapter_name_on_disk
                db_chapter.order_in_course = disk_chapter_order

            # 3. اسکن ویدیوها در داخل مسیر فصل فعلی (chapter_path_on_disk)
            chapter_total_duration = 0.0
            disk_video_order = 0
            current_disk_video_paths_in_chapter = set()

            try:
                # لیست کردن تمام آیتم‌ها در پوشه فصل
                # print(f"    اسکن ویدیوها در فصل '{chapter_name_on_disk}' مسیر: {chapter_path_on_disk}")
                items_in_chapter_dir = sorted(os.listdir(chapter_path_on_disk))
            except FileNotFoundError:
                print(f"    خطا: مسیر فصل '{chapter_path_on_disk}' یافت نشد. از این فصل صرف‌نظر می‌شود.")
                # اگر فصل در دیتابیس بود و الان نیست، در بخش بعدی (حذف فصل‌های گمشده) مدیریت می‌شود
                continue
            except PermissionError:
                print(f"    خطا: اجازه دسترسی به مسیر فصل '{chapter_path_on_disk}' وجود ندارد.")
                continue

            # print(f"    آیتم‌های یافت شده در '{chapter_name_on_disk}': {items_in_chapter_dir}")

            for file_name in items_in_chapter_dir:
                video_file_path_on_disk = os.path.join(chapter_path_on_disk, file_name)

                # بررسی اینکه آیا آیتم یک فایل است و پسوند ویدیویی دارد
                if not (os.path.isfile(video_file_path_on_disk) and file_name.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv'))):
                    # print(f"      نادیده گرفتن (فایل ویدیو نیست): {video_file_path_on_disk}")
                    continue

                    # print(f"    پردازش فایل ویدیو: {video_file_path_on_disk}")
                current_disk_video_paths_in_chapter.add(video_file_path_on_disk)
                disk_video_order += 1

                db_video = None
                if not is_new_course:
                    db_video = self.db_session.query(Video).filter_by(
                        # chapter_id=db_chapter.id, # این شرط لازم است اگر فایل با مسیر یکسان در چند فصل باشد
                        file_path=video_file_path_on_disk  # مسیر فایل ویدیو باید یکتا باشد در کل دیتابیس
                    ).first()
                    # اگر db_video پیدا شد ولی chapter_id آن با db_chapter.id فعلی متفاوت بود، یعنی مشکلی در داده‌ها هست
                    # یا ویدیو به فصل دیگری منتقل شده. در این سناریو ساده فرض می‌کنیم file_path یکتاست.
                    if db_video and db_video.chapter_id != db_chapter.id:
                        print(f"      هشدار: ویدیوی {file_name} با مسیر یکسان در فصل دیگری ({db_video.chapter_id}) یافت شد. این ویدیو برای فصل فعلی ({db_chapter.name}) دوباره ایجاد می‌شود.")
                        db_video = None  # مجبور به ایجاد مجدد برای این فصل

                video_duration = self.get_video_duration(video_file_path_on_disk)
                if video_duration is None or video_duration <= 0:
                    print(f"      هشدار: مدت زمان برای ویدیو '{video_file_path_on_disk}' قابل خواندن نیست یا صفر است.")
                    if db_video:  # اگر قبلا بوده و الان فایلش مشکل دارد، حذفش می‌کنیم
                        print(f"        ویدیوی نامعتبر '{db_video.name}' از فصل '{db_chapter.name}' حذف می‌شود.")
                        self.db_session.delete(db_video)
                    disk_video_order -= 1
                    current_disk_video_paths_in_chapter.remove(video_file_path_on_disk)
                    continue

                if not db_video:
                    print(f"      افزودن ویدیوی جدید: {file_name} به فصل {db_chapter.name}")
                    db_video = Video(
                        name=file_name,
                        file_path=video_file_path_on_disk,
                        duration_seconds=video_duration,
                        chapter_id=db_chapter.id  # اتصال به فصل فعلی
                    )
                    self.db_session.add(db_video)
                else:
                    # print(f"      به‌روزرسانی ویدیوی موجود: {file_name}")
                    db_video.name = file_name
                    db_video.duration_seconds = video_duration
                    # اگر ویدیو به این فصل تعلق نداشت و مجبور به ایجاد مجدد شدیم، chapter_id قبلا ست شده
                    # اگر ویدیو از قبل به همین فصل تعلق داشت، chapter_id آن صحیح است
                    if db_video.chapter_id != db_chapter.id:  # این حالت نباید رخ دهد اگر منطق بالا درست باشد
                        db_video.chapter_id = db_chapter.id

                db_video.order_in_chapter = disk_video_order
                db_video.subtitle_path = self.find_subtitle(video_file_path_on_disk)
                chapter_total_duration += video_duration

            # حذف ویدیوهایی از این فصل که در دیتابیس هستند ولی دیگر روی دیسک نیستند
            if not is_new_course:
                # اطمینان از اینکه db_chapter.id مقدار دارد (پس از flush یا اگر از قبل بوده)
                if db_chapter.id:
                    db_video_paths_for_this_chapter = {
                        vfp[0] for vfp in self.db_session.query(Video.file_path).filter_by(chapter_id=db_chapter.id).all()
                    }
                    videos_to_delete_paths = db_video_paths_for_this_chapter - current_disk_video_paths_in_chapter
                    if videos_to_delete_paths:
                        print(f"    حذف {len(videos_to_delete_paths)} ویدیوی گمشده از فصل '{db_chapter.name}'...")
                        for path_to_del in videos_to_delete_paths:
                            video_to_del_obj = self.db_session.query(Video).filter_by(chapter_id=db_chapter.id, file_path=path_to_del).first()
                            if video_to_del_obj: self.db_session.delete(video_to_del_obj)
                else:
                    print(f"    هشدار: فصل '{db_chapter.name}' شناسه معتبری برای حذف ویدیوهای گمشده ندارد.")

            db_chapter.total_duration_seconds = chapter_total_duration
            overall_course_duration += chapter_total_duration

        # 4. حذف فصل‌هایی از این دوره که در دیتابیس هستند ولی دیگر روی دیسک نیستند
        if not is_new_course:
            db_chapter_paths_for_this_course = {
                cp[0] for cp in self.db_session.query(Chapter.path).filter_by(course_id=course_obj.id).all()
            }
            chapters_to_delete_paths = db_chapter_paths_for_this_course - current_disk_chapter_paths
            if chapters_to_delete_paths:
                print(f"  حذف {len(chapters_to_delete_paths)} فصل گمشده از دوره '{course_obj.name}'...")
                for path_to_del in chapters_to_delete_paths:
                    chapter_to_del_obj = self.db_session.query(Chapter).filter_by(course_id=course_obj.id, path=path_to_del).first()
                    if chapter_to_del_obj: self.db_session.delete(chapter_to_del_obj)

        course_obj.total_duration_seconds = overall_course_duration
        print(f"پایان اسکن. مجموع زمان دوره: {overall_course_duration / 3600:.2f} ساعت.")

    def rescan_current_course(self):  # بدون تغییر نسبت به نسخه کامل قبلی
        if not self.current_course:
            self._call_gui_callback("show_message", "هیچ دوره‌ای برای بازاسکن انتخاب نشده است.", "warning")
            return

        print(f"شروع بازاسکن برای دوره: {self.current_course.name}...")
        self._call_gui_callback("show_message", f"درحال بازاسکن دوره: {self.current_course.name}...", "info")

        try:
            self.db_session.refresh(self.current_course)  # اطمینان از به‌روز بودن دوره از دیتابیس
            self._scan_and_save_course_content(self.current_course, self.current_course.base_directory_path, is_new_course=False)
            self.db_session.commit()
            self._call_gui_callback("show_message", "بازاسکن دوره با موفقیت انجام شد.", "info")
        except Exception as e:
            self.db_session.rollback()
            print(f"خطا در حین بازاسکن دوره: {e}")
            import traceback
            traceback.print_exc()
            self._call_gui_callback("show_message", f"خطا در بازاسکن: {e}", "error")

        if self.current_course:
            self.db_session.refresh(self.current_course)
        self._call_gui_callback("display_course_info", self.current_course)

    def generate_schedule(self, num_days_str, max_daily_hours_str):
        if not self.current_course:
            self._call_gui_callback("show_message", "لطفاً ابتدا یک دوره را بارگذاری یا انتخاب کنید.", "warning")
            return []

        try:
            num_days = int(num_days_str)
            # تبدیل ساعت به دقیقه، اجازه اعشار برای ساعت (مثلا 1.5 ساعت)
            max_daily_minutes_input = int(float(max_daily_hours_str.replace(",", ".")) * 60)  # جایگزینی کاما با نقطه برای اعداد اعشاری
        except ValueError:
            self._call_gui_callback("show_message", "تعداد روزها و حداکثر ساعت روزانه باید عدد باشند (مثلاً برای ساعت: 1 یا 1.5).", "error")
            return []

        if num_days <= 0 or max_daily_minutes_input <= 0:
            self._call_gui_callback("show_message", "تعداد روزها و حداکثر ساعت روزانه باید مثبت باشند.", "error")
            return []

        all_videos_flat = []
        # اطمینان از به‌روز بودن session
        self.db_session.expire_all()  # برای اینکه داده‌ها از دیتابیس مجدد خوانده شوند

        # current_course را مجددا از session بخوانید تا از به‌روز بودن آن مطمئن شوید
        refreshed_course = self.db_session.query(Course).filter_by(id=self.current_course.id).first()
        if not refreshed_course:
            self._call_gui_callback("show_message", "خطا: دوره فعلی در دیتابیس یافت نشد.", "error")
            return []
        self.current_course = refreshed_course

        for chapter in self.current_course.chapters:
            for video in chapter.videos:
                if video.watched_status != WatchedStatusEnum.WATCHED:
                    all_videos_flat.append({
                        "id": video.id,
                        "name": video.name,
                        "total_duration_seconds": video.duration_seconds,
                        "remaining_seconds": video.duration_seconds - video.watched_seconds,
                        "chapter_name": chapter.name,
                        "current_offset_seconds": video.watched_seconds
                    })

        if not all_videos_flat:
            self._call_gui_callback("show_message", "تمام ویدیوهای این دوره مشاهده شده‌اند یا ویدیویی برای برنامه‌ریزی نیست.", "info")
            return []

        total_remaining_course_duration_seconds = sum(v["remaining_seconds"] for v in all_videos_flat)

        if (total_remaining_course_duration_seconds / 60) > (num_days * max_daily_minutes_input) and total_remaining_course_duration_seconds > 0.1:
            min_daily_needed = (total_remaining_course_duration_seconds / 60) / num_days if num_days > 0 else float('inf')
            message = (f"هشدار: با حداکثر {max_daily_minutes_input} دقیقه در روز، اتمام دوره در {num_days} روز ممکن نیست.\n"
                       f"حداقل به روزی {min_daily_needed:.2f} دقیقه زمان نیاز دارید.")
            self._call_gui_callback("show_message", message, "warning")

        schedule_output_for_gui = []
        current_video_idx = 0

        for day_num in range(1, num_days + 1):
            daily_tasks_text = []
            time_allocated_for_day_seconds = 0.0  # استفاده از float برای دقت بیشتر

            while time_allocated_for_day_seconds < max_daily_minutes_input and current_video_idx < len(all_videos_flat):
                video_to_watch = all_videos_flat[current_video_idx]

                # اگر ویدیو هیچ زمان باقیمانده‌ای ندارد، از آن بگذر
                if video_to_watch["remaining_seconds"] < 0.1:  # تلورانس کوچک
                    current_video_idx += 1
                    continue

                time_can_spend_on_this_video_today = float(max_daily_minutes_input) - time_allocated_for_day_seconds

                watch_duration_this_session = min(video_to_watch["remaining_seconds"], time_can_spend_on_this_video_today)

                if watch_duration_this_session < 0.1:  # اگر زمان قابل مشاهده خیلی کم است، برو به روز بعد یا ویدیوی بعد
                    break

                start_display_seconds = video_to_watch["current_offset_seconds"]
                end_display_seconds = video_to_watch["current_offset_seconds"] + watch_duration_this_session

                task_description = (
                    f"فصل: {video_to_watch['chapter_name']}, ویدیو: {video_to_watch['name']}\n"
                    f"  از {start_display_seconds // 60:.0f}:{start_display_seconds % 60:02.0f} "
                    f"تا {end_display_seconds // 60:.0f}:{end_display_seconds % 60:02.0f} "
                    f"({watch_duration_this_session // 60:.0f}دقیقه و {watch_duration_this_session % 60:02.0f}ثانیه)"
                )
                daily_tasks_text.append(task_description)

                time_allocated_for_day_seconds += watch_duration_this_session
                video_to_watch["remaining_seconds"] -= watch_duration_this_session
                video_to_watch["current_offset_seconds"] += watch_duration_this_session

                if video_to_watch["remaining_seconds"] < 0.1:  # اگر ویدیو تمام شد
                    current_video_idx += 1

            if daily_tasks_text:
                schedule_output_for_gui.append({
                    "day": day_num,
                    "tasks_text": daily_tasks_text,
                    "total_time_minutes": time_allocated_for_day_seconds / 60
                })

            if current_video_idx >= len(all_videos_flat):  # همه ویدیوها برنامه‌ریزی شدند
                break

        if current_video_idx < len(all_videos_flat) and schedule_output_for_gui:  # اگر برنامه تولید شد ولی ویدیو باقی ماند
            remaining_videos_count = 0
            for i in range(current_video_idx, len(all_videos_flat)):
                if all_videos_flat[i]["remaining_seconds"] > 0.1:
                    remaining_videos_count += 1

            if remaining_videos_count > 0:
                self._call_gui_callback("show_message", f"هشدار: با این برنامه، {remaining_videos_count} ویدیو (یا بخش‌هایی از ویدیوها) باقی می‌ماند.", "warning")
        elif schedule_output_for_gui:
            self._call_gui_callback("show_message", "برنامه مشاهده با موفقیت تولید شد.", "info")

        return schedule_output_for_gui

    def update_video_progress(self, video_id_str, new_watched_status_str, watched_seconds_str="0"):
        try:
            video_id = int(video_id_str.replace("vid_", ""))
            video = self.db_session.query(Video).filter(Video.id == video_id).first()
            if not video:
                self._call_gui_callback("show_message", f"ویدیو با شناسه {video_id} یافت نشد.", "error")
                return

            new_status = WatchedStatusEnum(new_watched_status_str)

            if new_status == WatchedStatusEnum.WATCHED:
                video.watched_seconds = video.duration_seconds
            elif new_status == WatchedStatusEnum.UNWATCHED:
                video.watched_seconds = 0.0
            elif new_status == WatchedStatusEnum.PARTIALLY_WATCHED:
                try:
                    # اطمینان از اینکه ورودی عدد است و در محدوده صحیح قرار دارد
                    ws = float(watched_seconds_str.replace(",", "."))  # پشتیبانی از کاما و نقطه برای اعشار
                    if 0 < ws < video.duration_seconds:
                        video.watched_seconds = ws
                    elif ws >= video.duration_seconds:  # اگر بیشتر از کل ویدیو وارد شد، کامل در نظر بگیر
                        video.watched_seconds = video.duration_seconds
                        new_status = WatchedStatusEnum.WATCHED  # وضعیت را هم به کامل تغییر بده
                    else:  # اگر 0 یا منفی بود
                        video.watched_seconds = 0
                        new_status = WatchedStatusEnum.UNWATCHED  # وضعیت را هم به دیده نشده تغییر بده
                except ValueError:
                    self._call_gui_callback("show_message", f"مقدار نامعتبر برای زمان مشاهده شده: '{watched_seconds_str}'. باید عدد باشد.", "error")
                    return  # ادامه نده اگر مقدار نامعتبر است

            video.watched_status = new_status
            self.db_session.commit()
            self._call_gui_callback("show_message", f"وضعیت ویدیوی '{video.name}' به‌روز شد.", "info")
            # self.db_session.expire(video) # برای اطمینان از خواندن مجدد از دیتابیس در صورت نیاز
            self._call_gui_callback("display_course_info", self.current_course)

        except ValueError as ve:  # برای خطای تبدیل به int یا float یا enum
            self._call_gui_callback("show_message", f"خطا در مقدار ورودی: {ve}", "error")
        except Exception as e:
            self.db_session.rollback()
            self._call_gui_callback("show_message", f"خطا در به‌روزرسانی وضعیت ویدیو: {e}", "error")

    def get_all_courses(self):
        return self.db_session.query(Course).order_by(Course.name).all()

    def load_course_by_id(self, course_id):
        course = self.db_session.query(Course).filter(Course.id == course_id).first()
        if course:
            self.current_course = course
            self._call_gui_callback("display_course_info", self.current_course)
            self._call_gui_callback("show_message", f"دوره '{course.name}' بارگذاری شد.", "info")
        else:
            self.current_course = None
            self._call_gui_callback("display_course_info", None)
            self._call_gui_callback("show_message", f"دوره با شناسه {course_id} یافت نشد.", "error")

    def delete_course(self, course_id):
        course_to_delete = self.db_session.query(Course).filter(Course.id == course_id).first()
        if course_to_delete:
            course_name = course_to_delete.name
            self.db_session.delete(course_to_delete)
            self.db_session.commit()
            if self.current_course and self.current_course.id == course_id:
                self.current_course = None
                self._call_gui_callback("display_course_info", None)
            self._call_gui_callback("show_message", f"دوره '{course_name}' با موفقیت حذف شد.", "info")
            if "update_course_list_display" in self.gui_callbacks:  # بررسی وجود callback
                self.gui_callbacks["update_course_list_display"]()
        else:
            self._call_gui_callback("show_message", f"دوره با شناسه {course_id} برای حذف یافت نشد.", "error")

    def close_db_session(self):
        if self.db_session:
            self.db_session.close()
            print("Session پایگاه داده بسته شد.")
