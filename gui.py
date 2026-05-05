from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
    QPushButton, QLabel, QComboBox, QDialog, QFormLayout,
    QSpinBox, QCheckBox, QDialogButtonBox, QFileDialog,
    QScrollArea, QGroupBox, QFrame, QMessageBox
)
from PySide6.QtGui import QColor, QTextCharFormat, QFont, QSyntaxHighlighter
from PySide6.QtCore import Qt, QEvent, QPoint, Signal
from logic import OllamaTypingWorker, TextChangeMonitor
from settings import load_settings, save_settings
from history import save_history
from utils import get_ollama_models
from scanner import ProjectScanner, format_scan_results
from code_writer import CodeWriter
from code_writer_dialog import CodeWriterDialog
from completion import CompletionEngine, CompletionSuggestion
import re

# -------------------------
# Syntax Highlighter
# -------------------------
class SyntaxHighlighter(QSyntaxHighlighter):
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
            ] #
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

        # Reset formatting states for new response
        self.is_thinking = False
        self.is_answer = False
        self.pending_text = ""
        self._answer_started = False

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

        self.allow_long_analysis = QCheckBox("Allow Long Analysis")
        self.allow_long_analysis.setChecked(settings.get("allow_long_analysis", False))
        self.allow_long_analysis.setToolTip("Enable unlimited timeout for AI analyses (no timeout)")
        layout.addRow(self.allow_long_analysis)

        self.enable_completion = QCheckBox("Enable Code Completion")
        self.enable_completion.setChecked(settings.get("enable_completion", False))
        self.enable_completion.setToolTip("Enable real-time code completion suggestions")
        layout.addRow(self.enable_completion)

        # Model Provider Selection
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["ollama", "openai", "anthropic", "google"])
        current_provider = settings.get("model_provider", "ollama")
        self.provider_combo.setCurrentText(current_provider)
        self.provider_combo.currentTextChanged.connect(self.on_provider_changed)
        layout.addRow("Model Provider:", self.provider_combo)

        # Model selection (dynamic based on provider)
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self._update_models_for_provider(current_provider)
        current_model = settings.get("model", "phi3:mini")
        if current_model in [self.model_combo.itemText(i) for i in range(self.model_combo.count())]:
            self.model_combo.setCurrentText(current_model)
        layout.addRow("Model:", self.model_combo)

        # API Key inputs (conditional on provider)
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setText(settings.get(f"{current_provider}_api_key", ""))
        self.api_key_label = QLabel("API Key:")
        layout.addRow(self.api_key_label, self.api_key_input)

        self.language_combo = QComboBox()
        self.language_combo.addItems(["english", "spanish", "french", "german", "chinese", "japanese", "korean"])
        current_lang = settings.get("language", "english")
        if current_lang in ["english", "spanish", "french", "german", "chinese", "japanese", "korean"]:
            self.language_combo.setCurrentText(current_lang)
        layout.addRow("Response Language:", self.language_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def browse_path(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select Ollama Executable")
        if file:
            self.path_input.setText(file)

    def on_provider_changed(self, provider):
        """Update UI based on selected provider"""
        self._update_models_for_provider(provider)
        
        # Update API key field
        self.api_key_input.setText("")
        if provider != "ollama":
            self.api_key_label.setVisible(True)
            self.api_key_input.setVisible(True)
        else:
            self.api_key_label.setVisible(False)
            self.api_key_input.setVisible(False)

    def _update_models_for_provider(self, provider):
        """Update model list based on provider"""
        self.model_combo.clear()
        
        if provider == "ollama":
            try:
                from utils import get_ollama_models
                models = get_ollama_models("ollama")
                if models:
                    self.model_combo.addItems(models)
                else:
                    self.model_combo.addItems(["phi3:mini", "llama3:8b", "mistral:7b"])
            except Exception:
                self.model_combo.addItems(["phi3:mini", "llama3:8b", "mistral:7b"])
        elif provider == "openai":
            self.model_combo.addItems(["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"])
        elif provider == "anthropic":
            self.model_combo.addItems(["claude-3-5-sonnet-20241022", "claude-3-opus-20240229", "claude-3-haiku-20240307"])
        elif provider == "google":
            self.model_combo.addItems(["gemini-2.0-flash-exp", "gemini-1.5-pro", "gemini-1.5-flash"])

# -------------------------
# Entity Sidebar
# -------------------------
class EntitySidebar(QWidget):
    """Sidebar widget that displays shortcut buttons for found entities and skills."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.analysis_context = None
        self.main_window = parent  # Store reference to main window
        self.skill_loader = None
        self.init_ui()
        self.load_skills()

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
                border: 1px solid #f1f5f9;
                background-color: #ffffff;
                color: #202123;
                font-size: 14px;
                border-radius: 8px;
                margin-bottom: 5px;
            }
            QPushButton:hover {
                border: 1px solid #10a37f;
                background-color: #f7f7f8;
            }
            QPushButton:pressed {
                background-color: #ebeef5;
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
                border: 1px solid #f1f5f9;
                background-color: #ffffff;
                color: #202123;
                font-size: 14px;
                border-radius: 8px;
                margin-bottom: 5px;
            }
            QPushButton:hover {
                border: 1px solid #10a37f;
                background-color: #f7f7f8;
            }
            QPushButton:pressed {
                background-color: #ebeef5;
            }
        """)
        analyze_btn.clicked.connect(self.on_analyze_clicked)
        layout.addWidget(analyze_btn)

        # Teams button (Multi-Agent)
        teams_btn = QPushButton("🤖 AI Teams")
        teams_btn.setToolTip("Setup multi-agent teams")
        teams_btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 8px 10px;
                border: 1px solid #f1f5f9;
                background-color: #ffffff;
                color: #202123;
                font-size: 14px;
                border-radius: 8px;
                margin-bottom: 5px;
            }
            QPushButton:hover {
                border: 1px solid #ab68ff;
                background-color: #f7f7f8;
                color: #ab68ff;
            }
            QPushButton:pressed {
                background-color: #ab68ff;
                color: #ffffff;
            }
        """)
        teams_btn.clicked.connect(self.on_teams_clicked)
        layout.addWidget(teams_btn)

        # Skills button
        skills_btn = QPushButton("🎯 Skills")
        skills_btn.setToolTip("Browse and execute available skills")
        skills_btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 8px 10px;
                border: 1px solid #f1f5f9;
                background-color: #ffffff;
                color: #202123;
                font-size: 14px;
                border-radius: 8px;
                margin-bottom: 5px;
            }
            QPushButton:hover {
                border: 1px solid #ab68ff;
                background-color: #f7f7f8;
                color: #ab68ff;
            }
            QPushButton:pressed {
                background-color: #ab68ff;
                color: #ffffff;
            }
        """)
        skills_btn.clicked.connect(self.on_skills_clicked)
        layout.addWidget(skills_btn)

        # Task Agent button
        task_btn = QPushButton("🚀 Task Agent")
        task_btn.setToolTip("Run background exploration tasks")
        task_btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 8px 10px;
                border: 1px solid #f1f5f9;
                background-color: #ffffff;
                color: #202123;
                font-size: 14px;
                border-radius: 8px;
                margin-bottom: 5px;
            }
            QPushButton:hover {
                border: 1px solid #00d9ff;
                background-color: #f7f7f8;
                color: #00d9ff;
            }
            QPushButton:pressed {
                background-color: #00d9ff;
                color: #ffffff;
            }
        """)
        task_btn.clicked.connect(self.on_task_agent_clicked)
        layout.addWidget(task_btn)

        # Settings button
        settings_btn = QPushButton("⚙️ Settings")
        settings_btn.setToolTip("Open application settings")
        settings_btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 8px 10px;
                border: 1px solid #f1f5f9;
                background-color: #ffffff;
                color: #202123;
                font-size: 14px;
                border-radius: 8px;
                margin-bottom: 10px;
            }
            QPushButton:hover {
                border: 1px solid #20a37f;
                background-color: #f7f7f8;
                color: #209fb2;
            }
            QPushButton:pressed {
                background-color: #20a37f;
                color: #ffffff;
            }
        """)
        settings_btn.clicked.connect(self.on_settings_clicked)
        layout.addWidget(settings_btn)

    def load_skills(self):
        """Load available skills from the skills directory."""
        try:
            from skills import get_skill_loader
            import os
            root_path = os.path.join(os.path.dirname(__file__), ".")
            self.skill_loader = get_skill_loader(root_path)
        except Exception as e:
            print(f"Error loading skills: {e}")
            self.skill_loader = None

    def on_skills_clicked(self):
        """Handle skills button click - show available skills."""
        if not self.skill_loader:
            self.load_skills()
        
        if not self.skill_loader or not self.skill_loader.get_available_skills():
            if self.main_window and hasattr(self.main_window, 'show_entity_info'):
                self.main_window.show_entity_info("**Skills:** No skills loaded.\n\nAdd skill definitions to the `.skills/` directory.")
            return
        
        # Show skills help in chat
        help_text = self.skill_loader.get_skill_help()
        if self.main_window and hasattr(self.main_window, 'show_entity_info'):
            self.main_window.show_entity_info(help_text)

    def on_teams_clicked(self):
        """Handle teams button click - open team setup dialog."""
        try:
            from team_dialog import TeamDialog
            dialog = TeamDialog(self)
            dialog.exec()
        except Exception as e:
            print(f"Team dialog error: {e}")
            if self.main_window and hasattr(self.main_window, 'show_entity_info'):
                self.main_window.show_entity_info(f"**Teams Error:** {e}")

    def on_task_agent_clicked(self):
        """Handle task agent button click - open task agent dialog."""
        try:
            from task_agent_dialog import TaskAgentDialog
            dialog = TaskAgentDialog(self, self.main_window.settings if self.main_window else None)
            dialog.exec()
        except Exception as e:
            print(f"Task agent dialog error: {e}")
            if self.main_window and hasattr(self.main_window, 'show_entity_info'):
                self.main_window.show_entity_info(f"**Task Agent Error:** {e}")

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

    def clear_chat_and_sidebar(self, tab):
        """Clear the chat area and reset the sidebar to empty state."""
        tab.chat_area.clear()
        self.sidebar.show_empty_state()
        # Reset formatting states
        tab.is_thinking = False
        tab.is_answer = False
        tab.pending_text = ""

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
                border: 1px solid #f1f5f9;
                background-color: #ffffff;
                color: #202123;
                font-size: 14px;
            }
            QPushButton:hover {
                border: 1px solid #10a37f;
                background-color: #ebeef5;
                color: #209fb2;
            }
            QPushButton:pressed {
                background-color: #ebeef5;
                color: #20a37f;
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

        # Reset formatting states
        tab.is_thinking = False
        tab.is_answer = False
        tab.pending_text = ""

        # Call main window method to show entity info
        if self.main_window and hasattr(self.main_window, 'show_entity_info'):
            self.main_window.show_entity_info(info_text)

# -------------------------
# Chat Tab
# -------------------------
class ChatTab(QWidget):
    send_requested = Signal()
    is_thinking = False
    pending_text = ""
    is_answer = False

    # Ensure methods exist before they're connected in __init__
    def append_stream_char(self, c: str):
        if not c:
            return
        # Accumulate character in pending text
        self.pending_text += c
        
        # Check for thinking tags
        if "<ThoughtProcess>" in self.pending_text and not self.is_thinking:
            # Start of thinking section
            self.is_thinking = True
            self.is_answer = False
            # Insert the text before <ThoughtProcess> normally
            before_tag = self.pending_text.split("<ThoughtProcess>")[0]
            if before_tag:
                cursor = self.chat_area.textCursor()
                cursor.movePosition(cursor.MoveOperation.End)
                self.chat_area.setTextCursor(cursor)
                if self.is_answer:
                    self.chat_area.insertHtml(f'<b>{before_tag}</b>')
                else:
                    self.chat_area.insertPlainText(before_tag)
            # Reset pending and start thinking
            self.pending_text = ""
            return
        elif "</ThoughtProcess>" in self.pending_text and self.is_thinking:
            # End of thinking section
            self.is_thinking = False
            self.is_answer = True  # Now in answer mode
            # Insert the thinking text in italic
            thinking_content = self.pending_text.split("</ThoughtProcess>")[0]
            if thinking_content:
                cursor = self.chat_area.textCursor()
                cursor.movePosition(cursor.MoveOperation.End)
                self.chat_area.setTextCursor(cursor)
                self.chat_area.insertHtml(f'<i style="color:gray;">{thinking_content}</i>')
            # Reset pending
            self.pending_text = ""
            return
        elif "<Response>" in self.pending_text and self.is_answer:
            # Start of response section - remove the tag and continue
            self.pending_text = self.pending_text.replace("<Response>", "")
            return
        
        # If we're in thinking mode, accumulate until end tag
        if self.is_thinking:
            return
        
        # Normal text insertion, with formatting based on mode
        cursor = self.chat_area.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.chat_area.setTextCursor(cursor)
        if self.is_answer:
            self.chat_area.insertHtml(f'<b>{c}</b>')
        else:
            self.chat_area.insertPlainText(c)
        self.pending_text = ""  # Reset since we inserted
        self.chat_area.ensureCursorVisible()

    def on_model_changed(self, text: str):
        self.model = text.strip() if text.strip() else self.model
        try:
            if hasattr(self, 'completion_engine') and self.completion_engine:
                self.completion_engine.model = self.model
        except Exception:
            pass

    def refresh_models(self):
        current = self.model_combo.currentText().strip()
        ollama_path = self.settings.get("ollama_path", "ollama")
        models = get_ollama_models(ollama_path)
        if not models:
            return
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItems(models)
        if current in models:
            self.model_combo.setCurrentText(current)
        else:
            if current:
                self.model_combo.addItem(current)
                self.model_combo.setCurrentText(current)
        self.model_combo.blockSignals(False)
        self.model_combo.showPopup()

    def __init__(self, settings, model="phi3:mini", analysis_context=None):
        super().__init__()
        self.settings = settings
        self.model = model
        self.analysis_context = analysis_context  # Store analysis context for follow-up questions
        self.task_agent = None
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
        self.chat_area.setAcceptRichText(True)
        # ChatGPT-like chat area styling
        self.chat_area.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                color: #202123;
                border: 1px solid #e5e5e5;
                border-radius: 8px;
                padding: 16px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                font-size: 14px;
                line-height: 1.5;
                selection-background-color: #10a37f;
            }
            .thinking-section {
                background-color: #f8f9fa;
                border: 2px solid #6c757d;
                border-radius: 8px;
                margin: 8px 0;
                padding: 12px;
            }
            .thinking-header {
                color: #495057;
                font-weight: bold;
                font-size: 13px;
                margin-bottom: 8px;
            }
            .thinking-content {
                color: #6c757d;
                font-style: italic;
                font-size: 13px;
                line-height: 1.4;
            }
            .answer-section {
                background-color: #ffffff;
                border: 2px solid #10a37f;
                border-radius: 8px;
                margin: 8px 0;
                padding: 12px;
            }
            .answer-header {
                color: #10a37f;
                font-weight: bold;
                font-size: 13px;
                margin-bottom: 8px;
            }
            .answer-content {
                color: #202123;
                font-weight: normal;
                font-size: 14px;
                line-height: 1.5;
            }
        """)
        layout.addWidget(self.chat_area)

        # Apply syntax highlighter - DISABLED: causes gibberish in AI responses
        # self.highlighter = SyntaxHighlighter(self.chat_area)

        self.typing_label = QLabel("")
        layout.addWidget(self.typing_label)

        input_layout = QHBoxLayout()
        # Attach button
        self.attach_btn = QPushButton("📎")
        self.attach_btn.setToolTip("Attach a file")
        self.attach_btn.setStyleSheet("""
            QPushButton {
                padding: 12px 16px;
                border: 1px solid #e5e5e5;
                background-color: #ffffff;
                color: #6b7280;
                border-radius: 8px;
                font-size: 16px;
            }
            QPushButton:hover {
                border: 1px solid #10a37f;
                background-color: #f7f7f8;
                color: #10a37f;
            }
        """)
        self.attach_btn.clicked.connect(self.attach_file)

        # Multi-line chat input - FIXED HEIGHT to prevent squeezing
        self.input_box = QTextEdit()
        try:
            self.input_box.setPlaceholderText("Type a message... Enter to send, Shift+Enter for newline")
        except Exception:
            pass
        self.input_box.setFixedHeight(80)  # Fixed height - won't squeeze
        self.input_box.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)  # Allow scrolling if text exceeds
        self.input_box.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                color: #202123;
                border: 1px solid #e5e5e5;
                border-radius: 8px;
                padding: 12px 16px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                font-size: 14px;
                line-height: 1.4;
            }
        """)
        # Always install event filter for Enter-to-send UX
        try:
            self.input_box.installEventFilter(self)
        except Exception:
            pass

        # Primary chat actions
        self.send_btn = QPushButton("➤ Send")
        self.send_btn.setToolTip("Send message (Enter)")
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #10a37f;
                color: #ffffff;
                padding: 12px 16px;
                font-weight: 600;
                border: none;
                border-radius: 8px;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #19c37d; }
            QPushButton:disabled { background-color: #e5e5e5; color: #9ca3af; }
        """)

        # Send is wired by ChatApp using send_requested; no local handler here.

        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.setToolTip("Stop generation")
        self.stop_btn.setEnabled(False)  # Initially disabled
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: #ffffff;
                padding: 12px 16px;
                font-weight: 600;
                border: none;
                border-radius: 8px;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #dc2626; }
            QPushButton:disabled { background-color: #e5e5e5; color: #9ca3af; }
        """)
        self.stop_btn.clicked.connect(self.stop_generation)

        self.clear_btn = QPushButton("Clear History")
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #6b7280;
                border: 1px solid #e5e5e5;
                padding: 12px 16px;
                border-radius: 8px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #f7f7f8;
                border-color: #d1d5db;
            }
        """)

        # Add Write Code button
        self.write_code_btn = QPushButton("💾 Write Code")
        self.write_code_btn.setToolTip("Write code from chat to a file")
        self.write_code_btn.setStyleSheet("""
            QPushButton {
                background-color: #10a37f;
                color: #ffffff;
                padding: 12px 16px;
                font-weight: 600;
                border: none;
                border-radius: 8px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #19c37d;
            }
            QPushButton:disabled {
                background-color: #e5e5e5;
                color: #9ca3af;
            }
        """)
        self.write_code_btn.clicked.connect(self.write_code_to_file)

        # Write Code button should be after Send, Stop
        input_layout.addWidget(self.attach_btn)
        input_layout.addWidget(self.input_box, 1)
        input_layout.addWidget(self.stop_btn)
        input_layout.addWidget(self.send_btn)
        input_layout.addWidget(self.clear_btn)
        input_layout.addWidget(self.write_code_btn)

        # Assemble bottom input bar
        layout.addLayout(input_layout)

        # Fix layout: chat area stretches, input area stays fixed at bottom
        # Indices: 0=top_bar, 1=chat_area, 2=input_layout
        layout.setStretch(1, 1)  # chat_area (index 1) stretches
        layout.setStretch(2, 0)  # input_layout (index 2) fixed height

        # Reset formatting states for new response
        self.is_thinking = False
        self.is_answer = False
        self.pending_text = ""
        self._answer_started = False
        self.tool_context = ""  # Store tool execution context for follow-up questions

        # Initialize completion engine and floating suggestion widget if enabled
        if self.settings.get("enable_completion", False):
            try:
                self.completion_engine = CompletionEngine(self.settings.get("ollama_path", "ollama"), self.model)
                self.text_monitor = TextChangeMonitor(self.completion_engine)
                self.completion_widget = CompletionSuggestionWidget(self)
                self.completion_engine.suggestions_ready.connect(self.on_suggestions_ready)
                # QTextEdit does not have textChanged; use textChanged and pass current text
                self.input_box.textChanged.connect(lambda: self.on_input_edited(self.input_box.toPlainText()))
            except Exception as e:
                # Completion is optional; if initialization fails, continue without it
                self.completion_engine = None
                self.text_monitor = None
                self.completion_widget = None
        else:
            self.completion_engine = None
            self.text_monitor = None
            self.completion_widget = None

        # Add analysis-specific buttons if we have analysis context
        if self.analysis_context:
            self.edit_file_btn = QPushButton("Edit File")
            self.reanalyze_btn = QPushButton("Re-analyze")
            input_layout.addWidget(self.edit_file_btn)
            input_layout.addWidget(self.reanalyze_btn)

            # Connect analysis buttons
            self.edit_file_btn.clicked.connect(self.edit_file)
            self.reanalyze_btn.clicked.connect(self.reanalyze_project)

        # Connect buttons (Send/Stop handled in main via send_message; Stop connected there too)

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
            
            # Update analysis context
            self.analysis_context = results
            
        except Exception as e:
            self.chat_area.append(f"<b style='color:#ff4444;'>[Analysis Error]</b> {str(e)}\n")
        finally:
            if hasattr(self, 'scan_btn'):
                self.scan_btn.setEnabled(True)
            if hasattr(self, 'cancel_scan_btn'):
                self.cancel_scan_btn.setEnabled(False)

    def cancel_scan(self):
        """Cancel the ongoing scan operation."""
        if hasattr(self, 'scanner') and self.scanner:
            self.scanner.cancel_scan()
            if hasattr(self, 'cancel_scan_btn'):
                self.cancel_scan_btn.setEnabled(False)
            if hasattr(self, 'scan_btn'):
                self.scan_btn.setEnabled(True)
            self.chat_area.append("<b style='color:#ffaa00;'>[Scan Cancelled]</b>\n")

    def stop_generation(self):
        """Stop the ongoing AI generation."""
        if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
            self.worker.stop_generation()
            self.stop_btn.setEnabled(False)
        self.send_btn.setEnabled(True)
        self.chat_area.append("[Generation Stopped]\n")

    def write_code_to_file(self):
        """Open the Code Writer dialog using selected text or last code block."""
        try:
            # Prefer selected text in chat area
            cursor = self.chat_area.textCursor()
            selected = cursor.selectedText()
            # QTextEdit uses U+2029 paragraph separators in selectedText; normalize to newlines
            code = selected.replace('\u2029', '\n') if selected else ""
            language_hint = None

            # If nothing selected, try to extract the last fenced code block ```lang\n...\n```
            if not code:
                text = self.chat_area.toPlainText()
                matches = list(re.finditer(r"```(\w+)?\s*\n(.*?)```", text, re.DOTALL))
                if matches:
                    last = matches[-1]
                    language_hint = (last.group(1) or "").strip()
                    code = last.group(2)
                else:
                    # Fallback: use entire chat content
                    code = text

            # Normalize/detect language
            lang_map = {
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

            cw = CodeWriter(self)
            language = None
            if language_hint:
                language = lang_map.get(language_hint.lower())
            if not language:
                language = cw.detect_language_from_content(code)

            # Suggested filename
            ext = cw._get_language_extension(language or 'python')
            suggested = f"code_suggestion{ext}"

            # Open the dialog
            dlg = CodeWriterDialog(self, code_content=code, suggested_filename=suggested, language=language or 'python')

            def _on_written(file_path: str, success: bool):
                if success:
                    # Ask to delete backup now (accept changes)
                    reply = QMessageBox.question(
                        self,
                        "Accept Changes",
                        "Delete backup for this file now?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    if reply == QMessageBox.StandardButton.Yes:
                        cw.accept_changes(file_path)

            dlg.code_written.connect(_on_written)
            dlg.exec()
        except Exception as e:
            QMessageBox.critical(self, "Write Code Error", f"Failed to open code writer:\n{e}")
            
    def attach_file(self):
        """Attach a file and note it in the chat."""
        try:
            file_path, _ = QFileDialog.getOpenFileName(self, "Attach File")
            if file_path:
                self.chat_area.append(f"<b style='color:#9aa5ce;'>[Attached]</b> {file_path}\n")
        except Exception as e:
            self.chat_area.append(f"<b style='color:#ff4444;'>[Attach Error]</b> {e}\n")

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

    # ===== Completion integration (inside ChatTab) =====
    def on_input_edited(self, text: str):
        """Handle input edits to trigger completion updates."""
        if not getattr(self, 'text_monitor', None):
            return
        try:
            if hasattr(self.input_box, 'cursorPosition'):
                cursor_pos = self.input_box.cursorPosition()
            elif hasattr(self.input_box, 'textCursor'):
                cursor_pos = self.input_box.textCursor().position()
            else:
                cursor_pos = len(text or "")
            self.text_monitor.on_text_changed(text, cursor_pos)
        except Exception:
            pass

    def on_suggestions_ready(self, suggestions):
        """Display suggestions from the completion engine."""
        if not getattr(self, 'completion_widget', None):
            return
        try:
            if suggestions:
                pos = self._position_completion_widget()
                self.completion_widget.show_suggestions(suggestions, pos)
            else:
                self.completion_widget.hide_widget()
        except Exception:
            # Best effort: hide on any error
            self.completion_widget.hide_widget()

    def _position_completion_widget(self) -> QPoint:
        """Compute the on-screen position for the suggestion widget near the cursor."""
        rect = self.input_box.cursorRect() if hasattr(self.input_box, 'cursorRect') else self.input_box.rect()
        local = rect.bottomLeft()
        # Map from QLineEdit to ChatTab coordinate space and add a small vertical offset
        pt = self.input_box.mapTo(self, local)
        return QPoint(pt.x(), pt.y() + 8)

    def accept_completion(self, suggestion):
        """Accept a completion suggestion and insert into the input at the cursor."""
        try:
            # Support either object with .text or raw string
            text_to_insert = getattr(suggestion, 'text', None) or str(suggestion)
            if hasattr(self.input_box, 'text'):  # QLineEdit
                existing = self.input_box.text()
                pos = self.input_box.cursorPosition()
                new_text = existing[:pos] + text_to_insert + existing[pos:]
                self.input_box.setText(new_text)
                self.input_box.setCursorPosition(pos + len(text_to_insert))
            elif hasattr(self.input_box, 'toPlainText'):  # QTextEdit
                cursor = self.input_box.textCursor()
                cursor.insertText(text_to_insert)
                self.input_box.setTextCursor(cursor)
            if getattr(self, 'completion_widget', None):
                self.completion_widget.hide_widget()
        except Exception:
            pass

    def cleanup(self):
        """Cleanly stop all background workers related to this tab."""
        # Reset formatting states
        self.is_thinking = False
        self.is_answer = False
        self.pending_text = ""
        self._answer_started = False
        # Stop completion worker(s)
        try:
            if getattr(self, 'completion_engine', None):
                try:
                    self.completion_engine.stop_all()
                except Exception:
                    pass
        except Exception:
            pass
        # Stop any running long generation (OllamaTypingWorker)
        try:
            if getattr(self, 'worker', None) and self.worker.isRunning():
                self.worker.stop_generation()
                try:
                    self.worker.wait(2000)
                except Exception:
                    pass
        except Exception:
            pass

    def eventFilter(self, obj, event):
        """Keyboard handling for completion interactions."""
        if obj is self.input_box and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            # Enter to send, Shift+Enter for newline
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    return False  # allow newline
                # emit send request
                try:
                    self.send_requested.emit()
                    return True
                except Exception:
                    return False
            # Accept suggestion on Tab
            if key == Qt.Key.Key_Tab:
                if getattr(self, 'completion_widget', None) and self.completion_widget.isVisible():
                    self.completion_widget.accept_suggestion()
                    return True
            # Hide suggestions on Escape
            if key == Qt.Key.Key_Escape:
                if getattr(self, 'completion_widget', None):
                    self.completion_widget.hide_widget()
                    return True
            # Navigate suggestions with Up/Down
            if key == Qt.Key.Key_Down:
                if getattr(self, 'completion_widget', None) and self.completion_widget.isVisible():
                    self.completion_widget.next_suggestion()
                    return True
            if key == Qt.Key.Key_Up:
                if getattr(self, 'completion_widget', None) and self.completion_widget.isVisible():
                    self.completion_widget.previous_suggestion()
                    return True
        return super().eventFilter(obj, event)


# -------------------------
# File Editor Tab
# -------------------------
class FileEditorTab(QWidget):
    """A tab for editing files with syntax highlighting and basic operations."""

    def __init__(self, file_path=None, settings=None):
        super().__init__()
        self.settings = settings or {}
        self.file_path = file_path
        self.is_modified = False
        self.highlighter = None
        self.init_ui()

    def init_ui(self):
        """Initialize the file editor UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # File path display
        path_layout = QHBoxLayout()
        path_label = QLabel("File:")
        path_label.setStyleSheet("color: #9aa5ce; font-weight: bold; padding: 5px;")
        self.path_display = QLabel(self.file_path or "No file loaded")
        self.path_display.setStyleSheet("color: #c0caf5; padding: 5px; background-color: #1a2130; border: 1px solid #1f2a37;")
        path_layout.addWidget(path_label)
        path_layout.addWidget(self.path_display, 1)

        # Save button
        self.save_btn = QPushButton("💾 Save")
        self.save_btn.setToolTip("Save file (Ctrl+S)")
        self.save_btn.setStyleSheet("""
            QPushButton {
                padding: 6px 8px;
                background-color: #1a2130;
                color: #00ffa3;
                border: 1px solid #1f2a37;
                font-weight: bold;
                margin-left: 10px;
            }
            QPushButton:hover {
                border: 1px solid #00ffa3;
                background-color: #1f2a37;
            }
            QPushButton:disabled {
                color: #666;
                border: 1px solid #333;
            }
        """)
        self.save_btn.clicked.connect(self.save_file)
        self.save_btn.setEnabled(False)  # Initially disabled

        path_layout.addWidget(self.save_btn)
        layout.addLayout(path_layout)

        # Text editor area
        self.editor = QTextEdit()
        self.editor.setAcceptRichText(False)  # Plain text mode
        self.editor.textChanged.connect(self.on_text_changed)

        # Apply theme to editor
        font_size = int(self.settings.get("font_size", 14))
        self.editor.setStyleSheet(f"""
            QTextEdit {{
                background-color: #0f141a;
                color: #c0caf5;
                border: 1px solid #1f2a37;
                font-family: 'Fira Code', 'Consolas', monospace;
                font-size: {font_size}px;
                line-height: 1.4;
                selection-background-color: #7aa2f7;
            }}
        """)

        layout.addWidget(self.editor)

        # Status bar
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #9aa5ce; padding: 2px 5px; font-size: 11px;")

        self.line_col_label = QLabel("Ln 1, Col 1")
        self.line_col_label.setStyleSheet("color: #9aa5ce; padding: 2px 5px; font-size: 11px;")

        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.line_col_label)
        layout.addLayout(status_layout)

        # Load file if path provided
        if self.file_path:
            self.load_file()

    def load_file(self):
        """Load file content into the editor."""
        if not self.file_path:
            return

        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            self.editor.setPlainText(content)
            self.path_display.setText(self.file_path)
            self.status_label.setText("File loaded successfully")
            self.save_btn.setEnabled(False)
            self.is_modified = False

            # Apply syntax highlighting based on file extension
            self.apply_syntax_highlighting()

        except Exception as e:
            self.status_label.setText(f"Error loading file: {str(e)}")
            QMessageBox.critical(self, "File Error", f"Could not load file:\n{str(e)}")

    def save_file(self):
        """Save the current file content."""
        if not self.file_path:
            # If no file path, prompt for save location
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Save File", "", "All Files (*)"
            )
            if not file_path:
                return
            self.file_path = file_path
            self.path_display.setText(self.file_path)

        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                f.write(self.editor.toPlainText())

            self.status_label.setText("File saved successfully")
            self.save_btn.setEnabled(False)
            self.is_modified = False

        except Exception as e:
            self.status_label.setText(f"Error saving file: {str(e)}")
            QMessageBox.critical(self, "Save Error", f"Could not save file:\n{str(e)}")

    def on_text_changed(self):
        """Handle text changes in the editor."""
        if not self.is_modified:
            self.is_modified = True
            self.save_btn.setEnabled(True)
            self.status_label.setText("Modified - Unsaved changes")

        # Update line and column position
        cursor = self.editor.textCursor()
        line = cursor.blockNumber() + 1
        column = cursor.columnNumber() + 1
        self.line_col_label.setText(f"Ln {line}, Col {column}")

    def apply_syntax_highlighting(self):
        """Apply syntax highlighting based on file extension."""
        if not self.file_path:
            return

        # Determine language from file extension
        ext = self.file_path.split('.')[-1].lower()
        language_map = {
            'py': 'python',
            'js': 'javascript',
            'ts': 'typescript',
            'html': 'html',
            'css': 'css',
            'json': 'json',
            'md': 'markdown',
            'cpp': 'cpp',
            'c': 'c',
            'java': 'java'
        }

        language = language_map.get(ext, 'text')

        # Remove existing highlighter
        if self.highlighter:
            self.highlighter.setParent(None)

        # Apply new highlighter
        self.highlighter = SyntaxHighlighter(self.editor.document(), language=language)

    def set_file_path(self, file_path):
        """Set the file path and load the file."""
        self.file_path = file_path
        self.load_file()

    def get_content(self):
        """Get the current editor content."""
        return self.editor.toPlainText()

    def is_file_modified(self):
        """Check if the file has unsaved changes."""
        return self.is_modified

# -------------------------
# Completion Suggestion Widget
# -------------------------
class CompletionSuggestionWidget(QWidget):
    """Floating widget that displays code completion suggestions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.suggestions = []
        self.selected_index = 0
        self.parent_text_edit = parent
        self._build_ui()
        self.hide()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setMaximumHeight(200)

        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(0)
        self.scroll_area.setWidget(self.container)
        layout.addWidget(self.scroll_area)

        self.setStyleSheet("""
            CompletionSuggestionWidget {
                background-color: #1a2130;
                border: 1px solid #7aa2f7;
                border-radius: 4px;
            }
        """)
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

    def show_suggestions(self, suggestions, position: QPoint):
        """Render suggestions at the given position (in parent coordinates)."""
        self.suggestions = suggestions or []
        self.selected_index = 0
        # Clear old
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        # Add new
        for idx, s in enumerate(self.suggestions):
            display = getattr(s, 'display_text', None) or getattr(s, 'text', None) or str(s)
            btn = QPushButton(display)
            btn.setStyleSheet("""
                QPushButton {
                    text-align: left;
                    padding: 4px 8px;
                    border: none;
                    background-color: transparent;
                    color: #c0caf5;
                    font-family: 'Fira Code', 'Consolas', monospace;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #2a3140;
                }
            """)
            btn.clicked.connect(lambda _=False, i=idx: self.accept_suggestion(i))
            self.container_layout.addWidget(btn)
        if not self.suggestions:
            self.hide()
            return
        # Position and show
        self.move(position)
        self._apply_selection_styles()
        self.show()
        self.raise_()

    def _apply_selection_styles(self):
        for i in range(self.container_layout.count()):
            btn = self.container_layout.itemAt(i).widget()
            if not btn:
                continue
            is_selected = (i == self.selected_index)
            btn.setStyleSheet(f"""
                QPushButton {{
                    text-align: left;
                    padding: 4px 8px;
                    border: none;
                    background-color: {'#2a3140' if is_selected else 'transparent'};
                    color: #c0caf5;
                    font-family: 'Fira Code', 'Consolas', monospace;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    background-color: #2a3140;
                }}
            """)

    def accept_suggestion(self, index=None):
        if not self.suggestions:
            self.hide()
            return
        if index is None:
            index = self.selected_index
        index = max(0, min(index, len(self.suggestions) - 1))
        suggestion = self.suggestions[index]
        if self.parent() and hasattr(self.parent(), 'accept_completion'):
            self.parent().accept_completion(suggestion)
        self.hide()

    def next_suggestion(self):
        if not self.suggestions:
            return
        self.selected_index = (self.selected_index + 1) % len(self.suggestions)
        self._apply_selection_styles()

    def previous_suggestion(self):
        if not self.suggestions:
            return
        self.selected_index = (self.selected_index - 1) % len(self.suggestions)
        self._apply_selection_styles()

    def hide_widget(self):
        self.hide()

