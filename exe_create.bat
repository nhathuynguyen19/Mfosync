@echo off
cd /d "%~dp0" 
del /q mfosync.exe
pyinstaller --onefile --noconsole mfosync.py
for /f "delims=" %%i in ('where /r "%cd%\dist" mfosync.exe') do set EXE_PATH=%%i
if exist "%EXE_PATH%" (
    move /Y "%EXE_PATH%" "%cd%"
)
rmdir /s /q dist
del /q mfosync.spec
pause
