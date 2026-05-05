#!/bin/bash
# Quick Ollama installer for Linux users

echo "Installing Ollama for local AI models..."
curl -fsSL https://ollama.com/install.sh | sh

echo ""
echo "Ollama installed! Now pulling a recommended model (llama3.2)..."
ollama pull llama3.2

echo ""
echo "Setup complete! You can now run Chugagpt_Offline_Tool"
