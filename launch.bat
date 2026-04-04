@echo off
title YancoHub
cd /d "%~dp0"
echo.
echo  YancoHub — Starting up...
echo.

:: Find Python (try py launcher first, then python3, then python)
set PYTHON=
where py >nul 2>&1 && set PYTHON=py && goto :found
where python3 >nul 2>&1 && set PYTHON=python3 && goto :found
where python >nul 2>&1 && set PYTHON=python && goto :found

echo  ERROR: Python not found. Install Python 3.10+ from python.org
echo.
pause
exit /b 1

:found
echo  Using: %PYTHON%

:: Create venv if it doesn't exist
if not exist "venv\Scripts\activate.bat" (
    echo  Creating virtual environment...
    %PYTHON% -m venv venv
    if errorlevel 1 (
        echo  ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: Activate venv
call venv\Scripts\activate.bat

:: Install/update requirements
echo  Checking dependencies...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo  ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

:: Launch
echo  Launching YancoHub...
echo.
python launch.py
if errorlevel 1 (
    echo.
    echo  YancoHub exited with an error.
    pause
)
