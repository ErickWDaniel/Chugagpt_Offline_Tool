import re
import subprocess
import json

# Robust ANSI/OSC/DCS escape sequence removal (streaming-safe helpers included)
_ANSI_RE = re.compile(
    r'(?:'
    r'\x1B\[[0-?]*[ -/]*[@-~]'            # CSI ... final byte @-~
    r'|\x1B\][^\x07\x1B]*(?:\x07|\x1B\\)' # OSC ... BEL or ST (ESC \)
    r'|\x1B[P^_].*?\x1B\\'                # DCS/PM/APC ... ST (ESC \) non-greedy
    r'|\x1B[@-Z\\-_]'                     # 2-char escapes
    r')',
    re.DOTALL
)

def _split_incomplete_ansi_tail(s):
    """Split s into (safe_prefix, carry_tail) where carry_tail is a trailing
    incomplete ANSI/OSC/DCS sequence to be held for the next chunk.
    """
    idx = s.rfind('\x1B')
    if idx == -1:
        return s, ''
    tail = s[idx:]
    # Lone ESC at end
    if tail == '\x1B':
        return s[:idx], tail
    # OSC: ESC ] ... (BEL or ST terminator)
    if tail.startswith('\x1B]'):
        if '\x07' in tail or '\x1B\\' in tail:
            return s, ''
        return s[:idx], tail
    # DCS/PM/APC: ESC P/^/_ ... ST(ESC \)
    if tail.startswith('\x1BP') or tail.startswith('\x1B^') or tail.startswith('\x1B_'):
        if '\x1B\\' in tail:
            return s, ''
        return s[:idx], tail
    # CSI: ESC [  ... final byte @-~
    if tail.startswith('\x1B['):
        if re.search(r'[@-~]', tail[2:]):
            return s, ''
        return s[:idx], tail
    # Single-char ESC sequence incomplete if only one char remains
    if len(tail) < 2:
        return s[:idx], tail
    return s, ''

class AnsiStreamSanitizer:
    """Streaming-safe sanitizer that buffers incomplete escape sequences across chunks."""
    def __init__(self):
        self._carry = ''

    def push(self, chunk):
        if not chunk:
            return ''
        s = self._carry + chunk
        safe, self._carry = _split_incomplete_ansi_tail(s)
        # Remove escape sequences from the safe portion
        cleaned = _ANSI_RE.sub('', safe)
        # Optional normalizations
        cleaned = re.sub(r'[\u2800-\u28FF]', '', cleaned)  # strip braille patterns
        cleaned = cleaned.replace('\r', '')                # normalize CR
        return cleaned

def clean_output(text):
    # Remove Braille patterns (if any)
    text = re.sub(r'[\u2800-\u28FF]', '', text)
    
    # Remove ANSI/OSC/DCS escape sequences and normalize CR
    text = text.replace('\r', '')
    text = _ANSI_RE.sub('', text)
    
    return text.strip()

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
