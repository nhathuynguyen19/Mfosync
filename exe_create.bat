@echo off
cd /d "%~dp0" 
pyinstaller --onefile --noconsole app.py
for /f "delims=" %%i in ('where /r "%cd%\dist" app.exe') do set EXE_PATH=%%i
if exist "%EXE_PATH%" (
    move /Y "%EXE_PATH%" "%cd%"
)
rmdir /s /q dist
del /q app.spec
pause
