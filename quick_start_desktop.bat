@echo off
setlocal
title MoviePop Quick Desktop Test

cd /d "%~dp0MoviePop-backend"

echo Launching MoviePop desktop test app...
echo.

python run_desktop.py
