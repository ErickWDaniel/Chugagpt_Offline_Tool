import json
from datetime import datetime

HISTORY_FILE = "history.json"

def save_history(user_text, model):
    entry = {
        "date": str(datetime.now()),
        "user": user_text,
        "model": model
    }
    with open(HISTORY_FILE, "a") as f:
        json.dump(entry, f)
        f.write("\n")

def load_history():
    entries = []
    try:
        with open(HISTORY_FILE, "r") as f:
            for line in f:
                try:
                    entries.append(json.loads(line.strip()))
                except:
                    continue
    except FileNotFoundError:
        pass
    return entries
