from app_logic import VideoSchedulerAppLogic
from database import create_db_and_tables
from gui import VideoSchedulerGUI

if __name__ == "__main__":
    create_db_and_tables()  # Ensure database and tables exist on startup

    app_logic_instance = VideoSchedulerAppLogic()
    gui_application = VideoSchedulerGUI(app_logic_instance)
    gui_application.mainloop()
