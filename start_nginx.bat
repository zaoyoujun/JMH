@echo off
chcp 65001 >nul 2>nul
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python not found. Please install Python 3.10+ first.
  pause
  exit /b 1
)

if not exist "MoviePop-backend\requirements.txt" (
  echo Missing backend files.
  pause
  exit /b 1
)

cd /d "%~dp0MoviePop-backend"
python run_api.py
pause
