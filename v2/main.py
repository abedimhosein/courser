# main.py

from tkinter import ttk, messagebox

import customtkinter as ctk

from app_logic import VideoSchedulerAppLogic, Video
from database import create_db_and_tables, WatchedStatusEnum


class VideoSchedulerGUI(ctk.CTk):
    def __init__(self, app_logic):
        super().__init__()
        self.app_logic = app_logic

        self.title("برنامه‌ریز مشاهده ویدیو")
        self.geometry("1000x700")
        ctk.set_appearance_mode("System")  # System, Dark, Light
        ctk.set_default_color_theme("blue")

        # ثبت توابع callback برای به‌روزرسانی GUI از طریق app_logic
        self.app_logic.register_gui_callbacks(
            display_course_info=self.display_course_info_in_treeview,
            show_message=self.show_status_message,
            update_course_list_display=self.update_course_list_display
        )

        # --- فریم اصلی ---
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill=ctk.BOTH, expand=True, padx=10, pady=10)

        # --- بخش مدیریت دوره‌ها (ستون چپ) ---
        courses_frame = ctk.CTkFrame(main_frame, width=250)
        courses_frame.pack(side=ctk.LEFT, fill=ctk.Y, padx=(0, 5), pady=0)
        courses_frame.pack_propagate(False)

        ctk.CTkLabel(courses_frame, text="دوره‌های من", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)

        self.course_listbox = ctk.CTkScrollableFrame(courses_frame, label_text="")  # برای لیست دوره‌ها
        self.course_listbox.pack(fill=ctk.BOTH, expand=True, padx=5, pady=(0, 5))
        # self.course_list_items = {} # برای نگهداری دکمه‌های دوره‌ها

        btn_add_course = ctk.CTkButton(courses_frame, text="افزودن/بارگذاری دوره جدید", command=self.app_logic.select_and_load_course)
        btn_add_course.pack(pady=5, fill=ctk.X, padx=5)

        btn_rescan_course = ctk.CTkButton(courses_frame, text="بازاسکن دوره فعلی", command=self.on_rescan_button_click)
        btn_rescan_course.pack(pady=5, fill=ctk.X, padx=5)

        # --- بخش جزئیات دوره و برنامه‌ریزی (ستون راست) ---
        details_schedule_frame = ctk.CTkFrame(main_frame)
        details_schedule_frame.pack(side=ctk.LEFT, fill=ctk.BOTH, expand=True)

        # تب‌ها برای جزئیات دوره و برنامه مشاهده
        self.tab_view = ctk.CTkTabview(details_schedule_frame)
        self.tab_view.pack(fill=ctk.BOTH, expand=True, padx=5, pady=5)
        self.tab_view.add("جزئیات دوره")
        self.tab_view.add("برنامه مشاهده")
        self.tab_view.set("جزئیات دوره")  # تب پیش‌فرض

        # --- تب جزئیات دوره ---
        course_details_tab = self.tab_view.tab("جزئیات دوره")

        self.lbl_course_title = ctk.CTkLabel(course_details_tab, text="هیچ دوره‌ای انتخاب نشده", font=ctk.CTkFont(size=16, weight="bold"))
        self.lbl_course_title.pack(pady=10)

        self.lbl_course_duration = ctk.CTkLabel(course_details_tab, text="")
        self.lbl_course_duration.pack(pady=5)

        # Treeview برای نمایش فصل‌ها و ویدیوها
        style = ttk.Style()
        style.theme_use("default")  # برای هماهنگی با CustomTkinter، ممکن است نیاز به تنظیمات بیشتری باشد
        style.configure("Treeview", rowheight=25, font=('Tahoma', 10))  # فونت و ارتفاع ردیف
        style.configure("Treeview.Heading", font=('Tahoma', 11, 'bold'))

        self.tree = ttk.Treeview(course_details_tab, columns=("duration", "status"), selectmode="browse")
        self.tree.heading("#0", text="نام آیتم (فصل/ویدیو)")
        self.tree.heading("duration", text="مدت زمان")
        self.tree.heading("status", text="وضعیت")
        self.tree.column("#0", width=350, stretch=ctk.YES)
        self.tree.column("duration", width=100, anchor=ctk.CENTER)
        self.tree.column("status", width=150, anchor=ctk.CENTER)
        self.tree.pack(fill=ctk.BOTH, expand=True, padx=5, pady=5)
        self.tree.bind("<Double-1>", self.on_treeview_double_click)  # برای تغییر وضعیت

        # --- تب برنامه مشاهده ---
        schedule_tab = self.tab_view.tab("برنامه مشاهده")

        schedule_input_frame = ctk.CTkFrame(schedule_tab)
        schedule_input_frame.pack(fill=ctk.X, padx=5, pady=5)

        ctk.CTkLabel(schedule_input_frame, text="تعداد روزها برای اتمام:").pack(side=ctk.LEFT, padx=5)
        self.entry_num_days = ctk.CTkEntry(schedule_input_frame, width=50)
        self.entry_num_days.pack(side=ctk.LEFT, padx=5)
        self.entry_num_days.insert(0, "30")

        ctk.CTkLabel(schedule_input_frame, text="حداکثر ساعت مشاهده در روز:").pack(side=ctk.LEFT, padx=5)
        self.entry_max_daily_hours = ctk.CTkEntry(schedule_input_frame, width=50)
        self.entry_max_daily_hours.pack(side=ctk.LEFT, padx=5)
        self.entry_max_daily_hours.insert(0, "1")

        btn_generate_schedule = ctk.CTkButton(schedule_input_frame, text="تولید برنامه", command=self.generate_schedule_display)
        btn_generate_schedule.pack(side=ctk.LEFT, padx=10)

        self.schedule_display_textbox = ctk.CTkTextbox(schedule_tab, wrap=ctk.WORD, state=ctk.DISABLED, font=('Tahoma', 10))
        self.schedule_display_textbox.pack(fill=ctk.BOTH, expand=True, padx=5, pady=5)

        # --- نوار وضعیت ---
        self.status_bar = ctk.CTkLabel(self, text="آماده", anchor=ctk.W, font=ctk.CTkFont(size=10))
        self.status_bar.pack(side=ctk.BOTTOM, fill=ctk.X, padx=10, pady=(0, 5))

        # بارگذاری اولیه لیست دوره‌ها
        self.update_course_list_display()

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_rescan_button_click(self):
        if self.app_logic.current_course:
            self.app_logic.rescan_current_course()
        else:
            self.show_status_message("لطفا ابتدا یک دوره را برای بازاسکن انتخاب یا بارگذاری کنید.", "warning")

    def update_course_list_display(self):
        # پاک کردن لیست قبلی
        for widget in self.course_listbox.winfo_children():
            widget.destroy()
        # self.course_list_items.clear()

        courses = self.app_logic.get_all_courses()
        if not courses:
            ctk.CTkLabel(self.course_listbox, text="هیچ دوره‌ای یافت نشد.").pack(pady=5)
            return

        for course in courses:
            course_frame = ctk.CTkFrame(self.course_listbox)  # فریم برای هر دوره
            course_frame.pack(fill=ctk.X, pady=2, padx=2)

            btn_text = f"{course.name}"
            if self.app_logic.current_course and self.app_logic.current_course.id == course.id:
                btn_text += " (فعلی)"

            btn = ctk.CTkButton(
                course_frame,
                text=btn_text,
                # anchor="w", # برای چپ چین کردن متن دکمه
                command=lambda c_id=course.id: self.app_logic.load_course_by_id(c_id)
            )
            btn.pack(side=ctk.LEFT, fill=ctk.X, expand=True, padx=(0, 2))
            # self.course_list_items[course.id] = btn

            del_btn = ctk.CTkButton(
                course_frame,
                text="X",
                width=30,
                fg_color="red", hover_color="darkred",
                command=lambda c_id=course.id, c_name=course.name: self.confirm_delete_course(c_id, c_name)
            )
            del_btn.pack(side=ctk.RIGHT)

    def confirm_delete_course(self, course_id, course_name):
        if messagebox.askyesno("تایید حذف", f"آیا از حذف دوره '{course_name}' مطمئن هستید؟ این عمل قابل بازگشت نیست."):
            self.app_logic.delete_course(course_id)

    def display_course_info_in_treeview(self, course):
        # پاک کردن Treeview قبلی
        for item in self.tree.get_children():
            self.tree.delete(item)

        if not course:
            self.lbl_course_title.configure(text="هیچ دوره‌ای انتخاب نشده")
            self.lbl_course_duration.configure(text="")
            return

        self.lbl_course_title.configure(text=f"دوره: {course.name}")
        total_hours = course.total_duration_seconds / 3600
        total_minutes = (course.total_duration_seconds % 3600) / 60
        self.lbl_course_duration.configure(text=f"مجموع زمان کل دوره: {total_hours:.0f} ساعت و {total_minutes:.0f} دقیقه")

        course_node_id = f"course_{course.id}"
        self.tree.insert("", "end", iid=course_node_id, text=f"{course.name} (کل دوره)", values=(f"{total_hours:.0f}س {total_minutes:.0f}د", ""), open=True)

        for chapter in course.chapters:  # قبلا باید توسط SQLAlchemy مرتب شده باشند
            chap_hours = chapter.total_duration_seconds / 3600
            chap_minutes = (chapter.total_duration_seconds % 3600) / 60
            chap_seconds = chapter.total_duration_seconds % 60

            chapter_node_id = f"chap_{chapter.id}"
            self.tree.insert(course_node_id, "end", iid=chapter_node_id,
                             text=f"فصل {chapter.order_in_course}: {chapter.name}",
                             values=(f"{chap_minutes:.0f}د {chap_seconds:.0f}ث", ""), open=True)

            for video in chapter.videos:  # قبلا باید توسط SQLAlchemy مرتب شده باشند
                vid_minutes = video.duration_seconds / 60
                vid_seconds = video.duration_seconds % 60
                status_text_map = {
                    WatchedStatusEnum.UNWATCHED: "دیده نشده",
                    WatchedStatusEnum.PARTIALLY_WATCHED: f"تا {video.watched_seconds / 60:.1f}د دیده شده",
                    WatchedStatusEnum.WATCHED: "کامل دیده شده"
                }
                status_display = status_text_map[video.watched_status]
                video_node_id = f"vid_{video.id}"
                self.tree.insert(chapter_node_id, "end", iid=video_node_id,
                                 text=f"  {video.order_in_chapter}. {video.name}",
                                 values=(f"{vid_minutes:.0f}د {vid_seconds:.0f}ث", status_display))
        self.update_course_list_display()  # برای به‌روز کردن "(فعلی)" در لیست

    def _toggle_partial_entry_callback(self, var_name, index, mode, status_var, lbl_partial_time, entry_partial_time):
        """Callback for status_var trace to toggle partial time entry."""
        # var_name, index, mode are provided by Tkinter trace, but we don't need them here.
        # We pass status_var, lbl_partial_time, entry_partial_time explicitly.
        if status_var.get() == WatchedStatusEnum.PARTIALLY_WATCHED.value:
            lbl_partial_time.pack(side=ctk.LEFT, padx=(0,5))
            entry_partial_time.pack(side=ctk.LEFT)
        else:
            lbl_partial_time.pack_forget()
            entry_partial_time.pack_forget()

    def on_treeview_double_click(self, event):
        item_id = self.tree.focus()  # آیتمی که فوکوس شده (انتخاب شده)
        if not item_id or not item_id.startswith("vid_"):
            return  # فقط برای ویدیوها عمل می‌کند

        video_id_str = item_id
        # استخراج وضعیت فعلی و وضعیت بعدی
        current_status_str = self.tree.item(item_id, "values")[1]
        video = self.app_logic.db_session.query(Video).filter_by(id=int(item_id.replace("vid_", ""))).first()  # Video از database.py
        if not video:
            return

        current_status_enum = video.watched_status

        # پنجره کوچک برای انتخاب وضعیت جدید
        new_status_window = ctk.CTkToplevel(self)
        new_status_window.title("تغییر وضعیت مشاهده")
        new_status_window.geometry("300x200")
        new_status_window.transient(self)  # روی پنجره اصلی نمایش داده شود
        new_status_window.grab_set()  # مودال

        ctk.CTkLabel(new_status_window, text=f"تغییر وضعیت برای: {video.name}").pack(pady=10)

        status_var = ctk.StringVar(value=current_status_enum.value)

        rb_unwatched = ctk.CTkRadioButton(new_status_window, text="دیده نشده", variable=status_var, value=WatchedStatusEnum.UNWATCHED.value)
        rb_unwatched.pack(anchor=ctk.W, padx=20, pady=2)

        rb_partially = ctk.CTkRadioButton(new_status_window, text="بخشی دیده شده", variable=status_var, value=WatchedStatusEnum.PARTIALLY_WATCHED.value)
        rb_partially.pack(anchor=ctk.W, padx=20, pady=2)

        # فیلد برای وارد کردن زمان مشاهده شده (فقط اگر بخشی دیده شده انتخاب شود)
        partial_frame = ctk.CTkFrame(new_status_window, fg_color="transparent")
        partial_frame.pack(anchor=ctk.W, padx=40, pady=2)
        lbl_partial_time = ctk.CTkLabel(partial_frame, text="زمان مشاهده شده (ثانیه):")
        entry_partial_time = ctk.CTkEntry(partial_frame, width=60)
        entry_partial_time.insert(0, str(int(video.watched_seconds if video.watched_status == WatchedStatusEnum.PARTIALLY_WATCHED else 0)))

        def toggle_partial_entry():
            if status_var.get() == WatchedStatusEnum.PARTIALLY_WATCHED.value:
                lbl_partial_time.pack(side=ctk.LEFT, padx=(0, 5))
                entry_partial_time.pack(side=ctk.LEFT)
            else:
                lbl_partial_time.pack_forget()
                entry_partial_time.pack_forget()

        status_var.trace_add(
            "write",
            lambda name, index, mode: self._toggle_partial_entry_callback(
                name, index, mode, status_var, lbl_partial_time, entry_partial_time
            )
        )

        # Initial call to set the state correctly
        self._toggle_partial_entry_callback(None, None, None, status_var, lbl_partial_time, entry_partial_time)
        toggle_partial_entry()  # فراخوانی اولیه

        rb_watched = ctk.CTkRadioButton(new_status_window, text="کامل دیده شده", variable=status_var, value=WatchedStatusEnum.WATCHED.value)
        rb_watched.pack(anchor=ctk.W, padx=20, pady=2)

        def apply_status_change():
            new_status_val = status_var.get()
            watched_seconds_val = "0"
            if new_status_val == WatchedStatusEnum.PARTIALLY_WATCHED.value:
                watched_seconds_val = entry_partial_time.get()
                if not watched_seconds_val.isdigit() or not (0 <= int(watched_seconds_val) <= video.duration_seconds):
                    messagebox.showerror("خطا", "زمان مشاهده شده باید یک عدد صحیح بین 0 و مدت زمان ویدیو باشد.", parent=new_status_window)
                    return

            self.app_logic.update_video_progress(video_id_str, new_status_val, watched_seconds_val)
            new_status_window.destroy()

        btn_ok = ctk.CTkButton(new_status_window, text="تایید", command=apply_status_change)
        btn_ok.pack(pady=10)

    def generate_schedule_display(self):
        num_days = self.entry_num_days.get()
        max_hours = self.entry_max_daily_hours.get()

        schedule_data = self.app_logic.generate_schedule(num_days, max_hours)

        self.schedule_display_textbox.configure(state=ctk.NORMAL)
        self.schedule_display_textbox.delete("1.0", ctk.END)

        if not schedule_data:
            self.schedule_display_textbox.insert(ctk.END, "برنامه‌ای برای نمایش وجود ندارد یا خطایی رخ داده است.")
        else:
            full_schedule_text = ""
            for day_plan in schedule_data:
                full_schedule_text += f"\n--- روز {day_plan['day']} (مجموع زمان: {day_plan['total_time_minutes']:.2f} دقیقه) ---\n"
                for task_text in day_plan['tasks_text']:
                    full_schedule_text += f"  - {task_text}\n"
            self.schedule_display_textbox.insert(ctk.END, full_schedule_text.strip())

        self.schedule_display_textbox.configure(state=ctk.DISABLED)
        self.tab_view.set("برنامه مشاهده")  # رفتن به تب برنامه

    def show_status_message(self, message, msg_type="info"):
        self.status_bar.configure(text=message)
        # می‌توانید رنگ نوار وضعیت را بر اساس نوع پیام تغییر دهید
        # if msg_type == "error": self.status_bar.configure(text_color="red")
        # elif msg_type == "warning": self.status_bar.configure(text_color="orange")
        # else: self.status_bar.configure(text_color=ctk.ThemeManager.theme["CTkLabel"]["text_color"])
        print(f"[{msg_type.upper()}]: {message}")

    def on_closing(self):
        self.app_logic.close_db_session()
        self.destroy()


if __name__ == "__main__":
    create_db_and_tables()  # ایجاد جداول پایگاه داده در صورت عدم وجود
    app_logic_instance = VideoSchedulerAppLogic()
    gui_app = VideoSchedulerGUI(app_logic_instance)
    gui_app.mainloop()
