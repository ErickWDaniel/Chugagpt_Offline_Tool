import json
import os

SETTINGS_FILE = "settings.json"
DEFAULT_SETTINGS = {
    "ollama_path": "ollama",
    "font_size": 14,
    "dark_theme": True,
    "project_root": "..",
    "allow_long_analysis": False,
    "language": "english",
    "enable_completion": False,
    "model_provider": "ollama",
    "model": "phi3:mini",
    "openai_api_key": "",
    "anthropic_api_key": "",
    "google_api_key": "",
}

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            settings = json.load(f)
            # Merge with defaults
            return {**DEFAULT_SETTINGS, **settings}
    return DEFAULT_SETTINGS.copy()

def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=4)
