#!/bin/bash
# Chugagpt Offline Tool - Linux Launcher
# Double-click this file to start the application

cd "$(dirname "$0")/.." || exit

echo "Starting Chugagpt Offline Tool..."
echo "Make sure Ollama is running for local AI models!"

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Creating one..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Run the application
python main.py

if [ $? -ne 0 ]; then
    echo ""
    echo "Error running the application."
    echo "Make sure you have Python 3 installed and Ollama running."
    read -p "Press Enter to exit..."
fi
