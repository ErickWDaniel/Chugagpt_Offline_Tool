#!/bin/bash
# Build script for Linux
# This script creates a standalone executable for Linux

echo "Building Chugagpt_Offline_Tool for Linux..."

# Navigate to project root
cd "$(dirname "$0")/.." || exit

# Activate virtual environment
source venv/bin/activate

# Install PyInstaller if not already installed
pip install pyinstaller

# Run PyInstaller with the spec file
pyinstaller preview/Chugagpt_Offline_Tool.spec --distpath preview/dist/linux --workpath preview/build/linux --clean

echo ""
echo "Build complete!"
echo "Executable location: preview/dist/linux/Chugagpt_Offline_Tool"
echo ""
echo "To run: ./preview/dist/linux/Chugagpt_Offline_Tool"
