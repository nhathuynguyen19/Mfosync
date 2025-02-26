import os
import json
from paths import TASK_FILE, FILE_ATTRIBUTE_HIDDEN
import ctypes
import tkinter as tk
from tkinter import filedialog
import time
import psutil
import win32file

def load_tasks():
    if not os.path.exists(TASK_FILE):
        with open(TASK_FILE, "w", encoding='utf-8') as file:
            json.dump([], file)  # Tạo file trống với danh sách rỗng []
        print(f"📁 Đã tạo {TASK_FILE} vì không tìm thấy.")

    with open(TASK_FILE, "r", encoding='utf-8') as file:
        return json.load(file)

def save_tasks(tasks):
    """Lưu danh sách tiến trình vào file JSON"""
    with open(TASK_FILE, "w", encoding='utf-8') as f:
        json.dump(tasks, f, indent=4)

def get_drive_uuid(path):
    """Lấy UUID của ổ đĩa từ đường dẫn trên Windows"""
    drive = os.path.splitdrive(path)[0]  # Lấy ký tự ổ đĩa (D:, E:, ...)
    if not drive:
        return None  # Trả về None nếu không có ký tự ổ đĩa
    
    try:
        volume_guid = win32file.GetVolumeNameForVolumeMountPoint(f"{drive}\\")
        return volume_guid.strip("\\")  # Xóa ký tự "\" thừa
    except Exception as e:
        print(f"Lỗi khi lấy UUID của ổ {drive}: {e}")
        return None

def select_folder(title="Chọn thư mục"):
    """Mở hộp thoại chọn thư mục và lấy UUID của ổ đĩa"""
    root = tk.Tk()
    root.withdraw()
    folder = filedialog.askdirectory(title=title)
    root.destroy()

    if folder:
        uuid = get_drive_uuid(folder)
        return folder, uuid
    return None

def is_hidden(filepath):
    """Kiểm tra xem tệp/thư mục có thuộc tính ẩn không"""
    try:
        attrs = ctypes.windll.kernel32.GetFileAttributesW(filepath)
        return attrs & FILE_ATTRIBUTE_HIDDEN
    except:
        return False

def set_hidden(filepath):
    """Đặt thuộc tính ẩn cho tệp/thư mục"""
    try:
        ctypes.windll.kernel32.SetFileAttributesW(filepath, FILE_ATTRIBUTE_HIDDEN)
    except:
        pass

def is_temp_file(filename):
    """Kiểm tra xem tệp/thư mục có phải là tạm thời hay không."""
    temp_patterns = ["New folder", 
                     "New Text Document", 
                     "New shortcut", 
                     "New Microsoft Access Database", 
                     "New Bitmap image",
                     "New Microsoft Word Document",
                     "New Microsoft PowerPoint Presentation",
                     "New Microsoft Publisher Document",
                     "New Microsoft Excel Worksheet",
                     "New WinRAR ZIP archive"]
    return any(filename.startswith(pattern) or filename.endswith(pattern) for pattern in temp_patterns)

def is_recently_created(path, threshold=60):
    """Kiểm tra xem tệp hoặc thư mục có được tạo trong vòng `threshold` giây không."""
    creation_time = os.path.getctime(path)
    current_time = time.time()
    return (current_time - creation_time) < threshold

def list_files_and_folders(directory):
    result = {}
    
    for root, dirs, files in os.walk(directory):
        relative_path = os.path.relpath(root, directory)
        if relative_path == ".":
            relative_path = directory  # Thư mục gốc
        result[relative_path] = {"folders": dirs, "files": files}
    
    return result