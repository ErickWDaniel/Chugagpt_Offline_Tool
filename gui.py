from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
    QPushButton, QLabel, QComboBox, QDialog, QFormLayout,
    QSpinBox, QCheckBox, QDialogButtonBox, QFileDialog,
    QScrollArea, QGroupBox, QFrame
)
from PySide6.QtGui import QColor, QTextCharFormat, QFont, QSyntaxHighlighter
from PySide6.QtCore import Qt
from logic import OllamaTypingWorker
from settings import load_settings, save_settings
from history import save_history
from utils import get_ollama_models
from scanner import ProjectScanner, format_scan_results
import re

# -------------------------
# Syntax Highlighter
# -------------------------
class CodeHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None, language="python"):
        super().__init__(parent)
        self.language = language
        self.rules = []

        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#ff6600"))
        keyword_format.setFontWeight(QFont.Weight.Bold)

        keywords = []
        if language == "python":
            keywords = [
                "def", "class", "if", "else", "elif", "for", "while",
                "import", "from", "return", "in", "not", "and", "or",
                "with", "as", "pass", "break", "continue", "try", "except"
            ]
        elif language == "json":
            keywords = [r'"[^"]*"\s*:']

        for word in keywords:
            pattern = re.compile(r'\b' + word + r'\b') if language=="python" else re.compile(word)
            self.rules.append((pattern, keyword_format))

        # Strings
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#00ff99"))
        self.rules.append((re.compile(r'"[^"]*"'), string_format))
        self.rules.append((re.compile(r"'[^']*'"), string_format))

        # Numbers
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#99ccff"))
        self.rules.append((re.compile(r'\b\d+(\.\d+)?\b'), number_format))

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            for match in pattern.finditer(text):
                start, end = match.span()
                self.setFormat(start, end - start, fmt)

# -------------------------
# Settings Dialog
# -------------------------
class SettingsDialog(QDialog):
    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        layout = QFormLayout(self)

        self.path_input = QLineEdit()
        self.path_input.setText(settings.get("ollama_path", "ollama"))
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_path)
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(browse_btn)
        layout.addRow("Ollama Path:", path_layout)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 32)
        self.font_size_spin.setValue(settings.get("font_size", 14))
        layout.addRow("Font Size:", self.font_size_spin)

        self.dark_mode = QCheckBox("Enable Dark Mode")
        self.dark_mode.setChecked(settings.get("dark_theme", True))
        layout.addRow(self.dark_mode)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def browse_path(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select Ollama Executable")
        if file:
            self.path_input.setText(file)

# -------------------------
# Entity Sidebar
# -------------------------
class EntitySidebar(QWidget):
    """Sidebar widget that displays shortcut buttons for found entities."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.analysis_context = None
        self.main_window = parent  # Store reference to main window
        self.init_ui()

    def init_ui(self):
        """Initialize the sidebar UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Action buttons section
        self.add_action_buttons(layout)

        # Title
        title = QLabel("Entity Shortcuts")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-weight: bold; margin: 10px 0;")
        layout.addWidget(title)

        # Scrollable area for entities
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Container widget for scroll area
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(5)

        scroll_area.setWidget(self.container)
        layout.addWidget(scroll_area)

        # Initially show empty state
        self.show_empty_state()

    def add_action_buttons(self, layout):
        """Add common action buttons to the sidebar."""
        # New Chat button
        new_chat_btn = QPushButton("🗨️ New Chat")
        new_chat_btn.setToolTip("Create a new chat tab")
        new_chat_btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 8px 10px;
                border: 1px solid #1f2a37;
                background-color: #1a2130;
                color: #c0caf5;
                font-size: 12px;
                font-weight: bold;
                margin-bottom: 5px;
            }
            QPushButton:hover {
                border: 1px solid #7aa2f7;
                background-color: #1f2a37;
            }
            QPushButton:pressed {
                background-color: #2a3140;
            }
        """)
        new_chat_btn.clicked.connect(self.on_new_chat_clicked)
        layout.addWidget(new_chat_btn)

        # Analyze Project button
        analyze_btn = QPushButton("🔍 Analyze Project")
        analyze_btn.setToolTip("Analyze a project for code insights")
        analyze_btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 8px 10px;
                border: 1px solid #1f2a37;
                background-color: #1a2130;
                color: #c0caf5;
                font-size: 12px;
                font-weight: bold;
                margin-bottom: 5px;
            }
            QPushButton:hover {
                border: 1px solid #00ffa3;
                background-color: #1f2a37;
            }
            QPushButton:pressed {
                background-color: #2a3140;
            }
        """)
        analyze_btn.clicked.connect(self.on_analyze_clicked)
        layout.addWidget(analyze_btn)

        # Settings button
        settings_btn = QPushButton("⚙️ Settings")
        settings_btn.setToolTip("Open application settings")
        settings_btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 8px 10px;
                border: 1px solid #1f2a37;
                background-color: #1a2130;
                color: #c0caf5;
                font-size: 12px;
                font-weight: bold;
                margin-bottom: 10px;
            }
            QPushButton:hover {
                border: 1px solid #ffcc00;
                background-color: #1f2a37;
            }
            QPushButton:pressed {
                background-color: #2a3140;
            }
        """)
        settings_btn.clicked.connect(self.on_settings_clicked)
        layout.addWidget(settings_btn)

    def on_new_chat_clicked(self):
        """Handle new chat button click."""
        if self.main_window and hasattr(self.main_window, 'new_chat_tab'):
            self.main_window.new_chat_tab()

    def on_analyze_clicked(self):
        """Handle analyze project button click."""
        if self.main_window and hasattr(self.main_window, 'analyze_project'):
            self.main_window.analyze_project()

    def on_settings_clicked(self):
        """Handle settings button click."""
        if self.main_window and hasattr(self.main_window, 'open_settings'):
            self.main_window.open_settings()

    def show_empty_state(self):
        """Show empty state when no analysis has been performed."""
        self.clear_sidebar()

        empty_label = QLabel("No project analyzed yet.\nUse 'Tools → Analyze Project'\nto find entities.")
        empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_label.setWordWrap(True)
        empty_label.setStyleSheet("color: #9aa5ce; font-style: italic;")
        self.container_layout.addWidget(empty_label)

    def clear_sidebar(self):
        """Clear all widgets from the sidebar."""
        while self.container_layout.count():
            child = self.container_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def update_entities(self, analysis_results):
        """Update the sidebar with entities from analysis results."""
        self.analysis_context = analysis_results
        self.clear_sidebar()

        if not analysis_results or 'file_analysis' not in analysis_results:
            self.show_empty_state()
            return

        file_analysis = analysis_results['file_analysis']

        # Collect all entities
        all_classes = []
        all_functions = []

        for file_path, info in file_analysis.items():
            if info.get('type') != 'Python':
                continue

            # Add classes
            classes = info.get('classes', [])
            for cls in classes:
                all_classes.append({
                    'name': cls['name'],
                    'file': file_path,
                    'line': cls.get('line', 1),
                    'methods': cls.get('methods', [])
                })

            # Add functions (not methods)
            functions = info.get('functions', [])
            for func in functions:
                # Check if this function is a method (inside a class)
                is_method = False
                for cls in classes:
                    if func['name'] in cls.get('methods', []):
                        is_method = True
                        break

                if not is_method:
                    all_functions.append({
                        'name': func['name'],
                        'file': file_path,
                        'line': func.get('line', 1),
                        'args': func.get('args', [])
                    })

        # Display classes section
        if all_classes:
            self.add_entity_section("Classes", all_classes, "class")

        # Display functions section
        if all_functions:
            self.add_entity_section("Functions", all_functions, "function")

        # Add stretch to push content to top
        self.container_layout.addStretch()

    def add_entity_section(self, title, entities, entity_type):
        """Add a section of entity buttons."""
        # Section header
        header = QLabel(f"{title} ({len(entities)})")
        header.setStyleSheet("font-weight: bold; color: #7aa2f7; margin-top: 10px;")
        self.container_layout.addWidget(header)

        # Entity buttons
        for entity in entities[:20]:  # Limit to 20 entities per section
            btn = self.create_entity_button(entity, entity_type)
            self.container_layout.addWidget(btn)

        if len(entities) > 20:
            more_label = QLabel(f"... and {len(entities) - 20} more")
            more_label.setStyleSheet("color: #9aa5ce; font-style: italic;")
            self.container_layout.addWidget(more_label)

    def create_entity_button(self, entity, entity_type):
        """Create a button for an entity."""
        if entity_type == "class":
            display_name = f"📦 {entity['name']}"
            tooltip = f"Class: {entity['name']}\nFile: {entity['file']}\nLine: {entity['line']}\nMethods: {len(entity['methods'])}"
        else:  # function
            display_name = f"⚡ {entity['name']}"
            tooltip = f"Function: {entity['name']}\nFile: {entity['file']}\nLine: {entity['line']}\nArgs: {', '.join(entity['args']) if entity['args'] else 'None'}"

        btn = QPushButton(display_name)
        btn.setToolTip(tooltip)
        btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 5px 8px;
                border: 1px solid #1f2a37;
                background-color: #1a2130;
                color: #c0caf5;
                font-size: 11px;
            }
            QPushButton:hover {
                border: 1px solid #7aa2f7;
                background-color: #1f2a37;
            }
            QPushButton:pressed {
                background-color: #2a3140;
            }
        """)

        # Connect click handler
        btn.clicked.connect(lambda: self.on_entity_clicked(entity, entity_type))

        return btn

    def on_entity_clicked(self, entity, entity_type):
        """Handle entity button click."""
        # For now, just show information. In a full implementation,
        # this could navigate to the entity in an editor or show details
        info_text = f"**{entity_type.title()}:** {entity['name']}\n"
        info_text += f"**File:** {entity['file']}\n"
        info_text += f"**Line:** {entity['line']}\n"

        if entity_type == "class" and entity.get('methods'):
            info_text += f"**Methods:** {', '.join(entity['methods'])}\n"
        elif entity_type == "function" and entity.get('args'):
            info_text += f"**Arguments:** {', '.join(entity['args'])}\n"

        # Call main window method to show entity info
        if self.main_window and hasattr(self.main_window, 'show_entity_info'):
            self.main_window.show_entity_info(info_text)

# -------------------------
# Chat Tab
# -------------------------
class ChatTab(QWidget):
    def __init__(self, settings, model="deepseek-coder:6.7b", analysis_context=None):
        super().__init__()
        self.settings = settings
        self.model = model
        self.analysis_context = analysis_context  # Store analysis context for follow-up questions
        layout = QVBoxLayout(self)

        # Model selection row
        top_bar = QHBoxLayout()
        self.model_label = QLabel("Model:")
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)  # allow typing custom names
        self.model_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)

        # Try dynamic models from Ollama, fallback to a small default list
        dynamic_models = get_ollama_models(self.settings.get("ollama_path", "ollama"))
        default_models = [
            "deepseek-coder:6.7b",
            "llama3:8b",
            "mistral:7b",
            "phi3:mini",
            "qwen2:7b",
        ]
        models = dynamic_models or default_models
        self.model_combo.addItems(models)
        # Ensure current model is present and selected
        if model in models:
            self.model_combo.setCurrentText(model)
        else:
            self.model_combo.addItem(model)
            self.model_combo.setCurrentText(model)

        # Easier to open: clicking label also opens the dropdown
        def open_models_popup(event):
            self.model_combo.showPopup()
        self.model_label.mousePressEvent = open_models_popup

        # Add a Refresh button for reloading installed models
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setToolTip("Refresh installed models from Ollama")
        self.refresh_btn.clicked.connect(self.refresh_models)

        self.model_combo.currentTextChanged.connect(self.on_model_changed)
        top_bar.addWidget(self.model_label)
        top_bar.addWidget(self.model_combo, 1)
        top_bar.addWidget(self.refresh_btn)
        layout.addLayout(top_bar)

        self.chat_area = QTextEdit()
        self.chat_area.setReadOnly(True)
        layout.addWidget(self.chat_area)

        # Apply syntax highlighter - DISABLED: causes gibberish in AI responses
        # self.highlighter = CodeHighlighter(self.chat_area.document(), language="python")

        self.typing_label = QLabel("")
        layout.addWidget(self.typing_label)

        input_layout = QHBoxLayout()
        self.input_box = QLineEdit()
        self.send_btn = QPushButton("Send")
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)  # Initially disabled
        self.clear_btn = QPushButton("Clear History")
        self.scan_btn = QPushButton("Scan Project")
        self.cancel_scan_btn = QPushButton("Cancel Scan")
        self.cancel_scan_btn.setEnabled(False)
        input_layout.addWidget(self.input_box)
        input_layout.addWidget(self.send_btn)
        input_layout.addWidget(self.stop_btn)
        input_layout.addWidget(self.clear_btn)
        input_layout.addWidget(self.scan_btn)
        input_layout.addWidget(self.cancel_scan_btn)
        layout.addLayout(input_layout)

        # Add analysis-specific buttons if we have analysis context
        if self.analysis_context:
            self.edit_file_btn = QPushButton("Edit File")
            self.reanalyze_btn = QPushButton("Re-analyze")
            input_layout.addWidget(self.edit_file_btn)
            input_layout.addWidget(self.reanalyze_btn)
            
            # Connect analysis buttons
            self.edit_file_btn.clicked.connect(self.edit_file)
            self.reanalyze_btn.clicked.connect(self.reanalyze_project)

        # Connect buttons
        self.scan_btn.clicked.connect(self.select_and_scan_project)
        self.cancel_scan_btn.clicked.connect(self.cancel_scan)

    def append_stream_char(self, c: str):
        if not c:
            return
        # Ensure we always append at the end and keep the view scrolled
        cursor = self.chat_area.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.chat_area.setTextCursor(cursor)
        self.chat_area.insertPlainText(c)
        self.chat_area.ensureCursorVisible()

    def on_model_changed(self, text: str):
        self.model = text.strip() if text.strip() else self.model

    def refresh_models(self):
        # Remember current text to preserve user selection if possible
        current = self.model_combo.currentText().strip()
        ollama_path = self.settings.get("ollama_path", "ollama")
        models = get_ollama_models(ollama_path)
        if not models:
            # Keep existing if none found
            return
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItems(models)
        # Restore selection if still present, else keep current text as custom
        if current in models:
            self.model_combo.setCurrentText(current)
        else:
            if current:
                self.model_combo.addItem(current)
                self.model_combo.setCurrentText(current)
        self.model_combo.blockSignals(False)
        # Immediately show the popup so it's easy to choose
        self.model_combo.showPopup()

    def scan_project(self):
        """Scan the project directory and display results in chat."""
        try:
            # Assume project root is the parent directory of ChugaGPT
            project_root = self.settings.get("project_root", "..")
            scanner = ProjectScanner(project_root)
            results = scanner.scan_directory()
            formatted_results = format_scan_results(results)

            # Display in chat area
            self.chat_area.append(f"<b style='color:#66d9ef;'>[Project Scanner]</b>\n")
            self.chat_area.append(formatted_results)
            self.chat_area.append("\n")
        except Exception as e:
            self.chat_area.append(f"<b style='color:#ff4444;'>[Scan Error]</b> {str(e)}\n")

    def select_and_scan_project(self):
        """Allow user to select a project directory and scan it."""
        from PySide6.QtWidgets import QFileDialog
        directory = QFileDialog.getExistingDirectory(self, "Select Project Directory")
        if directory:
            self.settings["project_root"] = directory
            save_settings(self.settings)
            self.scan_project_with_analyzer(directory)

    def scan_project_with_analyzer(self, project_root=None):
        """Scan the project directory with advanced analysis and display results in chat."""
        try:
            if project_root is None:
                project_root = self.settings.get("project_root", "..")
            
            self.scan_btn.setEnabled(False)
            self.cancel_scan_btn.setEnabled(True)
            
            from scanner import ProjectAnalyzer
            self.scanner = ProjectAnalyzer(project_root)
            
            # Connect progress callback
            def progress_callback(message):
                self.chat_area.append(f"<b style='color:#66d9ef;'>[Progress]</b> {message}\n")
                # Scroll to bottom
                cursor = self.chat_area.textCursor()
                cursor.movePosition(cursor.MoveOperation.End)
                self.chat_area.setTextCursor(cursor)
            
            results = self.scanner.analyze_project(progress_callback)
            formatted_results = self.scanner.format_analysis_results(results)

            # Display in chat area
            self.chat_area.append(f"<b style='color:#66d9ef;'>[Project Analyzer]</b>\n")
            self.chat_area.append(formatted_results)
            self.chat_area.append("\n")
            
        except Exception as e:
            self.chat_area.append(f"<b style='color:#ff4444;'>[Analysis Error]</b> {str(e)}\n")
        finally:
            self.scan_btn.setEnabled(True)
            self.cancel_scan_btn.setEnabled(False)

    def cancel_scan(self):
        """Cancel the ongoing scan operation."""
        if hasattr(self, 'scanner') and self.scanner:
            self.scanner.cancel_scan()
            self.cancel_scan_btn.setEnabled(False)
            self.scan_btn.setEnabled(True)
            self.chat_area.append("<b style='color:#ffaa00;'>[Scan Cancelled]</b>\n")
    def stop_generation(self):
        """Stop the ongoing AI generation."""
        if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
            self.worker.stop_generation()
            self.stop_btn.setEnabled(False)
            self.send_btn.setEnabled(True)
            self.chat_area.append("[Generation Stopped]\n")
    
    def edit_file(self):
        """Open a file for editing based on analysis context."""
        if not self.analysis_context:
            return
            
        # Get list of files from analysis
        file_analysis = self.analysis_context.get('file_analysis', {})
        file_paths = list(file_analysis.keys())
        
        if not file_paths:
            self.chat_area.append("<b style='color:#ff4444;'>[Error]</b> No files found in analysis\n")
            return
            
        # For now, just show a simple file selection (could be improved with a proper dialog)
        file_list = "\n".join([f"{i+1}. {path}" for i, path in enumerate(file_paths[:10])])
        self.chat_area.append(f"<b style='color:#66d9ef;'>[Available Files]</b>\n{file_list}\n")
        self.chat_area.append("<b style='color:#ffaa00;'>[Note]</b> Use the chat to specify which file to edit\n")
    
    def reanalyze_project(self):
        """Re-run analysis on the project."""
        if not self.analysis_context:
            return
            
        # Get the project path from context
        project_path = self.analysis_context.get('project_path', '')
        if not project_path:
            self.chat_area.append("<b style='color:#ff4444;'>[Error]</b> Project path not found\n")
            return
            
        self.chat_area.append(f"<b style='color:#66d9ef;'>[Re-analysis]</b> Starting re-analysis of {project_path}\n")
        
        # Re-run analysis (similar to scan_project_with_analyzer)
        try:
            from scanner import ProjectAnalyzer
            analyzer = ProjectAnalyzer(project_path)
            
            # Connect progress callback
            def progress_callback(message):
                self.chat_area.append(f"<b style='color:#66d9ef;'>[Progress]</b> {message}\n")
                # Scroll to bottom
                cursor = self.chat_area.textCursor()
                cursor.movePosition(cursor.MoveOperation.End)
                self.chat_area.setTextCursor(cursor)
            
            results = analyzer.analyze_project(progress_callback)
            formatted_results = analyzer.format_analysis_results(results)
            
            self.chat_area.append(f"<b style='color:#66d9ef;'>[Re-analysis Complete]</b>\n")
            self.chat_area.append(formatted_results)
            self.chat_area.append("\n")
            
            # Update analysis context
            self.analysis_context = results
            
        except Exception as e:
            self.chat_area.append(f"<b style='color:#ff4444;'>[Re-analysis Error]</b> {str(e)}\n")
