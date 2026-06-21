:: run_server.bat
@echo off
REM Launch server.py using the venv Python

REM Ensure we’re in project root
cd /d %~dp0\..

REM Path to venv Python
set PYTHON=.venv\Scripts\python.exe

REM Check if venv exists
if not exist "%PYTHON%" (
    echo Virtual environment not found at %PYTHON%
    echo Run: python -m venv .venv
    exit /b 1
)

REM Run server.py through venv
echo Starting server.py with %PYTHON%
"%PYTHON%" server.py
