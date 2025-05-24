import os
import json
from tkinter import *
from tkinter import filedialog, messagebox, ttk
from moviepy import VideoFileClip

PROGRESS_FILE = "progress.json"


def get_video_duration(file_path):
    try:
        clip = VideoFileClip(file_path)
        duration = clip.duration / 60  # minutes
        clip.close()
        return duration
    except Exception as e:
        print(f"خطا در خواندن فایل: {file_path} -> {e}")
        return 0


def scan_directory(path):
    course = {}
    for root_dir, dirs, files in os.walk(path):
        folder = os.path.basename(root_dir)
        videos = [f for f in files if f.lower().endswith(('.mp4', '.mkv', '.avi'))]
        if videos:
            course[folder] = []
            for video in videos:
                full_path = os.path.join(root_dir, video)
                duration = get_video_duration(full_path)
                course[folder].append({
                    'name': video,
                    'path': full_path,
                    'duration': round(duration, 2),
                    'watched': False
                })
    return course


class CoursePlanner:
    def __init__(self, root):
        self.root = root
        self.root.title("برنامه‌ریزی کورس ویدیوها")
        self.course_data = {}
        self.tree = None
        self.progress_label = None

        self.days_entry = None
        self.daily_limit_entry = None

        self.load_ui()

    def load_ui(self):
        frame = Frame(self.root)
        frame.pack(padx=10, pady=10)

        Button(frame, text="انتخاب مسیر کورس", command=self.select_folder).grid(row=0, column=0, padx=5)
        self.progress_label = Label(frame, text="پیشرفت: 0%")
        self.progress_label.grid(row=0, column=1)

        Label(frame, text="تعداد روزها:").grid(row=1, column=0)
        self.days_entry = Entry(frame)
        self.days_entry.grid(row=1, column=1)

        Label(frame, text="حداکثر دقیقه در روز:").grid(row=2, column=0)
        self.daily_limit_entry = Entry(frame)
        self.daily_limit_entry.grid(row=2, column=1)

        Button(frame, text="محاسبه برنامه‌ریزی", command=self.calculate_schedule).grid(row=3, column=0, columnspan=2, pady=5)

        self.tree = ttk.Treeview(self.root, columns=("duration", "watched"), show='tree headings')
        self.tree.heading("#0", text="ویدیوها")
        self.tree.heading("duration", text="مدت (دقیقه)")
        self.tree.heading("watched", text="وضعیت")
        self.tree.pack(fill=BOTH, expand=True)

        self.tree.bind("<Double-1>", self.toggle_watched)

    def select_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.course_data = scan_directory(folder)
            self.load_progress()
            self.populate_tree()

    def populate_tree(self):
        self.tree.delete(*self.tree.get_children())
        for chapter, videos in self.course_data.items():
            chapter_node = self.tree.insert('', 'end', text=chapter, open=True)
            for video in videos:
                watched_str = "✅" if video["watched"] else "❌"
                self.tree.insert(chapter_node, 'end', text=video["name"],
                                 values=(video["duration"], watched_str))
        self.update_progress_label()

    def toggle_watched(self, event):
        item_id = self.tree.focus()
        item = self.tree.item(item_id)
        parent = self.tree.parent(item_id)

        if not parent:
            return  # فقط ویدیو قابل انتخاب است

        chapter = self.tree.item(parent)['text']
        video_name = item['text']

        for video in self.course_data[chapter]:
            if video['name'] == video_name:
                video['watched'] = not video['watched']
                break

        self.populate_tree()
        self.save_progress()

    def calculate_schedule(self):
        try:
            total_duration = sum(video["duration"]
                                 for videos in self.course_data.values()
                                 for video in videos)
            days = int(self.days_entry.get())
            limit = int(self.daily_limit_entry.get())

            if limit * days < total_duration:
                messagebox.showwarning("هشدار", "مجموع زمان روزانه برای تکمیل کورس کافی نیست!")
                return

            msg = f"مجموع زمان کورس: {round(total_duration, 2)} دقیقه\nبرای اتمام در {days} روز با حداکثر {limit} دقیقه در روز مشکلی نیست."
            messagebox.showinfo("برنامه‌ریزی موفق", msg)
        except Exception as e:
            messagebox.showerror("خطا", f"ورودی‌ها را بررسی کن!\n{e}")

    def save_progress(self):
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.course_data, f, ensure_ascii=False, indent=2)

    def load_progress(self):
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
                for chapter in self.course_data:
                    for video in self.course_data[chapter]:
                        for saved_video in saved_data.get(chapter, []):
                            if video['name'] == saved_video['name']:
                                video['watched'] = saved_video.get('watched', False)

    def update_progress_label(self):
        total = 0
        watched = 0
        for videos in self.course_data.values():
            for video in videos:
                total += 1
                if video['watched']:
                    watched += 1
        percent = round((watched / total) * 100, 1) if total else 0
        self.progress_label.config(text=f"پیشرفت: {percent}%")


if __name__ == "__main__":
    root = Tk()
    app = CoursePlanner(root)
    root.mainloop()
