import tkinter as tk
from tkinter import filedialog

def select_folder(title):
    """Mở hộp thoại chọn thư mục"""
    root = tk.Tk()
    root.withdraw()
    folder = filedialog.askdirectory(title=title)
    root.destroy()
    return folder