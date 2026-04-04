@echo off
title YancoHub
cd /d "%~dp0"

:: Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found! Please install Python 3.10+
    pause
    exit /b 1
)

:: Check for venv
if not exist "venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv venv
    echo Installing dependencies...
    venv\Scripts\pip install -r requirements.txt
)

:: Run YancoHub
venv\Scripts\python launch.py
