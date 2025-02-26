@echo off
cd /d "%~dp0"

:: Cài đặt thư viện từ requirements.txt
echo Installing libraries...
pip install -r requirements.txt

:: Chạy chương trình mà không hiển thị cửa sổ terminal
echo Running mfosync.py...
start /min pythonw mfosync.py

:: Thêm thông báo hoàn tất
echo --------------------------------------------------
echo Installation and program execution completed.

:: Đóng cửa sổ terminal
exit
