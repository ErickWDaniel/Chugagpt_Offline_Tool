# Chugagpt Offline Tool - User Guide

## What is this?
Chugagpt Offline Tool is a desktop application that lets you chat with AI models locally on your computer. No internet required after setup!

## For Linux Users

### Option 1: Run the Executable (Recommended)
1. Open the `dist/linux` folder
2. Double-click `Chugagpt_Offline_Tool` (or run it from terminal)
3. The app will start - that's it!

### Option 2: Build It Yourself
1. Open terminal in this folder
2. Run: `./build_linux.sh`
3. Wait for build to complete
4. Find your executable in `dist/linux/Chugagpt_Offline_Tool`

## For Windows Users

### Option 1: Run the Executable (Recommended)
1. Open the `dist/windows` folder
2. Double-click `Chugagpt_Offline_Tool.exe`
3. If Windows warns you, click "More info" then "Run anyway"
4. The app will start!

### Option 2: Build It Yourself
1. Install Python from https://python.org
2. Open Command Prompt in this folder
3. Run: `build_windows.bat`
4. Wait for build to complete
5. Find your executable in `dist\windows\Chugagpt_Offline_Tool.exe`

## First Time Setup

1. **Install Ollama** (for local AI models):
   - Linux: `curl -fsSL https://ollama.com/install.sh | sh`
   - Windows: Download from https://ollama.com/download

2. **Pull a model** (in terminal/command prompt):
   ```
   ollama pull llama3.2
   ```

3. **Start the app** and enjoy!

## Troubleshooting

- **App won't start**: Make sure Ollama is running in the background
- **No models found**: Run `ollama list` to see available models
- **Permission denied (Linux)**: Run `chmod +x Chugagpt_Offline_Tool`

## Need Help?
Check the main README.md file for more technical details.
