from tkinter import ttk, messagebox

import customtkinter as ctk

from database import WatchedStatusEnum, Video


class VideoSchedulerGUI(ctk.CTk):
    def __init__(self, app_logic_instance):
        super().__init__()
        self.app_logic = app_logic_instance

        self.title("Video Course Scheduler")
        self.geometry("1100x750")  # Slightly wider for English text
        ctk.set_appearance_mode("System")  # Options: "System", "Dark", "Light"
        ctk.set_default_color_theme("blue")  # Options: "blue", "green", "dark-blue"

        # Register GUI update callbacks with the app logic
        self.app_logic.register_gui_callbacks(
            display_course_info=self.display_course_info_in_treeview,
            show_message=self.show_status_message,
            update_course_list_display=self.update_course_list_display
        )

        # --- Main container frame ---
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill=ctk.BOTH, expand=True, padx=10, pady=10)

        # --- Left panel: Course Management ---
        courses_management_frame = ctk.CTkFrame(main_frame, width=300)  # Fixed width for left panel
        courses_management_frame.pack(side=ctk.LEFT, fill=ctk.Y, padx=(0, 5), pady=0)
        courses_management_frame.pack_propagate(False)  # Prevent frame from shrinking to content

        ctk.CTkLabel(courses_management_frame, text="My Courses", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10, padx=10)

        self.course_listbox_frame = ctk.CTkScrollableFrame(courses_management_frame, label_text="")  # For the list of courses
        self.course_listbox_frame.pack(fill=ctk.BOTH, expand=True, padx=5, pady=(0, 5))

        btn_add_course = ctk.CTkButton(courses_management_frame, text="Add/Load New Course", command=self.app_logic.select_and_load_course)
        btn_add_course.pack(pady=(10, 5), fill=ctk.X, padx=5)

        btn_rescan_course = ctk.CTkButton(courses_management_frame, text="Rescan Current Course", command=self.on_rescan_button_click)
        btn_rescan_course.pack(pady=5, fill=ctk.X, padx=5)

        # --- Right panel: Course Details and Scheduling ---
        details_and_schedule_frame = ctk.CTkFrame(main_frame)
        details_and_schedule_frame.pack(side=ctk.LEFT, fill=ctk.BOTH, expand=True)  # Takes remaining space

        # Tab view for details and schedule
        self.tab_view = ctk.CTkTabview(details_and_schedule_frame)
        self.tab_view.pack(fill=ctk.BOTH, expand=True, padx=5, pady=5)
        self.tab_view.add("Course Details")
        self.tab_view.add("Viewing Schedule")
        self.tab_view.set("Course Details")  # Default tab

        # --- Tab 1: Course Details ---
        course_details_tab_content = self.tab_view.tab("Course Details")

        self.lbl_course_title = ctk.CTkLabel(course_details_tab_content, text="No course selected",
                                             font=ctk.CTkFont(size=18, weight="bold"), anchor="w")
        self.lbl_course_title.pack(pady=10, fill=ctk.X, padx=10)

        self.lbl_course_duration = ctk.CTkLabel(course_details_tab_content, text="", anchor="w")
        self.lbl_course_duration.pack(pady=5, fill=ctk.X, padx=10)

        # Treeview for chapters and videos
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", rowheight=25, font=('Segoe UI', 10))  # Using a common Windows font
        style.configure("Treeview.Heading", font=('Segoe UI', 11, 'bold'))

        self.tree = ttk.Treeview(course_details_tab_content, columns=("duration", "status"), selectmode="browse")
        self.tree.heading("#0", text="Item Name (Chapter/Video)", anchor="w")  # LTR anchor
        self.tree.heading("duration", text="Duration", anchor="w")
        self.tree.heading("status", text="Status", anchor="w")

        self.tree.column("#0", width=400, stretch=ctk.YES, anchor="w")  # LTR anchor
        self.tree.column("duration", width=120, anchor="center")  # Center duration
        self.tree.column("status", width=180, anchor="w")  # LTR anchor
        self.tree.pack(fill=ctk.BOTH, expand=True, padx=5, pady=5)
        self.tree.bind("<Double-1>", self.on_treeview_double_click_show_dialog)  # For changing status

        # --- Tab 2: Viewing Schedule ---
        schedule_tab_content = self.tab_view.tab("Viewing Schedule")

        schedule_input_controls_frame = ctk.CTkFrame(schedule_tab_content)
        schedule_input_controls_frame.pack(fill=ctk.X, padx=5, pady=5)

        ctk.CTkLabel(schedule_input_controls_frame, text="Days to complete:").pack(side=ctk.LEFT, padx=(0, 5))
        self.entry_num_days = ctk.CTkEntry(schedule_input_controls_frame, width=50, justify=ctk.LEFT)
        self.entry_num_days.pack(side=ctk.LEFT, padx=(0, 10))
        self.entry_num_days.insert(0, "30")

        ctk.CTkLabel(schedule_input_controls_frame, text="Max daily hours:").pack(side=ctk.LEFT, padx=(0, 5))
        self.entry_max_daily_hours = ctk.CTkEntry(schedule_input_controls_frame, width=50, justify=ctk.LEFT)
        self.entry_max_daily_hours.pack(side=ctk.LEFT, padx=(0, 10))
        self.entry_max_daily_hours.insert(0, "1.0")  # Allow float input

        btn_generate_schedule = ctk.CTkButton(schedule_input_controls_frame, text="Generate Schedule",
                                              command=self.generate_and_display_schedule)
        btn_generate_schedule.pack(side=ctk.LEFT, padx=10)

        self.schedule_display_textbox = ctk.CTkTextbox(schedule_tab_content, wrap=ctk.WORD, state=ctk.DISABLED,
                                                       font=('Segoe UI', 10))
        # For LTR, no special tag needed for basic text alignment, but can be used for styling.
        # If specific lines needed different justification, tags would be useful.
        # self.schedule_display_textbox._textbox.tag_configure("schedule_style", justify="left") # Example
        self.schedule_display_textbox.pack(fill=ctk.BOTH, expand=True, padx=5, pady=5)

        # --- Status Bar ---
        self.status_bar = ctk.CTkLabel(self, text="Ready", anchor=ctk.W, font=ctk.CTkFont(size=10))
        self.status_bar.pack(side=ctk.BOTTOM, fill=ctk.X, padx=10, pady=(0, 5))

        # Initial load of course list
        self.update_course_list_display()
        # Handle window close event
        self.protocol("WM_DELETE_WINDOW", self.on_closing_application)

    def on_rescan_button_click(self):
        """Handles the rescan button click event."""
        if self.app_logic.current_course:
            self.app_logic.rescan_current_course()
        else:
            self.show_status_message("Please select or load a course to rescan.", "warning")

    def update_course_list_display(self):
        """Clears and repopulates the list of courses in the GUI."""
        # Clear previous course list items
        for widget in self.course_listbox_frame.winfo_children():
            widget.destroy()

        courses = self.app_logic.get_all_courses()
        if not courses:
            ctk.CTkLabel(self.course_listbox_frame, text="No courses found.").pack(pady=5, padx=5)
            return

        for course in courses:
            # Frame for each course item (button + delete button)
            course_item_frame = ctk.CTkFrame(self.course_listbox_frame)
            course_item_frame.pack(fill=ctk.X, pady=(2, 0), padx=2)

            course_button_text = f"{course.name}"
            if self.app_logic.current_course and self.app_logic.current_course.id == course.id:
                course_button_text += " (Current)"

            load_course_button = ctk.CTkButton(
                course_item_frame,
                text=course_button_text,
                anchor="w",  # Align text to the left within the button
                command=lambda c_id=course.id: self.app_logic.load_course_by_id(c_id)
            )
            load_course_button.pack(side=ctk.LEFT, fill=ctk.X, expand=True, padx=(0, 2))

            delete_course_button = ctk.CTkButton(
                course_item_frame,
                text="X",
                width=30,
                fg_color="red", hover_color="darkred",  # Styling for delete button
                command=lambda c_id=course.id, c_name=course.name: self.confirm_and_delete_course(c_id, c_name)
            )
            delete_course_button.pack(side=ctk.RIGHT)  # Delete button on the right of the item

    def confirm_and_delete_course(self, course_id, course_name):
        """Shows a confirmation dialog before deleting a course."""
        if messagebox.askyesno("Confirm Deletion",
                               f"Are you sure you want to delete the course '{course_name}'?\n"
                               "This action cannot be undone.",
                               parent=self):  # `parent=self` makes dialog modal to this window
            self.app_logic.delete_course(course_id)

    def display_course_info_in_treeview(self, course_data_object):
        """Displays course, chapter, and video information in the Treeview."""
        # Clear previous Treeview content
        for item in self.tree.get_children():
            self.tree.delete(item)

        if not course_data_object:
            self.lbl_course_title.configure(text="No course selected")
            self.lbl_course_duration.configure(text="")
            return

        self.lbl_course_title.configure(text=f"Course: {course_data_object.name}")
        total_hours = course_data_object.total_duration_seconds / 3600
        total_minutes = (course_data_object.total_duration_seconds % 3600) / 60
        self.lbl_course_duration.configure(text=f"Total Course Duration: {total_hours:.0f}h {total_minutes:.0f}m")

        course_node_id = f"course_{course_data_object.id}"
        self.tree.insert("", "end", iid=course_node_id,
                         text=f"{course_data_object.name} (Full Course)",
                         values=(f"{total_hours:.0f}h {total_minutes:.0f}m", ""), open=True)

        for chapter in course_data_object.chapters:  # Assumes chapters are ordered by relationship
            chap_minutes_total = chapter.total_duration_seconds / 60
            chap_seconds_rem = chapter.total_duration_seconds % 60

            chapter_node_id = f"chap_{chapter.id}"
            self.tree.insert(course_node_id, "end", iid=chapter_node_id,
                             text=f"Chapter {chapter.order_in_course}: {chapter.name}",
                             values=(f"{chap_minutes_total:.0f}m {chap_seconds_rem:.0f}s", ""), open=True)

            for video in chapter.videos:  # Assumes videos are ordered by relationship
                vid_minutes_total = video.duration_seconds / 60
                vid_seconds_rem = video.duration_seconds % 60
                status_text_map = {  # English status texts
                    WatchedStatusEnum.UNWATCHED: "Unwatched",
                    WatchedStatusEnum.PARTIALLY_WATCHED: f"Partial ({video.watched_seconds / 60:.1f}m watched)",
                    WatchedStatusEnum.WATCHED: "Watched"
                }
                status_display_text = status_text_map.get(video.watched_status, "Unknown")
                video_node_id = f"vid_{video.id}"  # Used as iid for treeview item
                self.tree.insert(chapter_node_id, "end", iid=video_node_id,
                                 text=f"  {video.order_in_chapter}. {video.name}",  # Indent video names
                                 values=(f"{vid_minutes_total:.0f}m {vid_seconds_rem:.0f}s", status_display_text))

        self.update_course_list_display()  # To update "(Current)" course indicator

    @staticmethod
    def _toggle_partial_entry_callback(status_variable, label_widget, entry_widget):
        """Callback for status_var trace to show/hide partial time entry field."""
        # This function is called by Tkinter's trace mechanism.
        # We only care about the value of status_variable.
        if status_variable.get() == WatchedStatusEnum.PARTIALLY_WATCHED.value:
            label_widget.pack(side=ctk.LEFT, padx=(0, 5))  # Label on the left
            entry_widget.pack(side=ctk.LEFT)  # Entry on the right of the label
        else:
            label_widget.pack_forget()
            entry_widget.pack_forget()

    def on_treeview_double_click_show_dialog(self, event):
        """Handles double-click on a video item in Treeview to change its status."""
        selected_item_id = self.tree.focus()  # Get the iid of the focused item
        if not selected_item_id or not selected_item_id.startswith("vid_"):
            return  # Action only for video items

        video_id_numeric = int(selected_item_id.replace("vid_", ""))

        # Fetch video details from database (using app_logic's session)
        # `Video` model needs to be imported at the top of main.py for this direct query
        video_object = self.app_logic.db_session.query(Video).filter_by(id=video_id_numeric).first()

        if not video_object:
            self.show_status_message(f"Error: Video with ID {video_id_numeric} not found in database.", "error")
            return

        # Create a Toplevel window for status update
        status_dialog = ctk.CTkToplevel(self)
        status_dialog.title("Update Video Status")
        status_dialog.geometry("380x250")  # Adjusted size for English text
        status_dialog.transient(self)  # Keep dialog on top of the main window
        status_dialog.grab_set()  # Make dialog modal

        dialog_content_frame = ctk.CTkFrame(status_dialog, fg_color="transparent")
        dialog_content_frame.pack(fill=ctk.BOTH, expand=True, padx=15, pady=10)

        ctk.CTkLabel(dialog_content_frame, text=f"Update status for:\n{video_object.name}",
                     anchor="w", justify=ctk.LEFT).pack(fill=ctk.X, pady=(0, 10))

        current_status_string_var = ctk.StringVar(value=video_object.watched_status.value)

        radiobutton_frame = ctk.CTkFrame(dialog_content_frame, fg_color="transparent")
        radiobutton_frame.pack(fill=ctk.X)

        ctk.CTkRadioButton(radiobutton_frame, text="Unwatched", variable=current_status_string_var,
                           value=WatchedStatusEnum.UNWATCHED.value).pack(anchor=ctk.W, fill=ctk.X, pady=2)

        ctk.CTkRadioButton(radiobutton_frame, text="Partially Watched", variable=current_status_string_var,
                           value=WatchedStatusEnum.PARTIALLY_WATCHED.value).pack(anchor=ctk.W, fill=ctk.X, pady=2)

        # Frame for "Partially Watched" time input
        partial_watch_time_frame = ctk.CTkFrame(radiobutton_frame, fg_color="transparent")
        partial_watch_time_frame.pack(fill=ctk.X, padx=(20, 0))  # Indent this section

        watched_time_seconds_entry = ctk.CTkEntry(partial_watch_time_frame, width=70, justify=ctk.LEFT)
        watched_time_label = ctk.CTkLabel(partial_watch_time_frame, text="Watched (seconds):")

        # Initialize entry and visibility based on current status
        initial_watched_s = int(video_object.watched_seconds) if video_object.watched_status == WatchedStatusEnum.PARTIALLY_WATCHED else 0
        watched_time_seconds_entry.insert(0, str(initial_watched_s))

        # Setup trace and initial call for visibility toggle
        self._toggle_partial_entry_callback(current_status_string_var, watched_time_label, watched_time_seconds_entry)
        current_status_string_var.trace_add(
            "write",
            lambda name, index, mode: self._toggle_partial_entry_callback(current_status_string_var, watched_time_label, watched_time_seconds_entry)
        )

        ctk.CTkRadioButton(radiobutton_frame, text="Watched", variable=current_status_string_var,
                           value=WatchedStatusEnum.WATCHED.value).pack(anchor=ctk.W, fill=ctk.X, pady=2)

        def handle_apply_status_change():
            selected_new_status = current_status_string_var.get()
            input_watched_seconds = "0"  # Default
            if selected_new_status == WatchedStatusEnum.PARTIALLY_WATCHED.value:
                input_watched_seconds = watched_time_seconds_entry.get()
                try:
                    # Validate input for partial watch time
                    ws_float = float(input_watched_seconds.replace(",", "."))
                    if not (0 <= ws_float <= video_object.duration_seconds):
                        messagebox.showerror("Input Error",
                                             f"Watched time must be between 0 and {video_object.duration_seconds:.0f} seconds.",
                                             parent=status_dialog)
                        return
                except ValueError:
                    messagebox.showerror("Input Error", "Watched time must be a valid number.", parent=status_dialog)
                    return

            # Call app_logic to update the database
            self.app_logic.update_video_progress(selected_item_id, selected_new_status, input_watched_seconds)
            status_dialog.destroy()  # Close dialog

        apply_button = ctk.CTkButton(dialog_content_frame, text="Apply Status", command=handle_apply_status_change)
        apply_button.pack(pady=(15, 5))

    def generate_and_display_schedule(self):
        """Gets input, generates schedule via app_logic, and displays it."""
        num_days_input = self.entry_num_days.get()
        max_hours_input = self.entry_max_daily_hours.get()

        schedule_data_list = self.app_logic.generate_schedule(num_days_input, max_hours_input)

        self.schedule_display_textbox.configure(state=ctk.NORMAL)  # Enable editing
        self.schedule_display_textbox.delete("1.0", ctk.END)  # Clear previous content

        if not schedule_data_list:
            self.schedule_display_textbox.insert(ctk.END, "No schedule to display or an error occurred.")
        else:
            full_schedule_display_text = []
            for day_plan_item in schedule_data_list:
                day_header_text = f"\n--- Day {day_plan_item['day']} (Total time: {day_plan_item['total_time_minutes']:.2f} minutes) ---"
                full_schedule_display_text.append(day_header_text)
                for task_item_text in day_plan_item['tasks_text']:
                    full_schedule_display_text.append(f"  - {task_item_text}")  # LTR: Indent with spaces

            final_text_to_show = "\n".join(full_schedule_display_text).strip()
            self.schedule_display_textbox.insert(ctk.END, final_text_to_show)

        self.schedule_display_textbox.configure(state=ctk.DISABLED)  # Disable editing
        self.tab_view.set("Viewing Schedule")  # Switch to the schedule tab

    def show_status_message(self, message_text, message_type="info"):
        """Displays a message in the status bar."""
        self.status_bar.configure(text=message_text)
        # Optionally, change status_bar text color based on message_type
        # if message_type == "error": self.status_bar.configure(text_color="red")
        # elif message_type == "warning": self.status_bar.configure(text_color="orange")
        # else: self.status_bar.configure(text_color=ctk.ThemeManager.theme["CTkLabel"]["text_color"])
        print(f"[{message_type.upper()}]: {message_text}")  # Also print to console

    def on_closing_application(self):
        """Handles cleanup when the application window is closed."""
        self.app_logic.close_db_session()  # Important to close DB session
        self.destroy()  # Close the GUI window
