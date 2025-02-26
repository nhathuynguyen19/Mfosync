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
from utils import *
from files import *
from paths import *
    
lock = threading.Lock()
running_threads = {}  # Lưu các luồng đồng bộ đang chạy
stop_flags = {}  # Cờ dừng cho từng tiến trình
running_flags = {}  # Cờ đánh dấu tiến trình đang chạy

def create_process_thread(icon, item):
    threading.Thread(target=create_process, args=(icon, item), daemon=True).start()

def sync_folders(src, dst, task_name, first=False):
    """Đồng bộ hóa thư mục giữa src và dst theo cả hai chiều."""
    deleted_items = set()
    
    if not os.path.exists(dst):
        os.makedirs(dst)
        print(f"Đã tạo thư mục đích: {dst}")
    
    if not os.path.exists(src):
        os.makedirs(src)
        print(f"Đã tạo thư mục nguồn: {src}")
    
    # Đồng bộ từ src -> dst
    sync_one_way(src, dst, task_name, True, first)
    # Đồng bộ từ dst -> src
    sync_one_way(dst, src, task_name, False, first)
    

def sync_one_way(src, dst, task_name, primary=False, first=False):

    if primary:
        current_struct = list_files_and_folders(src)
    else:
        current_struct = list_files_and_folders(dst)

    # Xóa file ở src nếu không có trong dst
    if not primary and not first:
        deleted = False
        for root, dirs, files in os.walk(src, topdown=False):  
            rel_path = os.path.relpath(root, src)
            dst_root = os.path.join(dst, rel_path) if rel_path != '.' else dst

            # XÓA FILE nếu không tồn tại trong `dst`
            for file in files:
                src_path = os.path.join(root, file)
                dst_path = os.path.join(dst_root, file)

                if not os.path.exists(dst_path) and not is_temp_file(src_path):
                    print(f"🚀 Xóa file: {src_path}")
                    os.remove(src_path)
                    deleted = True

            # XÓA THƯ MỤC nếu nó rỗng sau khi xóa file
            if deleted:
                for dir_name in dirs:
                    src_dir = os.path.join(root, dir_name)
                    dst_dir = os.path.join(dst_root, dir_name)

                    if not os.path.exists(dst_dir) and os.path.exists(src_dir):  # Nếu thư mục không có ở dst
                        try:
                            os.rmdir(src_dir)  # Xóa thư mục nếu nó RỖNG
                            print(f"🗑️ Đã xóa thư mục rỗng: {src_dir}")
                        except OSError:
                            print(f"⚠️ Không thể xóa {src_dir} (Không rỗng?)")
    
    """Đồng bộ hóa từ thư mục src sang dst."""
    for root, dirs, files in os.walk(src):
        rel_path = os.path.relpath(root, src)
        dst_root = os.path.join(dst, rel_path) if rel_path != '.' else dst

        # không tồn tại ở đích và không phải file tạm thời
        if not os.path.exists(dst_root) and not is_temp_file(rel_path):
            os.makedirs(dst_root)
            print(f"Đã tạo thư mục: {dst_root}")
        
        for file in files:
            src_path = os.path.join(root, file)
            dst_path = os.path.join(dst_root, file)
            
            if is_temp_file(file):
                continue
            
            if not os.path.exists(dst_path) and not is_temp_file(src_path):
                shutil.copy2(src_path, dst_path)
                print(f"Đã sao chép: {src_path} -> {dst_path}")
            elif not filecmp.cmp(src_path, dst_path, shallow=False):
                shutil.copy2(src_path, dst_path)
                print(f"Đã cập nhật: {src_path} -> {dst_path}")

def sync_loop(task_name, src, dst, src_uuid=None, dst_uuid=None):
    """Luồng chạy đồng bộ hóa cho từng tiến trình"""
    print(f"[{task_name}] Bắt đầu giám sát...")

    usb_plugin = True
    stop_flags[task_name] = False  # Cờ kiểm soát vòng lặp

    first = True
    while not stop_flags[task_name]:
        # Kiểm tra xem ổ đĩa có tồn tại không
        source_uuid = get_drive_uuid(src)
        if not source_uuid == src_uuid:
            if usb_plugin:
                print(f"[{task_name}] Ổ đĩa nguồn chưa cắm, đang chờ...")
                running_flags[task_name] = False
                usb_plugin = False
            time.sleep(2)
            continue  # Quay lại vòng lặp để tiếp tục kiểm tra
        running_flags[task_name] = True

        # Kiểm tra xem ổ đĩa có tồn tại không
        destination_uuid = get_drive_uuid(dst)
        if not destination_uuid == dst_uuid:
            if usb_plugin:
                print(f"[{task_name}] Ổ đĩa đích chưa cắm, đang chờ...")
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
        sync_folders(src, dst, task_name, first)
        running_flags[task_name] = False
        print(f"[{task_name}] Đồng bộ hoàn tất.")
        first = False
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

    src, src_uuid = select_folder("Chọn thư mục nguồn")
    if not src:
        print("⚠️ Hủy tiến trình do không có thư mục nguồn.")
        messagebox.showerror("Lỗi", "Không có thư mục nguồn nào được chọn.")
        return

    dst, dst_uuid = select_folder("Chọn thư mục đích")
    if not dst:
        print("⚠️ Hủy tiến trình do không có thư mục đích.")
        messagebox.showerror("Lỗi", "Không có thư mục đích nào được chọn.")
        return

    if not src or not dst:
        print("⚠️ Hủy tiến trình do không có thư mục nguồn hoặc đích.")
        messagebox.showerror("Lỗi", "Không có thư mục nguồn hoặc đích nào được chọn.")
        return

    tasks.append({"name": task_name, "source": src, "source_uuid": src_uuid, "destination_uuid": dst_uuid, "destination": dst})
    save_tasks(tasks)

    thread = threading.Thread(target=sync_loop, args=(task_name, src, dst, src_uuid, dst_uuid), daemon=True)
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
    if task['source_uuid'] and task['destination_uuid']:
        name_task = task["name"]
        src_path = task["source"]
        dst_path = task["destination"]
        src_struct = list_files_and_folders(src_path)
        dst_struct = list_files_and_folders(src_path)

        task_folder = os.path.join(BASE_DIR, "folder_struct", name_task)
        os.makedirs(task_folder, exist_ok=True)  # Tạo thư mục nếu chưa có
        src_struct_path = os.path.join(BASE_DIR, "folder_struct", name_task, "src_struct.json")
        dst_struct_path = os.path.join(BASE_DIR, "folder_struct", name_task, "dst_struct.json")
        
        # Lưu vào tệp JSON
        with open(src_struct_path, "w", encoding="utf-8") as json_file:
            json.dump(src_struct, json_file, indent=4, ensure_ascii=False)

        with open(dst_struct_path, "w", encoding="utf-8") as json_file:
            json.dump(dst_struct, json_file, indent=4, ensure_ascii=False)
            
        thread = threading.Thread(target=sync_loop, args=(task["name"], task["source"], task["destination"], task["source_uuid"], task["destination_uuid"]), daemon=True)
        thread.start()

create_system_tray_icon()

# Hiển thị thông báo
messagebox.showinfo("Thông báo", "Finish!")
