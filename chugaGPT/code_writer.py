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