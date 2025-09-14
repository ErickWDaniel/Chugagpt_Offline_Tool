import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QMenuBar, QMenu, QMessageBox, QTabWidget, QWidget, QHBoxLayout
from settings import load_settings, save_settings
from history import load_history, save_history
from gui import ChatTab, SettingsDialog, EntitySidebar
from logic import OllamaTypingWorker
from scanner import ProjectAnalyzer
from analysis_context import context_manager
from pathlib import Path
from PySide6.QtWidgets import QFileDialog, QProgressDialog
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QKeySequence, QAction

class AnalysisWorker(QThread):
    progress = Signal(str)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, project_path):
        super().__init__()
        self.project_path = project_path
        self.cancelled = False

    def cancel(self):
        """Cancel the analysis operation."""
        self.cancelled = True

    def run(self):
        try:
            analyzer = ProjectAnalyzer(self.project_path)
            results = analyzer.analyze_project(lambda msg: self.progress.emit(msg))
            if not self.cancelled:
                self.finished.emit(results)
        except Exception as e:
            if not self.cancelled:
                self.error.emit(str(e))

class ChatApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Offline ChugaGPT AI Tool")
        self.setGeometry(100, 100, 1000, 700)

        self.settings = load_settings()

        # Menu
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")
        
        # Add actions with shortcuts
        new_chat_action = QAction("New Chat", self)
        new_chat_action.setShortcut(QKeySequence("Ctrl+N"))
        new_chat_action.triggered.connect(self.new_chat_tab)
        file_menu.addAction(new_chat_action)
        
        analyze_action = QAction("Analyze Project", self)
        analyze_action.setShortcut(QKeySequence("Ctrl+P"))
        analyze_action.triggered.connect(self.analyze_project)
        file_menu.addAction(analyze_action)
        file_menu.addAction("Exit", self.close)

        tools_menu = menu_bar.addMenu("Tools")
        settings_menu = menu_bar.addMenu("Settings")
        help_menu = menu_bar.addMenu("Help")

        # Add analyze project action to Tools menu
        analyze_project_action = tools_menu.addAction("Analyze Project")
        analyze_project_action.triggered.connect(self.analyze_project)

        settings_action = settings_menu.addAction("Preferences")
        settings_action.triggered.connect(self.open_settings)
        help_menu.addAction("About", self.show_about)

        # Create main layout with sidebar and tabs
        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create sidebar
        self.sidebar = EntitySidebar(self)
        self.sidebar.setFixedWidth(250)
        main_layout.addWidget(self.sidebar)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        main_layout.addWidget(self.tabs)

        self.setCentralWidget(main_widget)
        self.new_chat_tab()

        # Apply theme once on startup
        self.apply_theme()

    def apply_theme(self):
        # Minimal Warp-like dark theme
        if not self.settings.get("dark_theme", True):
            self.setStyleSheet("")
            return
        font_size = int(self.settings.get("font_size", 14))
        base_bg = "#0b0f14"  # near-black blue
        panel_bg = "#0f141a"
        accent = "#7aa2f7"   # blue accent
        accent2 = "#00ffa3"  # green accent like cursor
        text_col = "#c0caf5"
        subtext = "#9aa5ce"
        btn_bg = "#1a2130"
        border = "#1f2a37"
        qss = f"""
            QMainWindow {{ background-color: {base_bg}; color: {text_col}; }}
            QWidget {{ color: {text_col}; font-size: {font_size}px; }}
            QTabWidget::pane {{ border: 1px solid {border}; background: {panel_bg}; }}
            QTabBar::tab {{ background: {btn_bg}; color: {subtext}; padding: 6px 12px; border: 1px solid {border}; border-bottom: none; }}
            QTabBar::tab:selected {{ background: {panel_bg}; color: {text_col}; }}
            QTextEdit {{ background-color: {panel_bg}; border: 1px solid {border}; selection-background-color: {accent}; }}
            QLineEdit {{ background-color: {panel_bg}; border: 1px solid {border}; padding: 6px; selection-background-color: {accent}; }}
            QPushButton {{ background-color: {btn_bg}; border: 1px solid {border}; padding: 6px 10px; color: {text_col}; }}
            QPushButton:hover {{ border: 1px solid {accent}; }}
            QLabel {{ color: {subtext}; }}
            QComboBox {{ background-color: {panel_bg}; border: 1px solid {border}; padding: 4px 6px; }}
            QComboBox QAbstractItemView {{ background: {panel_bg}; selection-background-color: {accent2}; }}
            QMenuBar {{ background: {panel_bg}; color: {text_col}; }}
            QMenuBar::item:selected {{ background: {btn_bg}; }}
            QMenu {{ background: {panel_bg}; color: {text_col}; border: 1px solid {border}; }}
            QMenu::item:selected {{ background: {btn_bg}; }}
            QScrollArea {{ background: {panel_bg}; border: none; }}
            QScrollBar:vertical {{ background: {panel_bg}; width: 12px; }}
            QScrollBar::handle:vertical {{ background: {btn_bg}; border-radius: 6px; }}
            QScrollBar::handle:vertical:hover {{ background: {accent2}; }}
            QTabBar::close-button {{ image: url(close.png); }}
            QTabBar::close-button:hover {{ background: {accent}; }}
        """
        self.setStyleSheet(qss)

    def new_chat_tab(self):
        tab = ChatTab(self.settings)
        self.tabs.addTab(tab, f"Chat {self.tabs.count()+1}")

        tab.send_btn.clicked.connect(lambda: self.send_message(tab))
        tab.input_box.returnPressed.connect(lambda: self.send_message(tab))
        tab.clear_btn.clicked.connect(lambda: tab.chat_area.clear())
        tab.stop_btn.clicked.connect(tab.stop_generation)

    def send_message(self, tab):
        text = tab.input_box.text().strip()
        if not text:
            return
        tab.chat_area.append(f"<b style='color:#ffcc00;'>You:</b> {text}\n")
        tab.input_box.clear()

        # Prepare the prompt with analysis context if available
        prompt = text
        if hasattr(tab, 'analysis_context') and tab.analysis_context:
            context = context_manager.get_context_for_chat()
            if context:
                prompt = f"{context}\n\nUser Question: {text}"

        # Show model label and start streaming directly under it
        tab.chat_area.append(f"<b style='color:#66d9ef;'>[{tab.model}]</b> ")
        tab.typing_label.setText(f"Typing with {tab.model}...")
        tab.worker = OllamaTypingWorker(tab.model, prompt, self.settings.get("ollama_path", "ollama"))
        # Stream characters into the chat area safely
        tab.worker.new_char.connect(tab.append_stream_char)
        tab.worker.finished_signal.connect(lambda: (tab.chat_area.insertPlainText("\n"), tab.typing_label.setText("")))
        tab.worker.start()
        save_history(text, tab.model)

    def open_settings(self):
        dialog = SettingsDialog(self, self.settings)
        if dialog.exec():
            self.settings["ollama_path"] = dialog.path_input.text()
            self.settings["font_size"] = dialog.font_size_spin.value()
            self.settings["dark_theme"] = dialog.dark_mode.isChecked()
            save_settings(self.settings)
            self.apply_theme()

    def show_about(self):
        QMessageBox.information(self, "About", "Offline Erick AI Tool\nWarp Style GUI\nSupports multiple chat tabs.")

    def analyze_project(self):
        """Analyze the project using offline AI and provide suggestions."""
        # Ask user to select project directory
        directory = QFileDialog.getExistingDirectory(self, "Select Project Directory to Analyze")
        if not directory:
            return

        # Create progress dialog
        progress = QProgressDialog("Analyzing project...", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.show()

        # Create analysis worker
        self.analysis_worker = AnalysisWorker(directory)
        self.analysis_worker.progress.connect(progress.setLabelText)
        self.analysis_worker.finished.connect(lambda results: self.on_analysis_finished(results, directory, progress))
        self.analysis_worker.error.connect(lambda err: self.on_analysis_error(err, progress))

        # Connect cancel button
        progress.canceled.connect(self.analysis_worker.cancel)

        # Start analysis
        self.analysis_worker.start()

    def on_analysis_finished(self, results, project_path, progress):
        progress.close()

        # Save analysis context
        context_manager.save_analysis_context(results, project_path)

        # Update sidebar with found entities
        self.sidebar.update_entities(results)

        # Create AI prompt based on analysis
        prompt = self.create_analysis_prompt(results, project_path)

        # Create new chat tab with analysis and AI suggestions
        self.create_analysis_tab(prompt, results, project_path)

    def on_analysis_error(self, error_msg, progress):
        progress.close()
        QMessageBox.critical(self, "Analysis Error", f"Failed to analyze project:\n{error_msg}")

    def show_entity_info(self, info_text):
        """Show entity information in a new chat tab."""
        tab = ChatTab(self.settings)
        tab_index = self.tabs.addTab(tab, f"Entity Info")
        self.tabs.setCurrentIndex(tab_index)

        # Display entity information
        tab.chat_area.append("<b style='color:#66d9ef;'>[Entity Information]</b>\n")
        tab.chat_area.append(info_text)
        tab.chat_area.append("\n")

        # Connect the tab's buttons
        tab.send_btn.clicked.connect(lambda: self.send_message(tab))
        tab.input_box.returnPressed.connect(lambda: self.send_message(tab))
        tab.clear_btn.clicked.connect(lambda: tab.chat_area.clear())
        tab.stop_btn.clicked.connect(tab.stop_generation)

    def close_tab(self, index):
        """Handle tab close request."""
        # Don't allow closing if it's the last tab
        if self.tabs.count() > 1:
            # Stop any running generation in this tab
            tab = self.tabs.widget(index)
            if hasattr(tab, 'worker') and tab.worker and tab.worker.isRunning():
                tab.worker.stop_generation()

            # Remove the tab
            self.tabs.removeTab(index)
        else:
            # If it's the last tab, just clear it instead of closing
            tab = self.tabs.widget(index)
            if hasattr(tab, 'chat_area'):
                tab.chat_area.clear()
            if hasattr(tab, 'input_box'):
                tab.input_box.clear()

    def create_analysis_prompt(self, results, project_path):
        """Create a comprehensive prompt for AI to analyze results and suggest solutions."""
        summary = results.get('summary', {})
        issues = results.get('issues', {})
        suggestions = results.get('suggestions', {})

        prompt = f"""# Project Analysis Results

## Project: {Path(project_path).name}
- **Total Files**: {summary.get('total_files', 0)}
- **Lines of Code**: {summary.get('total_lines', 0)}
- **Issues Found**: {summary.get('issues_count', 0)}

## Key Issues:
"""

        # Add major issues
        for category, issue_list in issues.items():
            if issue_list:
                prompt += f"### {category.replace('_', ' ').title()}\n"
                for issue in issue_list[:5]:  # Limit to 5 per category
                    prompt += f"- {issue}\n"

        prompt += "\n## Current Suggestions:\n"
        for category, suggestion_list in suggestions.items():
            if suggestion_list:
                prompt += f"### {category.title()}\n"
                for suggestion in suggestion_list:
                    prompt += f"- {suggestion}\n"

        prompt += """

## Task:
As an expert software engineer, please analyze this project analysis and provide:
1. Detailed assessment of the code quality and architecture
2. Prioritized list of issues that need immediate attention
3. Specific code improvements and refactoring suggestions
4. Best practices recommendations for this type of project
5. Any potential bugs or security concerns you can identify from the analysis

Please be thorough but practical in your recommendations. Focus on actionable improvements that will have the most impact."""

        return prompt

    def create_analysis_tab(self, prompt, results, project_path):
        """Create a new chat tab with the analysis prompt."""
        # Create tab with analysis context
        tab = ChatTab(self.settings, analysis_context=results)
        tab_index = self.tabs.addTab(tab, f"Analysis: {Path(project_path).name}")
        self.tabs.setCurrentIndex(tab_index)

        # Connect the tab's buttons
        tab.send_btn.clicked.connect(lambda: self.send_message(tab))
        tab.input_box.returnPressed.connect(lambda: self.send_message(tab))
        tab.clear_btn.clicked.connect(lambda: tab.chat_area.clear())

        # Display analysis summary first
        analyzer = ProjectAnalyzer()
        formatted_results = analyzer.format_analysis_results(results)

        tab.chat_area.append("<b style='color:#66d9ef;'>[Project Analysis Complete]</b>\n")
        tab.chat_area.append(formatted_results)
        tab.chat_area.append("\n\n" + "="*50 + "\n\n")
        tab.chat_area.append("<b style='color:#00ffa3;'>[AI Analysis & Suggestions]</b>\n")

        # Set up AI response
        tab.chat_area.append(f"<b style='color:#66d9ef;'>[{tab.model}]</b> ")
        tab.typing_label.setText(f"Analyzing with {tab.model}...")

        # Create worker for AI analysis
        tab.worker = OllamaTypingWorker(tab.model, prompt, self.settings.get("ollama_path", "ollama"))
        tab.worker.new_char.connect(tab.append_stream_char)
        tab.worker.finished_signal.connect(lambda: (tab.chat_area.insertPlainText("\n"), tab.typing_label.setText("")))
        tab.worker.start()

        save_history(prompt, tab.model)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ChatApp()
    window.show()
    # Load analysis context if available
    try:
        from analysis_context import context_manager
        context = context_manager.load_analysis_context()
        if context:
            print(f"Loaded analysis context for project: {context.get('project_name', 'Unknown')}")
    except ImportError:
        print("Analysis context manager not available")
    sys.exit(app.exec())
