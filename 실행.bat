@echo off
REM 주간 업무보고 코드 스니펫 생성기 - 원클릭 실행 런처
REM 이 파일과 weekly_report_web.py가 같은 폴더에 있어야 합니다.

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python이 설치되어 있지 않습니다. https://www.python.org 에서 설치 후 다시 실행해주세요.
    pause
    exit /b 1
)

python -c "import flask" >nul 2>nul
if errorlevel 1 (
    echo Flask 설치 중...
    pip install flask
)

start "" http://127.0.0.1:5050
python weekly_report_web.py

pause
