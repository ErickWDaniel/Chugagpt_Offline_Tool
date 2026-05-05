@echo off
REM Chugagpt Offline Tool - Windows Launcher
REM Double-click this file to start the application

echo Starting Chugagpt Offline Tool...
echo Make sure Ollama is running for local AI models!

REM Get the directory where this batch file is located
cd /d "%~dp0.."

REM Check if venv exists
if not exist "venv\" (
    echo Virtual environment not found. Creating one...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

REM Run the application
python main.py

if errorlevel 1 (
    echo.
    echo Error running the application.
    echo Make sure you have Python 3 installed and Ollama running.
    pause
)
