import os
import filecmp
import shutil
import tkinter as tk
from tkinter import simpledialog, filedialog, messagebox
import time
import ctypes
import threading
import json
from pystray import Icon, MenuItem, Menu
from PIL import Image, ImageDraw
import functools
import stat
import sys

if getattr(sys, 'frozen', False):  # Kiểm tra nếu chương trình chạy từ PyInstaller
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TASK_FILE = os.path.join(BASE_DIR, "tasks.json")
FILE_ATTRIBUTE_HIDDEN = 0x2
lock = threading.Lock()
running_threads = {}  # Lưu các luồng đồng bộ đang chạy
stop_flags = {}  # Cờ dừng cho từng tiến trình
running_flags = {}  # Cờ đánh dấu tiến trình đang chạy

def show_notification():
    messagebox.showinfo("Thông báo", "Process is running in the background. Check in system tray.")

def remove_readonly(func, path, _):
    os.chmod(path, stat.S_IWRITE)
    func(path)

def create_process_thread(icon, item):
    threading.Thread(target=create_process, args=(icon, item), daemon=True).start()

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

def select_folder(title):
    """Mở hộp thoại chọn thư mục"""
    root = tk.Tk()
    root.withdraw()
    folder = filedialog.askdirectory(title=title)
    root.destroy()
    return folder

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
    temp_patterns = ["~", ".tmp", ".part", ".crdownload", "New Folder", "New Text Document"]
    return any(filename.startswith(pattern) or filename.endswith(pattern) for pattern in temp_patterns)

def is_temp_file(filename):
    """Kiểm tra xem tệp/thư mục có phải là tạm thời không."""
    temp_extensions = {'.tmp', '.swp', '.lock'}
    return any(filename.endswith(ext) for ext in temp_extensions)

def is_recently_created(path, threshold=60):
    """Kiểm tra xem tệp hoặc thư mục có được tạo trong vòng `threshold` giây không."""
    creation_time = os.path.getctime(path)
    current_time = time.time()
    return (current_time - creation_time) < threshold

def sync_folders(src, dst, task_name):
    """Đồng bộ hóa thư mục nguồn sang thư mục đích theo hướng một chiều."""
    if not os.path.exists(src):
        if os.path.exists(dst):
            running_flags[task_name] = True
            shutil.rmtree(dst)
            print(f"Đã xóa thư mục đích: {dst} vì thư mục nguồn không tồn tại.")
        running_flags[task_name] = False
        return
    
    if not os.path.exists(dst):
        running_flags[task_name] = True
        os.makedirs(dst)
        print(f"Đã tạo thư mục đích: {dst}")
    running_flags[task_name] = False
    
    for root, dirs, files in os.walk(src):
        rel_path = os.path.relpath(root, src)
        dst_root = os.path.join(dst, rel_path) if rel_path != '.' else dst
        
        if not os.path.exists(dst_root):
            os.makedirs(dst_root)
            running_flags[task_name] = True
            print(f"Đã tạo thư mục: {dst_root}")
        running_flags[task_name] = False
        
        for file in files:
            if is_temp_file(file):
                continue
            
            src_path = os.path.join(root, file)
            dst_path = os.path.join(dst_root, file)
            
            if not os.path.exists(dst_path) or not filecmp.cmp(src_path, dst_path, shallow=False):
                running_flags[task_name] = True
                shutil.copy2(src_path, dst_path)
                print(f"Đã cập nhật: {src_path} -> {dst_path}")
            running_flags[task_name] = False
    
    for root, dirs, files in os.walk(dst, topdown=False):
        rel_path = os.path.relpath(root, dst)
        src_root = os.path.join(src, rel_path) if rel_path != '.' else src
        
        for file in files:
            dst_path = os.path.join(root, file)
            src_file_path = os.path.join(src_root, file)
            if not os.path.exists(src_file_path) and not is_temp_file(file):
                if not is_recently_created(dst_path):  # Kiểm tra thời gian tạo
                    os.remove(dst_path)
                    running_flags[task_name] = True
                    print(f"Đã xóa tệp: {dst_path}")
            running_flags[task_name] = False
        
        for dir in dirs:
            dst_dir = os.path.join(root, dir)
            src_dir_path = os.path.join(src_root, dir)
            if not os.path.exists(src_dir_path):
                if not is_recently_created(dst_dir):  # Kiểm tra thời gian tạo
                    shutil.rmtree(dst_dir)
                    running_flags[task_name] = True
                    print(f"Đã xóa thư mục: {dst_dir}")
            running_flags[task_name] = False

def sync_loop(task_name, src, dst):
    """Luồng chạy đồng bộ hóa cho từng tiến trình"""
    print(f"[{task_name}] Bắt đầu giám sát...")

    usb_plugin = True
    stop_flags[task_name] = False  # Cờ kiểm soát vòng lặp
    
    while not stop_flags[task_name]:
        # Kiểm tra xem ổ đĩa có tồn tại không
        dst_drive = os.path.splitdrive(dst)[0]  # Lấy phần ổ đĩa (ví dụ: 'E:')
        if not os.path.exists(dst_drive):
            if usb_plugin:
                print(f"[{task_name}] Ổ đĩa chưa cắm, đang chờ...")
                running_flags[task_name] = False
                usb_plugin = False
            time.sleep(2)
            continue  # Quay lại vòng lặp để tiếp tục kiểm tra
        running_flags[task_name] = True
        
        # Kiểm tra thư mục đích, nếu chưa có thì tạo
        if not os.path.exists(dst):
            print(f"[{task_name}] Thư mục đích chưa tồn tại, đang tạo...")
            os.makedirs(dst)
            running_flags[task_name] = True
        running_flags[task_name] = False

        # Thông báo USB đã được cắm
        if not usb_plugin:
            print(f"[{task_name}] Ổ đĩa đã cắm, bắt đầu đồng bộ...")
            running_flags[task_name] = True
            usb_plugin = True
        running_flags[task_name] = False

        # Tiến hành đồng bộ
        running_flags[task_name] = True
        sync_folders(src, dst, task_name)
        running_flags[task_name] = False
        print(f"[{task_name}] Đồng bộ hoàn tất.")
        time.sleep(2)

    print(f"[{task_name}] Đã dừng đồng bộ.")  # Xác nhận tiến trình đã dừng

def create_process(icon, item):
    tasks = load_tasks()
    root = tk.Tk()
    root.withdraw()

    task_name = simpledialog.askstring("Tên tiến trình", "Nhập tên tiến trình:", parent=root)
    root.destroy()

    if not task_name:
        print("⚠️ Tên tiến trình không được để trống.")
        messagebox.showerror("Lỗi", "Tên tiến trình không được để trống.")
        return
    
    try:
        task_name = task_name.strip()  # Xóa khoảng trắng thừa
        task_name.encode('utf-8')  # Kiểm tra xem có lỗi Unicode không
    except UnicodeEncodeError:
        print("❌ Lỗi khi nhập tên tiến trình, vui lòng nhập lại bằng ký tự hợp lệ.")
        messagebox.showerror("Lỗi", "Tên tiến trình không hợp lệ. Vui lòng nhập lại.")
        return

    if task_name in [t["name"] for t in tasks]:
        print("⚠️ Tên tiến trình đã tồn tại.")
        messagebox.showerror("Lỗi", "Tên tiến trình đã tồn tại. Vui lòng chọn tên khác.")
        return

    src = select_folder("Chọn thư mục nguồn")
    if not src:
        print("⚠️ Hủy tiến trình do không có thư mục nguồn.")
        messagebox.showerror("Lỗi", "Không có thư mục nguồn nào được chọn.")
        return

    dst = select_folder("Chọn thư mục đích")
    if not dst:
        print("⚠️ Hủy tiến trình do không có thư mục đích.")
        messagebox.showerror("Lỗi", "Không có thư mục đích nào được chọn.")
        return

    if not src or not dst:
        print("⚠️ Hủy tiến trình do không có thư mục nguồn hoặc đích.")
        messagebox.showerror("Lỗi", "Không có thư mục nguồn hoặc đích nào được chọn.")
        return

    tasks.append({"name": task_name, "source": src, "destination": dst})
    save_tasks(tasks)

    thread = threading.Thread(target=sync_loop, args=(task_name, src, dst, icon), daemon=True)
    thread.start()
    running_threads[task_name] = thread
    running_flags[task_name] = True

    update_menu(icon)

    messagebox.showinfo(f"Thông báo", "Tiến trình đã được thêm.")

def update_menu(icon):
    """Cập nhật menu systray với danh sách tiến trình"""
    tasks = load_tasks()

    if not isinstance(tasks, list):
        print("Lỗi: tasks không phải danh sách hợp lệ!")
        return

    menu_items = [MenuItem("Tạo tiến trình", create_process_thread)]
    task_name_item = []

    with lock:
        for task in tasks:
            if not isinstance(task, dict):
                print("Lỗi: task không phải dictionary!", task)
                continue  # Bỏ qua phần tử không hợp lệ
            if running_flags.get(task["name"], False):
                task_name = task.get("name", "Không tên")
            else:
                task_name = task.get("name", "Không tên")
            task_name = task_name.encode("utf-8").decode("utf-8")
            source = task.get("source", "Không xác định")
            destination = task.get("destination", "Không xác định")

            # Tạo submenu cho từng tiến trình
            task_submenu = Menu(
                MenuItem(f"🟢 {source} → {destination}", lambda: None, enabled=False),
                MenuItem(f"❌ Xóa {task_name}", functools.partial(delete_task, icon, task_name))
            )
            task_name_item.append(MenuItem(task_name, task_submenu))

    if task_name_item:
        menu_items.append(MenuItem("Danh sách tiến trình", Menu(*task_name_item)))
    else:
        menu_items.append(MenuItem("Không có tiến trình", lambda: None, enabled=False))

    menu_items.append(MenuItem("Thoát", lambda icon, item: exit_app(icon)))
    icon.menu = Menu(*menu_items)

def delete_task(icon, task_name, *args):
    """Xóa một tiến trình khỏi danh sách"""
    tasks = load_tasks()

    # Tìm tiến trình cần xóa
    task_to_delete = next((t for t in tasks if t["name"] == task_name), None)
    if not task_to_delete:
        print(f"⚠️ Không tìm thấy tiến trình {task_name} để xóa.")
        return

    # Dừng tiến trình nếu đang chạy
    if task_name in stop_flags:
        stop_flags[task_name] = True  # Đặt cờ dừng

    if task_name in running_threads:
        running_threads[task_name].join()  # Đợi luồng dừng hẳn
        del running_threads[task_name]  # Xóa khỏi danh sách luồng
        del stop_flags[task_name]  # Xóa cờ dừng
    
    # Lọc danh sách, giữ lại các task không trùng tên
    new_tasks = [task for task in tasks if task.get("name") != task_name]

    if len(new_tasks) == len(tasks):
        print(f"Không tìm thấy tiến trình {task_name}")
        return
    
    # Lưu danh sách sau khi xóa
    save_tasks(new_tasks)
    print(f"Đã xóa tiến trình {task_name}")
    
    # Cập nhật lại menu systray
    update_menu(icon)

def create_system_tray_icon():
    """Tạo icon trên system tray"""
    def create_icon():
        size = (64, 64)
        image = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        draw.rectangle((16, 0, 49, 49), fill="silver", outline="black")
        draw.rectangle((21, 51, 43, 64), fill="white", outline="black")

        return image

    icon = Icon("Mfosync", create_icon(), menu=Menu())
    icon.title = "Mfosync"  # Tooltip hiển thị khi di chuột qua
    update_menu(icon)
    
    # Chạy thông báo trong luồng riêng để không chặn system tray
    threading.Thread(target=show_notification, daemon=True).start()
    icon.run()
    return icon

def exit_app(icon):
    """Thoát ứng dụng"""
    icon.stop()
    os._exit(0)

# Khởi chạy tiến trình có sẵn
tasks = load_tasks()
for task in tasks:  # Duyệt từng task trong danh sách
    thread = threading.Thread(target=sync_loop, args=(task["name"], task["source"], task["destination"]), daemon=True)
    thread.start()

create_system_tray_icon()

# Hiển thị thông báo
messagebox.showinfo("Thông báo", "Finish!")
