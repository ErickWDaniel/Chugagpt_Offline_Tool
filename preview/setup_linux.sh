#!/bin/bash
# One-time setup script for Linux
# Run this first to prepare everything

set -e

echo "========================================"
echo "  Chugagpt Offline Tool - Setup"
echo "========================================"
echo ""

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed!"
    echo "Please install Python 3.10 or higher:"
    echo "  sudo apt update && sudo apt install python3 python3-venv python3-pip"
    exit 1
fi

echo "[1/4] Creating virtual environment..."
python3 -m venv venv

echo "[2/4] Installing dependencies (this may take a few minutes)..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "[3/4] Checking for Ollama..."
if ! command -v ollama &> /dev/null; then
    echo ""
    echo "Ollama not found. Installing Ollama for local AI models..."
    curl -fsSL https://ollama.com/install.sh | sh
    echo ""
    echo "Pulling recommended AI model (llama3.2)..."
    ollama pull llama3.2
else
    echo "Ollama is already installed."
fi

echo "[4/4] Creating launcher..."
cat > Run_Chugagpt.desktop << 'EOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=Chugagpt Offline Tool
Comment=Chat with AI models offline
Exec=bash -c "cd '$(dirname "$0")' && source venv/bin/activate && python main.py"
Icon=utilities-terminal
Terminal=false
Categories=Utility;Development;AI;
EOF
chmod +x Run_Chugagpt.desktop

echo ""
echo "========================================"
echo "  Setup Complete!"
echo "========================================"
echo ""
echo "To start the app:"
echo "  - Double-click 'Run_Chugagpt.desktop'"
echo "  - Or run: ./Run_Chugagpt_Linux.sh"
echo ""
echo "Enjoy!"
