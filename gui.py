from tkinter import ttk, messagebox
import customtkinter as ctk
import tkinter as tk
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
            update_course_list_display=self.update_course_list_display,
            update_progress=self.update_progress,
            show_progress_dialog=self.show_progress_dialog,
            hide_progress_dialog=self.hide_progress_dialog
        )

        # --- Progress Dialog ---
        self.progress_dialog = None
        self.progress_bar = None
        self.progress_label = None

        # --- Main container frame ---
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill=ctk.BOTH, expand=True, padx=10, pady=10)

        # --- Left panel: Course Management ---
        self.courses_management_frame = ctk.CTkFrame(main_frame)
        self.courses_management_frame.pack(side=ctk.LEFT, fill=ctk.Y, padx=(0, 5), pady=0)
        
        # Add search functionality
        search_frame = ctk.CTkFrame(self.courses_management_frame)
        search_frame.pack(fill=ctk.X, padx=5, pady=5)
        
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.filter_courses)
        
        search_entry = ctk.CTkEntry(search_frame, textvariable=self.search_var, placeholder_text="جستجوی دوره...")
        search_entry.pack(fill=ctk.X, padx=5, pady=5)

        ctk.CTkLabel(self.courses_management_frame, text="My Courses", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10, padx=10)

        # --- Scrollable area using Canvas for both horizontal and vertical scrollbars ---
        canvas_frame = ctk.CTkFrame(self.courses_management_frame)
        canvas_frame.pack(fill=ctk.BOTH, expand=True, padx=5, pady=(0, 5))

        # Create a frame for the canvas and scrollbars
        canvas_container = ctk.CTkFrame(canvas_frame)
        canvas_container.pack(fill=ctk.BOTH, expand=True)

        # Create canvas with both scrollbars
        self.canvas = tk.Canvas(canvas_container, highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scrollbars
        v_scrollbar = ttk.Scrollbar(canvas_container, orient="vertical", command=self.canvas.yview)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        h_scrollbar = ttk.Scrollbar(canvas_frame, orient="horizontal", command=self.canvas.xview)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        self.canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Internal scrollable frame
        self.course_listbox_frame = ctk.CTkFrame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.course_listbox_frame, anchor="nw")

        # Bind mouse wheel events for scrolling
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Shift-MouseWheel>", self._on_shift_mousewheel)
        
        # Bind resize events
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.course_listbox_frame.bind("<Configure>", self._on_frame_configure)

        # Add resize handle
        self.resize_handle = ctk.CTkFrame(self.courses_management_frame, width=5, cursor="size_we")
        self.resize_handle.pack(side=ctk.RIGHT, fill=ctk.Y)
        self.resize_handle.bind("<Button-1>", self._start_resize)
        self.resize_handle.bind("<B1-Motion>", self._on_resize)
        self.resize_handle.bind("<ButtonRelease-1>", self._stop_resize)

        btn_add_course = ctk.CTkButton(self.courses_management_frame, text="Add/Load New Course", command=self.app_logic.select_and_load_course)
        btn_add_course.pack(pady=(10, 5), fill=ctk.X, padx=5)

        btn_rescan_course = ctk.CTkButton(self.courses_management_frame, text="Rescan Current Course", command=self.on_rescan_button_click)
        btn_rescan_course.pack(pady=5, fill=ctk.X, padx=5)

        # --- Right panel: Course Details and Scheduling ---
        self.details_and_schedule_frame = ctk.CTkFrame(main_frame)
        self.details_and_schedule_frame.pack(side=ctk.LEFT, fill=ctk.BOTH, expand=True)  # Takes remaining space

        # Tab view for details and schedule
        self.tab_view = ctk.CTkTabview(self.details_and_schedule_frame)
        self.tab_view.pack(fill=ctk.BOTH, expand=True, padx=5, pady=5)
        self.tab_view.add("Course Details")
        self.tab_view.add("Viewing Schedule")
        self.tab_view.set("Course Details")  # Default tab

        # --- Tab 1: Course Details ---
        course_details_tab_content = self.tab_view.tab("Course Details")

        self._create_course_details_tab(course_details_tab_content)

        # --- Tab 2: Viewing Schedule ---
        schedule_tab_content = self.tab_view.tab("Viewing Schedule")

        self._create_schedule_tab(schedule_tab_content)

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

    def _create_course_details_tab(self, parent):
        """Creates the course details tab."""
        details_frame = ctk.CTkFrame(parent)
        details_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # دکمه‌های Expand/Collapse در یک فریم جداگانه بالای Treeview
        tree_buttons_frame = ctk.CTkFrame(details_frame)
        tree_buttons_frame.pack(fill="x", padx=10, pady=(0, 5))
        
        btn_collapse_all = ctk.CTkButton(
            tree_buttons_frame,
            text="Collapse All",
            width=100,
            command=self.collapse_all_tree_items
        )
        btn_collapse_all.pack(side=ctk.LEFT, padx=(0, 5))
        
        btn_expand_all = ctk.CTkButton(
            tree_buttons_frame,
            text="Expand All",
            width=100,
            command=self.expand_all_tree_items
        )
        btn_expand_all.pack(side=ctk.LEFT)

        # فریم برای Treeview و اسکرول‌بار
        treeview_frame = ctk.CTkFrame(details_frame)
        treeview_frame.pack(fill="both", expand=True, padx=0, pady=0)

        # Treeview برای نمایش ساختار درختی
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", rowheight=25, font=('Segoe UI', 10))
        style.configure("Treeview.Heading", font=('Segoe UI', 11, 'bold'))

        self.tree = ttk.Treeview(treeview_frame, columns=("duration", "status"), selectmode="browse")
        self.tree.heading("#0", text="Item Name (Chapter/Video)", anchor="w")
        self.tree.heading("duration", text="Duration", anchor="w")
        self.tree.heading("status", text="Status", anchor="w")
        self.tree.column("#0", width=400, stretch=ctk.YES, anchor="w")
        self.tree.column("duration", width=120, anchor="center")
        self.tree.column("status", width=180, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.tree.bind("<Double-1>", self.on_treeview_double_click_show_dialog)

        # اسکرول‌بار عمودی
        tree_scrollbar = ttk.Scrollbar(treeview_frame, orient="vertical", command=self.tree.yview)
        tree_scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=tree_scrollbar.set)

    def display_course_info_in_treeview(self, course):
        """Displays course information in the Treeview."""
        # Clear previous content
        for item in self.tree.get_children():
            self.tree.delete(item)

        if course is None:
            self.tree.insert("", "end", text="No course selected", values=("", ""))
            return

        # Course title and duration
        self.tree.insert("", "end", iid="course_title", text=f"Course: {course.name}", values=("", ""))
        total_duration = sum(ch.total_duration_seconds for ch in course.chapters)
        self.tree.insert("", "end", iid="course_duration", text=f"Total Duration: {self._format_time(total_duration)}", values=("", ""))

        # Sort chapters by order
        sorted_chapters = sorted(course.chapters, key=lambda x: x.order_in_course)

        for chapter in sorted_chapters:
            chapter_id = f"chapter_{chapter.id}"
            chapter_text = f"Chapter {chapter.order_in_course:02d}: {chapter.name}"
            chapter_node = self.tree.insert("", "end", iid=chapter_id, text=chapter_text, values=(self._format_time(chapter.total_duration_seconds), ""))
            for video in chapter.videos:
                video_id = f"vid_{video.id}"
                status = video.watched_status.value
                if video.watched_status != WatchedStatusEnum.WATCHED:
                    progress = (video.watched_seconds / video.duration_seconds) * 100 if video.duration_seconds else 0
                    status += f" ({progress:.1f}%)"
                self.tree.insert(chapter_id, "end", iid=video_id, text=video.name, values=(self._format_time(video.duration_seconds), status))

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

    def _create_schedule_tab(self, parent):
        """Creates the Viewing Schedule tab."""
        schedule_frame = ctk.CTkFrame(parent)
        schedule_frame.pack(fill="both", expand=True, padx=10, pady=10)
        schedule_frame.grid_propagate(False)
        schedule_frame.pack_propagate(False)
        schedule_frame.configure(width=900, height=600)
        schedule_frame.grid_rowconfigure(1, weight=1)
        schedule_frame.grid_columnconfigure(0, weight=1)

        # Controls frame with grid layout (no extra columns)
        controls_frame = ctk.CTkFrame(schedule_frame)
        controls_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 5))
        for i in range(6):
            controls_frame.grid_columnconfigure(i, weight=0)
        controls_frame.grid_columnconfigure(5, weight=1)

        # Days input
        days_label = ctk.CTkLabel(controls_frame, text="Days to complete:")
        days_label.grid(row=0, column=0, sticky="w", padx=(5, 2), pady=5)
        self.days_entry = ctk.CTkEntry(controls_frame, width=80)
        self.days_entry.grid(row=0, column=1, sticky="w", padx=(0, 10), pady=5)
        self.days_entry.insert(0, "30")
        self.days_entry.configure(font=ctk.CTkFont(size=13))

        # Max daily minutes input
        minutes_label = ctk.CTkLabel(controls_frame, text="Max daily minutes:")
        minutes_label.grid(row=0, column=2, sticky="w", padx=(5, 2), pady=5)
        self.minutes_entry = ctk.CTkEntry(controls_frame, width=80)
        self.minutes_entry.grid(row=0, column=3, sticky="w", padx=(0, 10), pady=5)
        self.minutes_entry.insert(0, "60")
        self.minutes_entry.configure(font=ctk.CTkFont(size=13))

        # Generate button
        generate_button = ctk.CTkButton(
            controls_frame,
            text="Generate Schedule",
            width=140,
            height=36,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self.generate_and_display_schedule
        )
        generate_button.grid(row=0, column=4, sticky="w", padx=(0, 5), pady=5)

        # Save button
        save_button = ctk.CTkButton(
            controls_frame,
            text="Save Schedule",
            width=140,
            height=36,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self.save_schedule_to_db
        )
        save_button.grid(row=0, column=5, sticky="w", padx=(0, 5), pady=5)

        # Schedule display directly in the main frame (no extra box)
        schedule_display_container = ctk.CTkFrame(schedule_frame)
        schedule_display_container.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        schedule_display_container.grid_rowconfigure(0, weight=1)
        schedule_display_container.grid_columnconfigure(0, weight=1)

        self.schedule_canvas = ctk.CTkCanvas(schedule_display_container)
        self.schedule_scrollbar = ctk.CTkScrollbar(schedule_display_container, orientation="vertical",
                                                 command=self.schedule_canvas.yview)
        self.schedule_scrollable_frame = ctk.CTkFrame(self.schedule_canvas)

        self.schedule_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.schedule_canvas.configure(
                scrollregion=self.schedule_canvas.bbox("all")
            )
        )
        self.schedule_canvas.create_window((0, 0), window=self.schedule_scrollable_frame, anchor="nw")
        self.schedule_canvas.configure(yscrollcommand=self.schedule_scrollbar.set)

        self.schedule_canvas.grid(row=0, column=0, sticky="nsew")
        self.schedule_scrollbar.grid(row=0, column=1, sticky="ns")

        self.schedule_canvas.bind_all("<MouseWheel>", self._on_schedule_mousewheel)
        self.schedule_canvas.bind_all("<Shift-MouseWheel>", self._on_schedule_shift_mousewheel)

        # Variable to hold the generated schedule
        self.generated_schedule = None

    def generate_and_display_schedule(self):
        """Generate and display the schedule (without saving)."""
        # Clear previous schedule
        for widget in self.schedule_scrollable_frame.winfo_children():
            widget.destroy()

        num_days = self.days_entry.get()
        max_daily_minutes = self.minutes_entry.get()

        # Only generate schedule (do not save)
        schedule = self.app_logic.generate_schedule(num_days, max_daily_minutes)
        self.generated_schedule = schedule

        if not schedule:
            return

        for day_plan in schedule:
            day_frame = ctk.CTkFrame(self.schedule_scrollable_frame)
            day_frame.pack(fill="x", padx=5, pady=5)

            day_label = ctk.CTkLabel(
                day_frame,
                text=f"Day {day_plan['day']} - Total Time: {day_plan['total_time_minutes']:.1f} minutes",
                font=("Arial", 14, "bold")
            )
            day_label.pack(fill="x", padx=5, pady=5)

            for task in day_plan['tasks']:
                task_frame = ctk.CTkFrame(day_frame)
                task_frame.pack(fill="x", padx=10, pady=2)

                start_time = self._format_time(task['start_time'])
                end_time = self._format_time(task['end_time'])
                duration = self._format_time(task['duration'])

                task_text = f"{task['chapter_name']} - {task['video_name']}\n"
                task_text += f"Time: {start_time} to {end_time} (Duration: {duration})"

                task_label = ctk.CTkLabel(task_frame, text=task_text, justify="left")
                task_label.pack(fill="x", padx=5, pady=2)

    def save_schedule_to_db(self):
        """Save the generated schedule to the database."""
        if not self.generated_schedule:
            self.show_status_message("Please generate the schedule first.", "warning")
            return
        num_days = self.days_entry.get()
        max_daily_minutes = self.minutes_entry.get()
        result = self.app_logic.save_schedule(self.generated_schedule, num_days, max_daily_minutes)
        if result:
            self.show_status_message("Schedule saved successfully.", "info")
        else:
            self.show_status_message("Error saving schedule!", "error")

    def _on_schedule_mousewheel(self, event):
        """Handle mouse wheel scrolling for schedule."""
        if self.schedule_canvas.winfo_height() < self.schedule_scrollable_frame.winfo_height():
            self.schedule_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_schedule_shift_mousewheel(self, event):
        """Handle shift+mouse wheel scrolling for schedule."""
        if self.schedule_canvas.winfo_width() < self.schedule_scrollable_frame.winfo_width():
            self.schedule_canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")

    def _format_time(self, seconds):
        """Formats time in seconds to HH:MM:SS format."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

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

    def _on_mousewheel(self, event):
        """Handle vertical scrolling with mouse wheel"""
        # Only scroll if the content is larger than the visible area
        if self.canvas.winfo_height() < self.course_listbox_frame.winfo_height():
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_shift_mousewheel(self, event):
        """Handle horizontal scrolling with Shift + mouse wheel"""
        # Only scroll if the content is wider than the visible area
        if self.canvas.winfo_width() < self.course_listbox_frame.winfo_width():
            self.canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_canvas_configure(self, event):
        """Update the width of the internal frame when canvas is resized"""
        self.canvas.itemconfig(self.canvas_window, width=event.width)
        # Update scroll region after resize
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_frame_configure(self, event):
        """Update the scroll region when the internal frame changes size"""
        # Update scroll region
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        # Show/hide scrollbars based on content size
        if self.canvas.winfo_height() >= self.course_listbox_frame.winfo_height():
            self.canvas.yview_moveto(0)  # Reset vertical scroll position
        if self.canvas.winfo_width() >= self.course_listbox_frame.winfo_width():
            self.canvas.xview_moveto(0)  # Reset horizontal scroll position

    def _start_resize(self, event):
        """Start the resize operation"""
        self.resize_start_x = event.x_root
        self.resize_start_width = self.courses_management_frame.winfo_width()

    def _on_resize(self, event):
        """Handle the resize operation"""
        delta = event.x_root - self.resize_start_x
        new_width = max(200, self.resize_start_width + delta)  # Minimum width of 200
        self.courses_management_frame.configure(width=new_width)

    def _stop_resize(self, event):
        """Stop the resize operation"""
        pass

    def filter_courses(self, *args):
        """Filter courses based on search text"""
        search_text = self.search_var.get().lower()
        
        # Clear previous course list items
        for widget in self.course_listbox_frame.winfo_children():
            widget.destroy()

        courses = self.app_logic.get_all_courses()
        if not courses:
            ctk.CTkLabel(self.course_listbox_frame, text="No courses found.").pack(pady=5, padx=5)
            return

        for course in courses:
            if search_text in course.name.lower():
                # Frame for each course item (button + delete button)
                course_item_frame = ctk.CTkFrame(self.course_listbox_frame)
                course_item_frame.pack(fill=ctk.X, pady=(2, 0), padx=2)

                course_button_text = f"{course.name}"
                if self.app_logic.current_course and self.app_logic.current_course.id == course.id:
                    course_button_text += " (Current)"

                load_course_button = ctk.CTkButton(
                    course_item_frame,
                    text=course_button_text,
                    anchor="w",
                    command=lambda c_id=course.id: self.app_logic.load_course_by_id(c_id)
                )
                load_course_button.pack(side=ctk.LEFT, fill=ctk.X, expand=True, padx=(0, 2))

                delete_course_button = ctk.CTkButton(
                    course_item_frame,
                    text="X",
                    width=30,
                    fg_color="red",
                    hover_color="darkred",
                    command=lambda c_id=course.id, c_name=course.name: self.confirm_and_delete_course(c_id, c_name)
                )
                delete_course_button.pack(side=ctk.RIGHT)

    def show_progress_dialog(self, title="Processing..."):
        """Shows the progress dialog"""
        if self.progress_dialog is None:
            self.progress_dialog = ctk.CTkToplevel(self)
            self.progress_dialog.title(title)
            self.progress_dialog.geometry("400x150")
            self.progress_dialog.transient(self)
            self.progress_dialog.grab_set()
            
            # Center window
            self.progress_dialog.update_idletasks()
            width = self.progress_dialog.winfo_width()
            height = self.progress_dialog.winfo_height()
            x = (self.progress_dialog.winfo_screenwidth() // 2) - (width // 2)
            y = (self.progress_dialog.winfo_screenheight() // 2) - (height // 2)
            self.progress_dialog.geometry(f'{width}x{height}+{x}+{y}')
            
            # Disable window buttons
            self.progress_dialog.protocol("WM_DELETE_WINDOW", lambda: None)
            
            # Add progress bar
            self.progress_label = ctk.CTkLabel(self.progress_dialog, text="Scanning files...", font=ctk.CTkFont(size=12))
            self.progress_label.pack(pady=(20, 10))
            
            self.progress_bar = ctk.CTkProgressBar(self.progress_dialog, width=350)
            self.progress_bar.pack(pady=10, padx=20)
            self.progress_bar.set(0)
            
            # Disable interaction with main window
            self.progress_dialog.focus_set()
            self.progress_dialog.grab_set()
            
            # Force update
            self.progress_dialog.update()

    def hide_progress_dialog(self):
        """Hides the progress dialog"""
        if self.progress_dialog is not None:
            self.progress_dialog.destroy()
            self.progress_dialog = None
            self.progress_bar = None
            self.progress_label = None
            # Force update
            self.update()

    def update_progress(self, value, text=None):
        """Updates the progress bar value and text"""
        if self.progress_bar is not None:
            self.progress_bar.set(value)
        if text and self.progress_label is not None:
            self.progress_label.configure(text=text)
        # Force update
        if self.progress_dialog is not None:
            self.progress_dialog.update()

    def collapse_all_tree_items(self):
        """Collapses all items in the treeview"""
        for item in self.tree.get_children():
            self.tree.item(item, open=False)
            # Also collapse all children recursively
            self._collapse_children(item)

    def _collapse_children(self, parent):
        """Recursively collapses all children of a tree item"""
        for child in self.tree.get_children(parent):
            self.tree.item(child, open=False)
            self._collapse_children(child)

    def expand_all_tree_items(self):
        """Expands all items in the treeview"""
        for item in self.tree.get_children():
            self.tree.item(item, open=True)
            # Also expand all children recursively
            self._expand_children(item)

    def _expand_children(self, parent):
        """Recursively expands all children of a tree item"""
        for child in self.tree.get_children(parent):
            self.tree.item(child, open=True)
            self._expand_children(child)
