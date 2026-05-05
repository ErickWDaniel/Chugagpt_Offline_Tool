"""
Task Agent Dialog - Configure and run background tasks with skill management
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QComboBox, QListWidget, QListWidgetItem, QCheckBox,
    QDialogButtonBox, QFormLayout, QSpinBox, QTextEdit,
    QTabWidget, QWidget, QGroupBox, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from task_agent import get_task_agent, TaskAgent
from skills import get_skill_loader
import threading

class TaskAgentDialog(QDialog):
    task_started = Signal(str)  # task_id
    
    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.settings = settings or {}
        self.setWindowTitle("Task Agent - Background Tasks")
        self.setMinimumSize(600, 500)
        self.skill_loader = None
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("Task Agent")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        layout.addWidget(title)
        
        # Tab widget for different sections
        tabs = QTabWidget()
        
        # Task Execution Tab
        task_tab = QWidget()
        self.setup_task_tab(task_tab)
        tabs.addTab(task_tab, "Run Tasks")
        
        # Skills Management Tab
        skills_tab = QWidget()
        self.setup_skills_tab(skills_tab)
        tabs.addTab(skills_tab, "Skills")
        
        # Results Tab
        results_tab = QWidget()
        self.setup_results_tab(results_tab)
        tabs.addTab(results_tab, "Results")
        
        layout.addWidget(tabs)
        
        # Close button
        button_layout = QHBoxLayout()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)
        
    def setup_task_tab(self, tab):
        layout = QVBoxLayout(tab)
        
        # Task type selection
        form_layout = QFormLayout()
        
        self.task_type_combo = QComboBox()
        self.task_type_combo.addItems(["explore", "search", "read_file"])
        self.task_type_combo.currentTextChanged.connect(self.on_task_type_changed)
        form_layout.addRow("Task Type:", self.task_type_combo)
        
        self.root_path_input = QTextEdit()
        self.root_path_input.setMaximumHeight(60)
        self.root_path_input.setPlainText(self.settings.get("project_root", ".."))
        form_layout.addRow("Root Path:", self.root_path_input)
        
        self.pattern_input = QTextEdit()
        self.pattern_input.setMaximumHeight(60)
        self.pattern_input.setPlainText("*.py")
        form_layout.addRow("Pattern:", self.pattern_input)
        
        layout.addLayout(form_layout)
        
        # Run button
        run_btn = QPushButton("Run Task")
        run_btn.setStyleSheet("""
            QPushButton {
                background-color: #10a37f;
                color: white;
                padding: 10px 20px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #19c37d; }
        """)
        run_btn.clicked.connect(self.run_task)
        layout.addWidget(run_btn)
        
        # Output area
        layout.addWidget(QLabel("Output:"))
        self.output_area = QTextEdit()
        self.output_area.setReadOnly(True)
        self.output_area.setStyleSheet("""
            QTextEdit {
                background-color: #f7f7f8;
                border: 1px solid #e5e5e5;
                border-radius: 8px;
                padding: 10px;
                font-family: monospace;
            }
        """)
        layout.addWidget(self.output_area)
        
    def setup_skills_tab(self, tab):
        layout = QVBoxLayout(tab)
        
        # Load skills
        try:
            self.skill_loader = get_skill_loader(".")
            available_skills = self.skill_loader.get_available_skills()
        except Exception as e:
            available_skills = []
            layout.addWidget(QLabel(f"Error loading skills: {e}"))
            
        # Skills list
        layout.addWidget(QLabel("Available Skills:"))
        self.skills_list = QListWidget()
        
        for skill_name in available_skills:
            item = QListWidgetItem(skill_name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)  # Enabled by default
            self.skills_list.addItem(item)
            
        if not available_skills:
            self.skills_list.addItem("No skills found in .skills/ directory")
            
        layout.addWidget(self.skills_list)
        
        # Skill description
        self.skill_description = QTextEdit()
        self.skill_description.setReadOnly(True)
        self.skill_description.setMaximumHeight(100)
        layout.addWidget(QLabel("Description:"))
        layout.addWidget(self.skill_description)
        
        # Buttons
        btn_layout = QHBoxLayout()
        enable_all_btn = QPushButton("Enable All")
        disable_all_btn = QPushButton("Disable All")
        refresh_btn = QPushButton("Refresh")
        
        enable_all_btn.clicked.connect(lambda: self.toggle_all_skills(True))
        disable_all_btn.clicked.connect(lambda: self.toggle_all_skills(False))
        refresh_btn.clicked.connect(self.refresh_skills)
        
        btn_layout.addWidget(enable_all_btn)
        btn_layout.addWidget(disable_all_btn)
        btn_layout.addWidget(refresh_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # Connect selection change
        self.skills_list.itemSelectionChanged.connect(self.on_skill_selected)
        
    def setup_results_tab(self, tab):
        layout = QVBoxLayout(tab)
        
        layout.addWidget(QLabel("Recent Task Results:"))
        self.results_area = QTextEdit()
        self.results_area.setReadOnly(True)
        self.results_area.setStyleSheet("""
            QTextEdit {
                background-color: #f7f7f8;
                border: 1px solid #e5e5e5;
                border-radius: 8px;
                padding: 10px;
                font-family: monospace;
            }
        """)
        layout.addWidget(self.results_area)
        
        # Refresh results button
        refresh_btn = QPushButton("Refresh Results")
        refresh_btn.clicked.connect(self.load_results)
        layout.addWidget(refresh_btn)
        
        # Load initial results
        self.load_results()
        
    def on_task_type_changed(self, task_type):
        if task_type == "explore":
            self.pattern_input.setPlainText("*.py")
        elif task_type == "search":
            self.pattern_input.setPlainText("def ")
        elif task_type == "read_file":
            self.pattern_input.setPlainText("main.py")
            
    def run_task(self):
        task_type = self.task_type_combo.currentText()
        root_path = self.root_path_input.toPlainText().strip()
        pattern = self.pattern_input.toPlainText().strip()
        
        self.output_area.append(f"Running {task_type} task...\n")
        
        def run_in_background():
            try:
                agent = get_task_agent()
                if task_type == "explore":
                    result = agent.explore_codebase(root_path, pattern)
                elif task_type == "search":
                    result = agent.search_code(root_path, pattern)
                elif task_type == "read_file":
                    result = agent.read_file(root_path, pattern)
                else:
                    result = "Unknown task type"
                    
                self.output_area.append(result)
                self.output_area.append("\nTask completed!\n")
                self.load_results()  # Refresh results
            except Exception as e:
                self.output_area.append(f"\nError: {e}\n")
                
        thread = threading.Thread(target=run_in_background, daemon=True)
        thread.start()
        
    def toggle_all_skills(self, enabled):
        state = Qt.Checked if enabled else Qt.Unchecked
        for i in range(self.skills_list.count()):
            item = self.skills_list.item(i)
            item.setCheckState(state)
            
    def refresh_skills(self):
        self.skills_list.clear()
        try:
            self.skill_loader = get_skill_loader(".")
            available_skills = self.skill_loader.get_available_skills()
            for skill_name in available_skills:
                item = QListWidgetItem(skill_name)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked)
                self.skills_list.addItem(item)
        except Exception as e:
            self.skills_list.addItem(f"Error: {e}")
            
    def on_skill_selected(self):
        selected_items = self.skills_list.selectedItems()
        if selected_items:
            skill_name = selected_items[0].text()
            try:
                if hasattr(self, 'skill_loader') and self.skill_loader:
                    skills = self.skill_loader.load_skills()
                    if skill_name in skills:
                        skill = skills[skill_name]
                        self.skill_description.setPlainText(
                            f"Name: {skill.name}\n"
                            f"Description: {skill.description}\n"
                            f"Triggers: {', '.join(skill.triggers)}\n"
                        )
            except Exception as e:
                self.skill_description.setPlainText(f"Error: {e}")
                
    def load_results(self):
        self.results_area.clear()
        try:
            agent = get_task_agent()
            results = agent.get_recent_results(limit=10)
            for r in results:
                self.results_area.append(
                    f"[{r['task_type']}] Status: {r['status']}\n"
                    f"Result: {r['result'][:200]}...\n"
                    f"{'='*50}\n"
                )
        except Exception as e:
            self.results_area.append(f"Error loading results: {e}")
            
    def get_enabled_skills(self):
        """Return list of enabled skill names"""
        enabled = []
        for i in range(self.skills_list.count()):
            item = self.skills_list.item(i)
            if item.checkState() == Qt.Checked:
                enabled.append(item.text())
        return enabled
