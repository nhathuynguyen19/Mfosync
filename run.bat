@echo off
cd /d "%~dp0"

:: Kiểm tra Python có sẵn không
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed. Downloading Python...
    powershell Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.11.6/python-3.11.6-amd64.exe" -OutFile python_installer.exe
    echo Installing Python...
    start /wait python_installer.exe /quiet InstallAllUsers=1 PrependPath=1
    del python_installer.exe
)

:: Kiểm tra pip có sẵn không
python -m ensurepip
python -m pip install --upgrade pip

:: Cài đặt thư viện
pip install -r requirements.txt
echo "Installing libraries..."

:: Chạy chương trình
pythonw mfosync.py
exit
