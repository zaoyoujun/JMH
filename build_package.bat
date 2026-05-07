@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python not found. Please install Python 3.10+ first.
  exit /b 1
)

python -m PyInstaller --noconfirm --clean "MoviePop.spec"
if errorlevel 1 exit /b %errorlevel%

echo.
echo Package created: "%~dp0dist\MoviePop"
exit /b 0
