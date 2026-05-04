import sys
import time
from PySide6.QtWidgets import QApplication, QMainWindow, QMenuBar, QMenu, QMessageBox, QTabWidget, QWidget, QHBoxLayout
from settings import load_settings, save_settings
from history import load_history, save_history
from gui import ChatTab, SettingsDialog, EntitySidebar
from logic import OllamaTypingWorker, TextChangeMonitor
from scanner import ProjectAnalyzer
from analysis_context import context_manager
from pathlib import Path
from PySide6.QtWidgets import QFileDialog, QProgressDialog
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QKeySequence, QAction
from response_handler import EnhancedResponseHandler
from tools import create_tool_executor
from skills import get_skill_loader
from task_agent import get_task_agent
from unified_worker import UnifiedWorker

class AnalysisWorker(QThread):
    progress = Signal(str)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, project_path):
        super().__init__()
        self.project_path = project_path
        self.cancelled = False
        self.analyzer = None

    def cancel(self):
        """Cancel the analysis operation."""
        self.cancelled = True
        if hasattr(self, "analyzer") and self.analyzer:
            try:
                self.analyzer.cancel_scan()
            except Exception:
                pass

    def run(self):
        try:
            self.analyzer = ProjectAnalyzer(self.project_path)
            results = self.analyzer.analyze_project(lambda msg: self.progress.emit(msg))
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
        
        # Add teams action to Tools menu
        teams_action = tools_menu.addAction("AI Teams")
        teams_action.triggered.connect(self.open_team_dialog)

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
        if not self.settings.get("dark_theme", True):
            self.setStyleSheet("")
            return
        font_size = int(self.settings.get("font_size", 14))

        # Grok-inspired palette
        base_bg = "#0d0d0f"      # Deep dark background
        panel_bg = "#1a1c24"     # Slightly lighter panel background
        accent = "#ab68ff"       # Grok neon purple
        accent2 = "#00d9ff"      # Grok neon blue
        text_col = "#ffffff"     # White text
        subtext = "#9ca3af"      # Muted gray for secondary
        btn_bg = "#10121a"       # Button background
        border = "#2d2f36"       # Subtle border gray
        input_bg = "#1f222a"     # Dark input background

        qss = f"""
            QMainWindow {{ background-color: {base_bg}; color: {text_col}; }}
            QWidget {{ color: {text_col}; font-size: {font_size}px; }}
            QTabWidget::pane {{ border: 1px solid {border}; background: {panel_bg}; }}
            QTabBar::tab {{ background: {btn_bg}; color: {subtext}; padding: 8px 16px; border: 1px solid {border}; border-bottom: none; }}
            QTabBar::tab:selected {{ background: {panel_bg}; color: {accent}; }}
            QTextEdit {{ background-color: {panel_bg}; border: 1px solid {border}; selection-background-color: {accent}; color: {text_col}; }}
            QLineEdit {{ background-color: {input_bg}; border: 1px solid {border}; padding: 8px; selection-background-color: {accent2}; color: {text_col}; }}
            QPushButton {{ background-color: {btn_bg}; border: 1px solid {border}; padding: 8px 12px; color: {text_col}; }}
            QPushButton:hover {{ border: 1px solid {accent}; background-color: {panel_bg}; }}
            QLabel {{ color: {subtext}; }}
            QComboBox {{ background-color: {input_bg}; border: 1px solid {border}; padding: 6px 8px; color: {text_col}; }}
            QComboBox QAbstractItemView {{ background: {panel_bg}; selection-background-color: {accent2}; }}
            QMenuBar {{ background: {panel_bg}; color: {text_col}; }}
            QMenuBar::item:selected {{ background: {btn_bg}; }}
            QMenu {{ background: {panel_bg}; color: {text_col}; border: 1px solid {border}; }}
            QMenu::item:selected {{ background: {accent}; }}
            QScrollArea {{ background: {panel_bg}; border: none; }}
            QScrollBar:vertical {{ background: {panel_bg}; width: 12px; }}
            QScrollBar::handle:vertical {{ background: {accent}; border-radius: 6px; }}
            QScrollBar::handle:vertical:hover {{ background: {accent2}; }}
            QTabBar::close-button {{ image: url(close.png); }}
            QTabBar::close-button:hover {{ background: {accent2}; }}
        """
        self.setStyleSheet(qss)

    def new_chat_tab(self):
        tab = ChatTab(self.settings)
        self.tabs.addTab(tab, f"Chat {self.tabs.count()+1}")
        # Ensure Enter-to-send works with QTextEdit input and connect unified signal
        try:
            tab.input_box.installEventFilter(tab)
        except Exception:
            pass
        tab.send_requested.connect(lambda: self.send_message(tab))
        tab.send_btn.clicked.connect(lambda: self.send_message(tab))
        tab.clear_btn.clicked.connect(lambda: self.clear_chat_and_sidebar(tab))
        tab.stop_btn.clicked.connect(tab.stop_generation)

    def clear_chat_and_sidebar(self, tab):
        """Clear the chat area and reset the sidebar to empty state."""
        tab.chat_area.clear()
        self.sidebar.show_empty_state()

    def send_message(self, tab):
        # Support both QLineEdit and QTextEdit inputs
        text = ""
        try:
            if hasattr(tab.input_box, "toPlainText"):
                text = tab.input_box.toPlainText().strip()
            elif hasattr(tab.input_box, "text"):
                text = tab.input_box.text().strip()
        except Exception:
            text = ""
        if not text:
            return
        tab.chat_area.append(f"<b style='color:#ffcc00;'>You:</b> {text}\n")
        try:
            tab.input_box.clear()
        except Exception:
            pass

        # Build the full prompt with context
        prompt_parts = []
        
        # Add analysis context if available
        if hasattr(tab, 'analysis_context') and tab.analysis_context:
            context = context_manager.get_context_for_chat()
            if context:
                prompt_parts.append(context)
        
        # Add tool context from previous tool executions
        if hasattr(tab, 'tool_context') and tab.tool_context:
            prompt_parts.append(tab.tool_context)
        
        # Add the user's question
        prompt_parts.append(f"User Question: {text}")
        
        base_prompt = "\n\n".join(prompt_parts) if prompt_parts else text
        
        # Get project root for tool execution
        project_root = self.settings.get("project_root", "..")
        
        # Load skills for enhanced capabilities
        try:
            skill_loader = get_skill_loader(project_root)
            available_skills = skill_loader.get_available_skills()
            skill_help = skill_loader.get_skill_help()
        except Exception:
            available_skills = []
            skill_help = ""
        
        # Initialize task agent for background tasks
        try:
            task_agent = get_task_agent(tab.model, self.settings.get("ollama_path", "ollama"))
        except Exception:
            task_agent = None
        
        # Add tool and skill instructions as a system prompt
        system_prompt = f"""You can use the following tools when needed:
- glob <pattern>: Find files matching pattern (e.g., glob **/*.py)
- grep <pattern> --include <ext>: Search for pattern in files (e.g., grep "function" --include *.py)
- read <file> [limit] [offset]: Read a file (e.g., read src/main.py 100 10)
- write <file> <content>: Write content to file
- edit <file> <old> <new>: Edit file content (replace first occurrence)
- bash <command>: Execute shell command

Wrap tool calls in <tool>...</tool> tags like: <tool>glob **/*.py</tool>

Think step by step inside <ThoughtProcess></ThoughtProcess> tags, then provide your final answer inside <Response></Response> tags.

If you need to examine code, use the appropriate tool and include results in your thinking.

Available Skills: {', '.join(available_skills) if available_skills else 'None'}
Task Agent: {'Available for background exploration tasks' if task_agent else 'Not available'}

{skill_help}"""
        
        # Combine: system prompt first, then context, then user question
        full_prompt = f"{system_prompt}\n\n{base_prompt}"

        # Show model label and start streaming directly under it
        tab.chat_area.append(f"<b style='color:#66d9ef;'>[{tab.model}]</b> ")
        # Reset formatting states for new response
        tab.is_thinking = False
        tab.is_answer = False
        tab.pending_text = ""
        allow_long = self.settings.get("allow_long_analysis", False)
        status_txt = "(Long Analysis: Enabled, no timeout)" if allow_long else "(Timeout: 5 minutes)"
        tab.typing_label.setText(f"Typing with {tab.model}... {status_txt}")
        
        try:
            # Create enhanced response handler
            tab.response_handler = EnhancedResponseHandler(tab.chat_area)
            tab.response_handler.set_tool_root(project_root)
            
            # Connect signals
            tab.response_handler.new_content.connect(tab.chat_area.append)
            tab.response_handler.progress_update.connect(tab.typing_label.setText)
            tab.response_handler.error_signal.connect(lambda err: tab.chat_area.append(f"<b style='color:#ff4444;'>[Error]</b> {err}\n"))
            tab.response_handler.tool_executed.connect(lambda res: tab.chat_area.append(f"\n<b style='color:#66d9ef;'>[Tool: {res.get('type', 'unknown')}]</b>\n{res.get('result', res.get('error', ''))}\n"))
            
            # Store task agent reference
            try:
                tab.task_agent = get_task_agent(tab.model, self.settings.get("ollama_path", "ollama"))
            except Exception:
                tab.task_agent = None
            
            def _on_finish():
                tab.typing_label.setText("")
                tab.stop_btn.setEnabled(False)
                tab.stop_btn.setText("Stop")
                tab.send_btn.setEnabled(True)
                # Tools are now executed in response_handler.finish_response()
                # Just get the tool context for follow-up questions
                if hasattr(tab.response_handler, 'get_tool_context'):
                    tab.tool_context = tab.response_handler.get_tool_context()
                else:
                    tab.tool_context = ""
            
            tab.response_handler.finished_signal.connect(_on_finish)
            
            # Create unified worker for AI generation (supports Ollama + cloud)
            provider = self.settings.get("model_provider", "ollama")
            api_key = ""
            if provider == "openai":
                api_key = self.settings.get("openai_api_key", "")
            elif provider == "anthropic":
                api_key = self.settings.get("anthropic_api_key", "")
            elif provider == "google":
                api_key = self.settings.get("google_api_key", "")
            
            tab.worker = UnifiedWorker(
                tab.model, full_prompt, provider,
                self.settings.get("ollama_path", "ollama"), api_key, allow_long
            )
            
            # Connect worker to response handler
            tab.worker.new_chunk.connect(tab.response_handler.handle_chunk)
            tab.worker.progress_update.connect(tab.typing_label.setText)
            tab.worker.error_signal.connect(lambda err: tab.chat_area.append(f"<b style='color:#ff4443;'>[Error]</b> {err}\n"))
            
            tab.stop_btn.setText("Halt" if allow_long else "Stop")
            tab.stop_btn.setEnabled(True)
            tab.send_btn.setEnabled(False)
            tab.worker.start()
            
        except Exception as e:
            tab.chat_area.append(f"<b style='color:#ff4444;'>[Error]</b> Failed to start model: {e}\n")
            tab.typing_label.setText("")
            tab.stop_btn.setEnabled(False)
            tab.send_btn.setEnabled(True)
        
        save_history(text, tab.model)

    def open_settings(self):
        dialog = SettingsDialog(self, self.settings)
        if dialog.exec():
            self.settings["ollama_path"] = dialog.path_input.text()
            self.settings["font_size"] = dialog.font_size_spin.value()
            self.settings["dark_theme"] = dialog.dark_mode.isChecked()
            self.settings["allow_long_analysis"] = dialog.allow_long_analysis.isChecked()
            self.settings["language"] = dialog.language_combo.currentText()
            self.settings["enable_completion"] = dialog.enable_completion.isChecked()
            self.settings["model_provider"] = dialog.provider_combo.currentText()
            self.settings["model"] = dialog.model_combo.currentText()
            # Save API keys
            provider = dialog.provider_combo.currentText()
            if provider == "openai":
                self.settings["openai_api_key"] = dialog.api_key_input.text()
            elif provider == "anthropic":
                self.settings["anthropic_api_key"] = dialog.api_key_input.text()
            elif provider == "google":
                self.settings["google_api_key"] = dialog.api_key_input.text()
            save_settings(self.settings)
            self.apply_theme()

    def open_team_dialog(self):
        """Open the team setup dialog"""
        try:
            from team_dialog import TeamDialog
            dialog = TeamDialog(self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Teams Error", f"Failed to open team dialog:\n{e}")

    def show_about(self):
        QMessageBox.information(self, "About", "Offline chugaGPT AI Tool\nWarp Style GUI\nSupports multiple chat tabs.\nerickwilfreddaniel@gmail.com")

    def analyze_project(self):
        """Analyze the project using offline AI and provide suggestions."""
        # Ask user to select project directory
        directory = QFileDialog.getExistingDirectory(self, "Select Project Directory to Analyze")
        if not directory:
            return

        # Create progress dialog
        allow_long = self.settings.get("allow_long_analysis", False)
        cancel_text = "Halt" if allow_long else "Cancel"
        progress = QProgressDialog("Analyzing project...", cancel_text, 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        status_line = "Long Analysis Mode: Enabled (no timeout)" if allow_long else "Timeout: 5 minutes"
        progress.setLabelText(f"Analyzing project...\n{status_line}")
        progress.show()

        # Create analysis worker
        start_time = time.time()
        self.analysis_worker = AnalysisWorker(directory)
        def _progress_update(msg: str):
            # Add simple ETA when possible by parsing "(current/total)" in message
            eta_txt = ""
            try:
                if "(" in msg and ")" in msg and "/" in msg:
                    inner = msg[msg.rfind("(")+1: msg.rfind(")")]
                    parts = inner.split("/")
                    if len(parts) == 2:
                        current = int(''.join(ch for ch in parts[0] if ch.isdigit()))
                        total = int(''.join(ch for ch in parts[1] if ch.isdigit()))
                        if current > 0 and total > 0 and current <= total:
                            elapsed = time.time() - start_time
                            per_item = elapsed / current
                            remain = max(0, int((total - current) * per_item))
                            m, s = divmod(remain, 60)
                            eta_txt = f" | ETA: {m}m {s}s"
            except Exception:
                eta_txt = ""
            progress.setLabelText(f"{msg}\n{status_line}{eta_txt}")
        self.analysis_worker.progress.connect(_progress_update)
        self.analysis_worker.finished.connect(lambda results: self.on_analysis_finished(results, directory, progress))
        self.analysis_worker.error.connect(lambda err: self.on_analysis_error(err, progress))

        # Connect cancel/halt button to graceful cancellation with feedback
        def _on_cancel():
            progress.setLabelText(f"Halting analysis...\n{status_line}")
            self.analysis_worker.cancel()
        progress.canceled.connect(_on_cancel)

        # Start analysis
        self.analysis_worker.start()

    def on_analysis_finished(self, results, project_path, progress):
        # If user halted, confirm and do not create analysis tab or save context
        if progress.wasCanceled():
            progress.close()
            QMessageBox.information(self, "Analysis Halted", "The analysis was halted successfully. No data was saved.")
            return
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
        try:
            tab.input_box.installEventFilter(tab)
        except Exception:
            pass
        tab.send_requested.connect(lambda: self.send_message(tab))
        tab.send_btn.clicked.connect(lambda: self.send_message(tab))
        tab.clear_btn.clicked.connect(lambda: self.clear_chat_and_sidebar(tab))
        tab.stop_btn.clicked.connect(tab.stop_generation)

    def close_tab(self, index):
        """Handle tab close request."""
# Don't allow closing if it's the last tab
        if self.tabs.count() > 1:
            # Stop any running generation in this tab
            # Clean up background workers (completion engine, suggestion widget, typing worker)
            try:
                if hasattr(self.tabs.widget(index), 'cleanup'):
                    self.tabs.widget(index).cleanup()
            except Exception:
                pass
            if hasattr(self.tabs.widget(index), 'worker') and self.tabs.widget(index).worker and hasattr(self.tabs.widget(index).worker, 'isRunning') and self.tabs.widget(index).worker.isRunning():
                self.tabs.widget(index).worker.stop_generation()

            # Remove the tab
            self.tabs.removeTab(index)
        else:
            # If it's the last tab, just clear it instead of closing
            tab = self.tabs.widget(index)
            if hasattr(tab, 'chat_area'):
                tab.chat_area.clear()
            if hasattr(tab, 'input_box'):
                tab.input_box.clear()

    def closeEvent(self, event):
        """Ensure all background threads are stopped before window closes."""
        # Stop project analysis worker if running
        try:
            if hasattr(self, 'analysis_worker') and self.analysis_worker:
                try:
                    # Signal cancellation then wait briefly
                    self.analysis_worker.cancel()
                except Exception:
                    pass
                try:
                    self.analysis_worker.wait(2000)
                except Exception:
                    pass
        except Exception:
            pass
        # Clean up each chat tab (completion engine, suggestion widget, typing workers)
        try:
            for i in range(self.tabs.count()):
                tab = self.tabs.widget(i)
                if hasattr(tab, 'cleanup'):
                    try:
                        tab.cleanup()
                    except Exception:
                        pass
        except Exception:
            pass
        # Stop task agent if running
        try:
            if hasattr(self, '_task_agent') and self._task_agent:
                # Task agent doesn't have a stop method, but we can clear references
                self._task_agent = None
        except Exception:
            pass
        # Proceed with normal close
        super().closeEvent(event)

    def run_background_task(self, task_type: str, root_path: str, pattern: str = ""):
        """Run a background task using the task agent."""
        try:
            if not hasattr(self, '_task_agent') or not self._task_agent:
                from task_agent import get_task_agent
                self._task_agent = get_task_agent()
            
            if task_type == "explore":
                result = self._task_agent.explore_codebase(root_path, pattern or "*.py")
                # Show result in current tab
                current_tab = self.tabs.currentWidget()
                if current_tab and hasattr(current_tab, 'chat_area'):
                    current_tab.chat_area.append(f"\n<b style='color:#66d9ef;'>[Task Agent - Explore]</b>\n{result}\n")
            elif task_type == "search":
                result = self._task_agent.search_code(root_path, pattern)
                current_tab = self.tabs.currentWidget()
                if current_tab and hasattr(current_tab, 'chat_area'):
                    current_tab.chat_area.append(f"\n<b style='color:#66d9ef;'>[Task Agent - Search]</b>\n{result}\n")
        except Exception as e:
            current_tab = self.tabs.currentWidget()
            if current_tab and hasattr(current_tab, 'chat_area'):
                current_tab.chat_area.append(f"\n<b style='color:#ff4444;'>[Task Agent Error]</b> {e}\n")

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
        try:
            tab.input_box.installEventFilter(tab)
        except Exception:
            pass
        tab.send_requested.connect(lambda: self.send_message(tab))
        tab.send_btn.clicked.connect(lambda: self.send_message(tab))
        tab.clear_btn.clicked.connect(lambda: self.clear_chat_and_sidebar(tab))
        tab.stop_btn.clicked.connect(tab.stop_generation)

# Display analysis summary first
        analyzer = ProjectAnalyzer()
        formatted_results = analyzer.format_analysis_results(results)

        tab.chat_area.append("<b style='color:#66d9ef;'>[Project Analysis Complete]</b>\n")
        tab.chat_area.append(formatted_results)
        tab.chat_area.append("\n\n" + "="*50 + "\n\n")
        tab.chat_area.append("<b style='color:#00ffa3;'>[AI Analysis & Suggestions]</b>\n")

# Set up AI response
        tab.chat_area.append(f"<b style='color:#66d9ef;'>[{tab.model}]</b> ")
        allow_long = self.settings.get("allow_long_analysis", False)
        status_txt = "(Long Analysis: Enabled, no timeout)" if allow_long else "(Timeout: 5 minutes)"
        tab.typing_label.setText(f"Analyzing with {tab.model}... {status_txt}")

# Create enhanced response handler
        tab.response_handler = EnhancedResponseHandler(tab.chat_area)
        
        # Connect signals
        tab.response_handler.new_content.connect(tab.chat_area.append)
        tab.response_handler.progress_update.connect(tab.typing_label.setText)
        tab.response_handler.error_signal.connect(lambda err: tab.chat_area.append(f"<b style='color:#ff4444;'>[Error]</b> {err}\n"))
        
        def _on_analysis_finish():
            tab.chat_area.insertPlainText("\n")
            tab.typing_label.setText("")
            tab.stop_btn.setEnabled(False)
            tab.stop_btn.setText("Stop")
            tab.send_btn.setEnabled(True)
            tab.response_handler.finish_response()
        
        tab.response_handler.finished_signal.connect(_on_analysis_finish)

        # Create worker for AI analysis using unified worker
        try:
            provider = self.settings.get("model_provider", "ollama")
            api_key = ""
            if provider == "openai":
                api_key = self.settings.get("openai_api_key", "")
            elif provider == "anthropic":
                api_key = self.settings.get("anthropic_api_key", "")
            elif provider == "google":
                api_key = self.settings.get("google_api_key", "")
            
            tab.worker = UnifiedWorker(
                tab.model, prompt, provider,
                self.settings.get("ollama_path", "ollama"), api_key, allow_long
            )
            tab.worker.new_chunk.connect(tab.response_handler.handle_chunk)
            tab.worker.progress_update.connect(tab.typing_label.setText)
            tab.worker.error_signal.connect(lambda err: tab.chat_area.append(f"<b style='color:#ff4443;'>[Error]</b> {err}\n"))
            
            tab.stop_btn.setText("Halt" if allow_long else "Stop")
            tab.stop_btn.setEnabled(True)
            tab.send_btn.setEnabled(False)
            tab.worker.start()
        except Exception as e:
            tab.chat_area.append(f"<b style='color:#ff4444;'>[Error]</b> Failed to start analysis model: {e}\n")
            tab.typing_label.setText("")
            tab.stop_btn.setEnabled(False)
            tab.send_btn.setEnabled(True)

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
