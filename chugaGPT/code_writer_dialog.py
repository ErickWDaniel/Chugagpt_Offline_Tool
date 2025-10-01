from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QCheckBox, QPushButton, QProgressBar,
    QDialogButtonBox, QFileDialog, QMessageBox
)
from PySide6.QtCore import Signal
from code_writer import CodeWriter

class CodeWriterDialog(QDialog):
    code_written = Signal(str, bool)  # file_path, success

    def __init__(self, parent=None, code_content="", suggested_filename="", language="python"):
        super().__init__(parent)
        self.code_content = code_content
        self.suggested_filename = suggested_filename
        self.language = language
        self.code_writer = CodeWriter(self)

        self.setWindowTitle("Write Code to File")
        self.setModal(True)
        self.resize(500, 300)

        self.init_ui()
        self.setup_connections()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # File path
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("File Path:"))
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setText(self.suggested_filename)
        path_layout.addWidget(self.file_path_edit)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_file)
        path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)

        # Language
        lang_layout = QHBoxLayout()
        lang_layout.addWidget(QLabel("Language:"))
        self.language_combo = QComboBox()
        self.language_combo.addItems([
            "python", "javascript", "typescript", "html", "css",
            "json", "markdown", "cpp", "c", "java", "go", "rust",
            "ruby", "php", "sql", "bash", "powershell", "yaml", "xml"
        ])
        self.language_combo.setCurrentText(self.language)
        lang_layout.addWidget(self.language_combo)
        lang_layout.addStretch()
        layout.addLayout(lang_layout)

        # Options
        self.create_backup_check = QCheckBox("Create backup file")
        self.create_backup_check.setChecked(True)
        layout.addWidget(self.create_backup_check)

        self.confirm_overwrite_check = QCheckBox("Confirm overwrite")
        self.confirm_overwrite_check.setChecked(True)
        layout.addWidget(self.confirm_overwrite_check)

        # Status
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Buttons
        button_box = QDialogButtonBox()
        self.write_btn = QPushButton("Write Code")
        self.write_btn.setDefault(True)
        button_box.addButton(self.write_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        cancel_btn = button_box.addButton(QDialogButtonBox.StandardButton.Cancel)
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(button_box)

    def setup_connections(self):
        self.write_btn.clicked.connect(self.write_code)

    def browse_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Code File", self.file_path_edit.text(), "All Files (*)"
        )
        if file_path:
            self.file_path_edit.setText(file_path)

    def write_code(self):
        """Write the code to the specified file."""
        file_path = self.file_path_edit.text().strip()
        language = self.language_combo.currentText()
        if not file_path:
            # Prompt for save location if not provided
            suggested_name = self.suggested_filename or f"new_file{self.code_writer._get_language_extension(language)}"
            chosen = self.code_writer.get_save_location(suggested_name, language)
            if not chosen:
                self.status_label.setText("Save cancelled.")
                return
            file_path = chosen
            self.file_path_edit.setText(file_path)

        create_backup = self.create_backup_check.isChecked()
        confirm_overwrite = self.confirm_overwrite_check.isChecked()

        # Update status
        self.status_label.setText("Writing code to file...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.write_btn.setEnabled(False)

        # Write the code
        success = self.code_writer.write_code_to_file(
            code=self.code_content,
            file_path=file_path,
            language=language,
            create_backup=create_backup,
            confirm_overwrite=confirm_overwrite
        )

        # This will be handled by the signal, but we hide progress for now
        self.progress_bar.setVisible(False)
        self.write_btn.setEnabled(True)

        if success:
            self.status_label.setText(f"Code successfully written to: {file_path}")
            self.code_written.emit(file_path, True)
            # Don't auto-close, let user see the result
        else:
            self.status_label.setText("Failed to write code to file.")
