import re
import subprocess
import json

def clean_output(text):
    text = re.sub(r'[\u2800-\u28FF]', '', text)
    text = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text)
    return text

def get_ollama_models(ollama_path: str = "ollama"):
    """Return a list of locally available Ollama model names.
    Tries JSON format first, falls back to parsing plain text.
    """
    try:
        # Prefer JSON output when available
        result = subprocess.run(
            [ollama_path, "list", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                # Expected: [{"name": "model:tag", ...}, ...]
                names = [item.get("name") for item in data if isinstance(item, dict) and item.get("name")]
                return names
            except json.JSONDecodeError:
                pass
        # Fallback to plain text parsing
        result = subprocess.run([ollama_path, "list"], capture_output=True, text=True, timeout=5)
        names = []
        for line in result.stdout.splitlines():
            # Lines look like: "llama3:8b  4.7 GB  xxx"
            parts = line.strip().split()
            if parts and ":" in parts[0]:
                names.append(parts[0])
        return names
    except Exception:
        return []
