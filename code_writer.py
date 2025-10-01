import os
from PySide6.QtWidgets import QFileDialog, QMessageBox
from pathlib import Path

class CodeWriter:
    def __init__(self, parent=None):
        self.parent = parent
        self.language_extensions = {
            'python': '.py',
            'javascript': '.js',
            'typescript': '.ts',
            'html': '.html',
            'css': '.css',
            'json': '.json',
            'markdown': '.md',
            'cpp': '.cpp',
            'c': '.c',
            'java': '.java',
            'go': '.go',
            'rust': '.rs',
            'ruby': '.rb',
            'php': '.php',
            'sql': '.sql',
            'bash': '.sh',
            'powershell': '.ps1',
            'yaml': '.yaml',
            'xml': '.xml'
        }

    def _get_language_extension(self, language):
        """Get file extension for the given language."""
        return self.language_extensions.get(language.lower(), '.txt')

    def detect_language_from_content(self, content: str) -> str:
        """Heuristically detect a programming language from content."""
        import re
        text = content or ""
        lower = text.lower()
        # 1) Fenced code block language hint ```lang
        m = re.search(r"```(\w+)", text)
        if m:
            alias = m.group(1).lower()
            alias_map = {
                'py': 'python', 'python': 'python',
                'js': 'javascript', 'javascript': 'javascript',
                'ts': 'typescript', 'typescript': 'typescript',
                'c++': 'cpp', 'cpp': 'cpp', 'c': 'c',
                'ps1': 'powershell', 'sh': 'bash', 'bash': 'bash',
                'html': 'html', 'css': 'css', 'json': 'json',
                'yaml': 'yaml', 'yml': 'yaml', 'xml': 'xml',
                'java': 'java', 'go': 'go', 'rust': 'rust',
                'rb': 'ruby', 'ruby': 'ruby', 'php': 'php', 'sql': 'sql',
                'md': 'markdown', 'markdown': 'markdown'
            }
            return alias_map.get(alias, alias)
        # 2) JSON (try quick parse)
        try:
            import json
            s = text.strip()
            if (s.startswith("{") or s.startswith("[")) and ":" in s:
                json.loads(s)
                return "json"
        except Exception:
            pass
        # 3) HTML
        if "<html" in lower or "</html" in lower or "<!doctype html" in lower:
            return "html"
        # 4) YAML (key: value lines without semicolons)
        if re.search(r"(?m)^\s*[-\w]+\s*:\s+.+$", text) and not re.search(r";\s*$", text):
            return "yaml"
        # 5) Python
        if re.search(r"(?m)^\s*def\s+\w+\s*\(.*\)\s*:", text) or re.search(r"(?m)^\s*class\s+\w+\s*:", text):
            return "python"
        # 6) TypeScript vs JavaScript
        if re.search(r"(?m)\b(function|const|let|=>)\b", text):
            if re.search(r"(?m)\binterface\b|\btype\s+\w+\s*=", text) or re.search(r"(?m)\bimport\s+.*from\s+['\"].*['\"]\s*;", text):
                return "typescript"
            return "javascript"
        # 7) C / C++
        if re.search(r"(?m)^\s*#include\s*<", text) or re.search(r"(?m)\bprintf\s*\(", text) or "std::" in text:
            return "cpp" if ("iostream" in text or "std::" in text) else "c"
        # 8) Java
        if re.search(r"(?m)\bpublic\s+class\b|\bSystem\.out\.println\b", text):
            return "java"
        # 9) Go
        if re.search(r"(?m)^\s*package\s+\w+", text) and "func " in text:
            return "go"
        # 10) Rust
        if re.search(r"(?m)^\s*fn\s+\w+\s*\(", text) and "let " in text:
            return "rust"
        # 11) SQL
        if re.search(r"(?is)\bselect\b.*\bfrom\b", text):
            return "sql"
        # 12) Bash
        if re.search(r"(?m)^#!/bin/(ba)?sh", text) or re.search(r"(?m)^\s*(echo|cd|ls|export)\b", text):
            return "bash"
        # 13) Markdown
        if re.search(r"(?m)^#\s+\S+", text):
            return "markdown"
        # Default
        return "python"
    
    def get_save_location(self, suggested_name, language):
        """Prompt user for save location."""
        if not self.parent:
            return None
        file_path, _ = QFileDialog.getSaveFileName(
            self.parent,
            "Save Code File",
            suggested_name,
            "All Files (*)"
        )
        return file_path if file_path else None

    def write_code_to_file(self, code, file_path, language, create_backup=True, confirm_overwrite=True):
        """Write code to file with optional backup and overwrite confirmation."""
        try:
            if not file_path:
                return False

            # Check if file exists and confirm overwrite
            if confirm_overwrite and os.path.exists(file_path):
                reply = QMessageBox.question(
                    self.parent,
                    "Overwrite File",
                    f"File '{file_path}' already exists. Overwrite?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return False

            # Create backup if requested
            if create_backup and os.path.exists(file_path):
                backup_path = file_path + '.backup'
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        backup_content = f.read()
                    with open(backup_path, 'w', encoding='utf-8') as f:
                        f.write(backup_content)
                except Exception as e:
                    print(f"Failed to create backup: {e}")

            # Write the code
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)

            return True

        except Exception as e:
            if self.parent:
                QMessageBox.critical(self.parent, "Write Error", f"Failed to write code:\n{str(e)}")
            return False

    def accept_changes(self, file_path):
        """Accept changes by removing backup file."""
        backup_path = file_path + '.backup'
        if os.path.exists(backup_path):
            try:
                os.remove(backup_path)
            except Exception as e:
                print(f"Failed to remove backup: {e}")