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

# Lấy đường dẫn thư mục chứa file .exe hoặc .py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TASK_FILE = os.path.join(BASE_DIR, "tasks.json")
FILE_ATTRIBUTE_HIDDEN = 0x2
running_threads = {}  # Lưu các luồng đồng bộ đang chạy
stop_flags = {}  # Cờ dừng cho từng tiến trình

root = tk.Tk()
root.withdraw()

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
    return filedialog.askdirectory(title=title)

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

def sync_folders(src, dst):
    """Đồng bộ hóa từ thư mục nguồn (src) sang thư mục đích (dst) mà KHÔNG xóa dữ liệu ở nguồn"""
    
    # 🔹 Kiểm tra nếu thư mục đích bị xóa khi đang chạy
    if not os.path.exists(dst):
        print(f"⚠️ Thư mục đích {dst} bị xóa! Đang tạo lại...")
        os.makedirs(dst)

    # 🔹 Kiểm tra nếu thư mục nguồn bị xóa (chương trình sẽ không làm gì)
    if not os.path.exists(src):
        print(f"⚠️ Thư mục nguồn {src} không tồn tại! Bỏ qua đồng bộ.")
        return

    # 🔹 Lấy danh sách tệp/thư mục
    src_files = set(os.listdir(src))
    dst_files = set(os.listdir(dst))

    for file in src_files:
        src_path = os.path.join(src, file)
        dst_path = os.path.join(dst, file)

        if os.path.isdir(src_path):
            # 🔥 Chỉ tạo thư mục con nếu nó có dữ liệu trong nguồn
            if not os.path.exists(dst_path):
                os.makedirs(dst_path)
                print(f"📂 Đã tạo thư mục: {dst_path}")

            sync_folders(src_path, dst_path)

        else:
            try:
                if file not in dst_files or (os.path.exists(dst_path) and not filecmp.cmp(src_path, dst_path, shallow=False)):
                    shutil.copy2(src_path, dst_path)
                    print(f"📄 Đã sao chép: {src_path} -> {dst_path}")
                    continue
            except PermissionError:
                print(f"❌ Không thể truy cập {src_path}. Bỏ qua.")

    # ❌ Không bao giờ xóa file/thư mục trong nguồn
    for file in dst_files:
        if file not in src_files:  # Nếu file không còn trong nguồn, xóa khỏi đích
            dst_path = os.path.join(dst, file)
            if os.path.isdir(dst_path):
                shutil.rmtree(dst_path, onerror=remove_readonly)
            else:
                os.remove(dst_path)
            print(f"🗑 Đã xóa khỏi {dst}: {dst_path}")

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
                usb_plugin = False
            time.sleep(1)
            continue  # Quay lại vòng lặp để tiếp tục kiểm tra
        
        # Kiểm tra thư mục đích, nếu chưa có thì tạo
        if not os.path.exists(dst):
            print(f"[{task_name}] Thư mục đích chưa tồn tại, đang tạo...")
            os.makedirs(dst)

        # Thông báo USB đã được cắm
        if not usb_plugin:
            print(f"[{task_name}] Ổ đĩa đã cắm, bắt đầu đồng bộ...")
            usb_plugin = True

        # Tiến hành đồng bộ
        sync_folders(src, dst)
        sync_folders(dst, src)
        print(f"[{task_name}] Đồng bộ hoàn tất.")
        time.sleep(1)

    print(f"[{task_name}] Đã dừng đồng bộ.")  # Xác nhận tiến trình đã dừng

def create_process(icon, item):
    tasks = load_tasks()

    task_name = simpledialog.askstring("Tên tiến trình", "Nhập tên tiến trình:", parent=root)
    root.destroy()

    if not task_name:
        print("⚠️ Tên tiến trình không được để trống.")
        return
    
    try:
        task_name = task_name.strip()  # Xóa khoảng trắng thừa
        task_name.encode('utf-8')  # Kiểm tra xem có lỗi Unicode không
    except UnicodeEncodeError:
        print("❌ Lỗi khi nhập tên tiến trình, vui lòng nhập lại bằng ký tự hợp lệ.")
        return

    if task_name in [t["name"] for t in tasks]:
        print("⚠️ Tên tiến trình đã tồn tại.")
        return

    src = select_folder("Chọn thư mục nguồn")
    if not src:
        print("⚠️ Hủy tiến trình do không có thư mục nguồn.")
        return

    dst = select_folder("Chọn thư mục đích")
    if not dst:
        print("⚠️ Hủy tiến trình do không có thư mục đích.")
        return

    tasks.append({"name": task_name, "source": src, "destination": dst})
    save_tasks(tasks)

    thread = threading.Thread(target=sync_loop, args=(task_name, src, dst), daemon=True)
    thread.start()
    running_threads[task_name] = thread

    update_menu(icon)


def update_menu(icon):
    """Cập nhật menu systray với danh sách tiến trình"""
    tasks = load_tasks()

    if not isinstance(tasks, list):
        print("Lỗi: tasks không phải danh sách hợp lệ!")
        return

    menu_items = [MenuItem("Tạo tiến trình", create_process_thread)]
    task_name_item = []
    for task in tasks:
        if not isinstance(task, dict):
            print("Lỗi: task không phải dictionary!", task)
            continue  # Bỏ qua phần tử không hợp lệ

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

    icon = Icon("Sync USB", create_icon(), menu=Menu())
    update_menu(icon)
    icon.run()

def exit_app(icon):
    """Thoát ứng dụng"""
    icon.stop()
    os._exit(0)

# Khởi chạy tiến trình có sẵn
tasks = load_tasks()
for task in tasks:  # Duyệt từng task trong danh sách
    thread = threading.Thread(target=sync_loop, args=(task["name"], task["source"], task["destination"]), daemon=True)
    thread.start()

# Khởi chạy icon system tray
create_system_tray_icon()

# Hiển thị thông báo
messagebox.showinfo("Thông báo", "Finish!")
