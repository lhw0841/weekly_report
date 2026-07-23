@echo off
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python not found. Please install from https://www.python.org
    pause
    exit /b 1
)

python -c "import flask" >nul 2>nul
if errorlevel 1 (
    echo Installing flask...
    python -m pip install flask
    if errorlevel 1 (
        echo Failed to install flask. Try running "python -m pip install flask" manually.
        pause
        exit /b 1
    )
)

start "" http://127.0.0.1:5050
python weekly_report_web.py

pause
