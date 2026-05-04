"""
Team Setup Dialog for ChugaGPT Multi-Agent System
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QSpinBox, QCheckBox,
    QPushButton, QLabel, QListWidget, QListWidgetItem,
    QDialogButtonBox, QMessageBox, QWidget
)
from PySide6.QtCore import Qt, Signal
from multi_agent import (
    AgentRole, AgentConfig, AgentTeam, TeamManager,
    DEFAULT_TEAMS
)


class AgentConfigWidget(QWidget):
    """Widget for configuring a single agent"""
    
    removed = Signal()
    
    def __init__(self, agent: AgentConfig = None, parent=None):
        super().__init__(parent)
        self.agent = agent or AgentConfig("", "phi3:mini", "ollama", AgentRole.CODER)
        self.init_ui()
        
    def init_ui(self):
        layout = QFormLayout(self)
        
        # Agent name
        self.name_input = QLineEdit(self.agent.name)
        layout.addRow("Name:", self.name_input)
        
        # Model selection
        self.model_combo = QComboBox()
        self._populate_models()
        self.model_combo.setCurrentText(self.agent.model)
        layout.addRow("Model:", self.model_combo)
        
        # Provider
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["ollama", "openai", "anthropic", "google"])
        self.provider_combo.setCurrentText(self.agent.provider)
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        layout.addRow("Provider:", self.provider_combo)
        
        # Role
        self.role_combo = QComboBox()
        for role in AgentRole:
            self.role_combo.addItem(role.value.title(), role)
        self.role_combo.setCurrentText(self.agent.role.value.title())
        layout.addRow("Role:", self.role_combo)
        
        # System prompt
        self.prompt_input = QLineEdit(self.agent.system_prompt)
        self.prompt_input.setPlaceholderText("Enter system prompt for this agent...")
        layout.addRow("System Prompt:", self.prompt_input)
        
        # Tools enabled
        self.tools_check = QCheckBox("Enable Tools")
        self.tools_check.setChecked(self.agent.tools_enabled)
        layout.addRow(self.tools_check)
        
        # Max iterations
        self.iterations_spin = QSpinBox()
        self.iterations_spin.setRange(1, 50)
        self.iterations_spin.setValue(self.agent.max_iterations)
        layout.addRow("Max Iterations:", self.iterations_spin)
        
        # Remove button
        self.remove_btn = QPushButton("Remove Agent")
        self.remove_btn.setStyleSheet("background-color: #ef4444; color: white;")
        self.remove_btn.clicked.connect(self.removed.emit)
        layout.addRow(self.remove_btn)
        
    def _populate_models(self):
        """Populate model list based on provider"""
        provider = self.provider_combo.currentText()
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
                self.model_combo.addItems(["phi3:mini", "llama3:8b"])
        elif provider == "openai":
            self.model_combo.addItems(["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"])
        elif provider == "anthropic":
            self.model_combo.addItems(["claude-3-5-sonnet-20241022", "claude-3-opus-20240229"])
        elif provider == "google":
            self.model_combo.addItems(["gemini-2.0-flash-exp", "gemini-1.5-pro"])
            
    def _on_provider_changed(self, provider):
        """Update model list when provider changes"""
        self._populate_models()
        
    def get_config(self) -> AgentConfig:
        """Get agent configuration"""
        return AgentConfig(
            name=self.name_input.text(),
            model=self.model_combo.currentText(),
            provider=self.provider_combo.currentText(),
            role=AgentRole(self.role_combo.currentData()),
            system_prompt=self.prompt_input.text(),
            tools_enabled=self.tools_check.isChecked(),
        )


class TeamDialog(QDialog):
    """Dialog for managing agent teams"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Team Setup - Multi-Agent System")
        self.setMinimumSize(600, 500)
        self.team_manager = TeamManager()
        self.init_ui()
        self._load_teams()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Team selection
        team_layout = QHBoxLayout()
        team_layout.addWidget(QLabel("Select Team:"))
        
        self.team_combo = QComboBox()
        self.team_combo.currentTextChanged.connect(self._on_team_changed)
        team_layout.addWidget(self.team_combo)
        
        new_team_btn = QPushButton("New Team")
        new_team_btn.clicked.connect(self._create_new_team)
        team_layout.addWidget(new_team_btn)
        
        delete_team_btn = QPushButton("Delete Team")
        delete_team_btn.setStyleSheet("background-color: #ef4444; color: white;")
        delete_team_btn.clicked.connect(self._delete_team)
        team_layout.addWidget(delete_team_btn)
        
        team_layout.addStretch()
        layout.addLayout(team_layout)
        
        # Team description
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("Team description...")
        layout.addWidget(self.desc_input)
        
        # Agents list
        layout.addWidget(QLabel("Agents in Team:"))
        
        self.agents_list = QListWidget()
        layout.addWidget(self.agents_list)
        
        # Agent edit area
        self.agent_edit_area = QWidget()
        self.agent_layout = QVBoxLayout(self.agent_edit_area)
        layout.addWidget(self.agent_edit_area)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        add_agent_btn = QPushButton("Add Agent")
        add_agent_btn.clicked.connect(self._add_agent)
        button_layout.addWidget(add_agent_btn)
        
        button_layout.addStretch()
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        button_layout.addWidget(buttons)
        
        layout.addLayout(button_layout)
        
    def _load_teams(self):
        """Load teams from manager"""
        self.team_combo.clear()
        for team_name in self.team_manager.teams.keys():
            self.team_combo.addItem(team_name)
            
    def _on_team_changed(self, team_name):
        """Load selected team"""
        team = self.team_manager.get_team(team_name)
        if not team:
            return
        
        self.desc_input.setText(team.description)
        self._display_agents(team)
        
    def _display_agents(self, team: AgentTeam):
        """Display agents in list"""
        self.agents_list.clear()
        for agent in team.agents:
            item = QListWidgetItem(f"{agent.name} ({agent.role.value}) - {agent.model}")
            item.setData(Qt.ItemDataRole.UserRole, agent)
            self.agents_list.addItem(item)
            
    def _add_agent(self):
        """Add a new agent to current team"""
        team_name = self.team_combo.currentText()
        if not team_name:
            return
        
        team = self.team_manager.get_team(team_name)
        if not team:
            return
        
        # Create default agent
        agent = AgentConfig(
            name=f"Agent{len(team.agents)+1}",
            model="phi3:mini",
            provider="ollama",
            role=AgentRole.CODER
        )
        team.add_agent(agent)
        self._display_agents(team)
        
    def _create_new_team(self):
        """Create a new team"""
        name, ok = QMessageBox.question(
            self, "New Team",
            "Enter team name:",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        if ok and name:
            team = AgentTeam(name, "New team")
            self.team_manager.add_team(team)
            self.team_combo.addItem(name)
            self.team_combo.setCurrentText(name)
            
    def _delete_team(self):
        """Delete current team"""
        team_name = self.team_combo.currentText()
        if not team_name:
            return
        
        reply = QMessageBox.question(
            self, "Delete Team",
            f"Delete team '{team_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.team_manager.remove_team(team_name)
            self.team_combo.removeItem(self.team_combo.currentIndex())
            
    def accept(self):
        """Save teams and close"""
        # Update current team description
        team_name = self.team_combo.currentText()
        if team_name:
            team = self.team_manager.get_team(team_name)
            if team:
                team.description = self.desc_input.text()
        
        self.team_manager.save_teams()
        super().accept()
