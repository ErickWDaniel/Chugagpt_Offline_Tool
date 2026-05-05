@echo off
REM Build script for Windows
REM This script creates a standalone executable for Windows
REM Run this on Windows with Python and PyInstaller installed

echo Building Chugagpt_Offline_Tool for Windows...

REM Navigate to project root
cd /d "%~dp0.."

REM Activate virtual environment (if using one)
REM call venv\Scripts\activate.bat

REM Install PyInstaller if not already installed
pip install pyinstaller

REM Run PyInstaller with the spec file
pyinstaller preview/Chugagpt_Offline_Tool.spec --distpath preview/dist/windows --workpath preview/build/windows --clean

echo.
echo Build complete!
echo Executable location: preview\dist\windows\Chugagpt_Offline_Tool.exe
echo.
echo To run: Double-click preview\dist\windows\Chugagpt_Offline_Tool.exe
