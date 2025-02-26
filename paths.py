import os
import sys

if getattr(sys, 'frozen', False):  # Kiểm tra nếu chương trình chạy từ PyInstaller
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
TASK_FILE = os.path.join(BASE_DIR, "tasks.json")
FILE_ATTRIBUTE_HIDDEN = 0x2