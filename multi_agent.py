"""
Multi-Agent System for ChugaGPT
Implements Anthropic-style agentic AI with tool use, team collaboration
Supports agents creating other agents (self-replicating teams)
"""

import json
import time
from typing import Dict, List, Any, Optional
from enum import Enum
from pathlib import Path
import subprocess


class AgentRole(Enum):
    """Different agent roles for team collaboration"""
    COORDINATOR = "coordinator"  # Main orchestrator
    CODER = "coder"  # Code generation specialist
    ANALYST = "analyst"  # Code analysis specialist
    REVIEWER = "reviewer"  # Code review specialist
    RESEARCHER = "researcher"  # Information gathering
    EXECUTOR = "executor"  # Tool execution specialist
    CREATOR = "creator"  # Agent that can create other agents


class AgentConfig:
    """Configuration for a single agent"""
    
    def __init__(self, name: str, model: str, provider: str, role: AgentRole, 
                 system_prompt: str = "", tools_enabled: bool = True,
                 can_create_agents: bool = False):
        self.name = name
        self.model = model
        self.provider = provider
        self.role = role
        self.system_prompt = system_prompt
        self.tools_enabled = tools_enabled
        self.max_iterations = 10
        self.can_create_agents = can_create_agents  # New: can this agent spawn others?
        
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "model": self.model,
            "provider": self.provider,
            "role": self.role.value,
            "system_prompt": self.system_prompt,
            "tools_enabled": self.tools_enabled,
            "max_iterations": self.max_iterations,
            "can_create_agents": self.can_create_agents,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AgentConfig':
        return cls(
            name=data.get("name", "Agent"),
            model=data.get("model", "phi3:mini"),
            provider=data.get("provider", "ollama"),
            role=AgentRole(data.get("role", "coder")),
            system_prompt=data.get("system_prompt", ""),
            tools_enabled=data.get("tools_enabled", True),
            can_create_agents=data.get("can_create_agents", False),
        )


class AgentTeam:
    """A team of agents working together - supports dynamic agent creation"""
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.agents: List[AgentConfig] = []
        self.coordinator = None
        self._next_agent_id = 0
        
    def add_agent(self, agent: AgentConfig):
        """Add an agent to the team"""
        self.agents.append(agent)
        if agent.role == AgentRole.COORDINATOR:
            self.coordinator = agent
            
    def create_agent(self, name: str, model: str, provider: str, 
                      role: AgentRole = AgentRole.CODER) -> AgentConfig:
        """Create a new agent (used by creator agents)"""
        self._next_agent_id += 1
        agent = AgentConfig(
            name=f"{name}_{self._next_agent_id}",
            model=model,
            provider=provider,
            role=role,
            system_prompt=f"You are {name}, a {role.value} agent created by the team.",
            tools_enabled=True,
        )
        self.agents.append(agent)
        return agent
        
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "agents": [a.to_dict() for a in self.agents]
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AgentTeam':
        team = cls(
            name=data.get("name", "Default Team"),
            description=data.get("description", "")
        )
        for agent_data in data.get("agents", []):
            team.add_agent(AgentConfig.from_dict(agent_data))
        return team


# Default agent teams
DEFAULT_TEAMS = {
    "development": AgentTeam(
        name="Development Team",
        description="Full development team with multiple specialists"
    ),
    "quick_analysis": AgentTeam(
        name="Quick Analysis",
        description="Fast single-agent analysis"
    ),
    "self_replicating": AgentTeam(
        name="Self-Replicating Team",
        description="Agents can create other agents dynamically"
    ),
}

DEFAULT_TEAMS["development"].agents = [
    AgentConfig("Coordinator", "claude-3-5-sonnet-20241022", "anthropic", AgentRole.COORDINATOR,
                 system_prompt="You are the coordinator. Break down tasks and delegate to specialists."),
    AgentConfig("Coder", "gpt-4o", "openai", AgentRole.CODER,
                 system_prompt="You are a coding specialist. Write clean, efficient code."),
    AgentConfig("Analyst", "phi3:mini", "ollama", AgentRole.ANALYST,
                 system_prompt="You are a code analyst. Analyze code quality and issues."),
]

DEFAULT_TEAMS["quick_analysis"].agents = [
    AgentConfig("Analyst", "phi3:mini", "ollama", AgentRole.ANALYST,
                 system_prompt="You are a quick analysis agent. Provide concise insights."),
]

DEFAULT_TEAMS["self_replicating"].agents = [
    AgentConfig("Creator", "llama3:8b", "ollama", AgentRole.CREATOR,
                 system_prompt="You are a creator agent. You can create other agents when needed. "
                            "To create an agent, respond with: CREATE_AGENT: name,model,provider,role",
                 can_create_agents=True),
    AgentConfig("Worker1", "phi3:mini", "ollama", AgentRole.CODER,
                 system_prompt="You are a worker agent."),
]


class TeamManager:
    """Manages multiple agent teams"""
    
    def __init__(self, config_file: str = "agent_teams.json"):
        self.config_file = Path(config_file)
        self.teams: Dict[str, AgentTeam] = {}
        self._load_teams()
        
    def _load_teams(self):
        """Load teams from config file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                for team_name, team_data in data.items():
                    self.teams[team_name] = AgentTeam.from_dict(team_data)
            except Exception:
                self.teams = DEFAULT_TEAMS.copy()
        else:
            self.teams = DEFAULT_TEAMS.copy()
            
    def save_teams(self):
        """Save teams to config file"""
        try:
            data = {name: team.to_dict() for name, team in self.teams.items()}
            with open(self.config_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving teams: {e}")
            
    def get_team(self, name: str) -> Optional[AgentTeam]:
        """Get a team by name"""
        return self.teams.get(name)
    
    def add_team(self, team: AgentTeam):
        """Add a new team"""
        self.teams[team.name] = team
        self.save_teams()
            
    def remove_team(self, name: str):
        """Remove a team"""
        if name in self.teams:
            del self.teams[name]
            self.save_teams()


class MultiAgentWorker:
    """Worker that orchestrates multiple agents - supports creator agents"""
    
    def __init__(self, team: AgentTeam, prompt: str, project_root: str = "."):
        self.team = team
        self.prompt = prompt
        self.project_root = project_root
        self.stop_flag = False
        self._current_agent = None
        self._created_agents: List[AgentConfig] = []  # Track dynamically created agents
        
    def stop(self):
        """Stop all agents"""
        self.stop_flag = True
        if self._current_agent:
            try:
                self._current_agent.stop_generation()
            except Exception:
                pass
                
    def execute(self) -> str:
        """Execute the multi-agent workflow with creator support"""
        results = []
        agents_to_run = list(self.team.agents)  # Copy list
        
        # Start with coordinator or first agent
        if self.team.coordinator:
            # Move coordinator to front
            agents_to_run = [self.team.coordinator] + [a for a in agents_to_run if a != self.team.coordinator]
            
        for agent in agents_to_run:
            if self.stop_flag:
                break
                
            result = self._execute_agent(agent, results)
            results.append(result)
            
            # Check if this agent created new agents
            if agent.can_create_agents and agent.role == AgentRole.CREATOR:
                new_agents = self._parse_created_agents(result, agent)
                for new_agent in new_agents:
                    self.team.agents.append(new_agent)
                    agents_to_run.append(new_agent)  # They'll be executed later in this loop
                    
        return "\n".join(results)
        
    def _execute_agent(self, agent: AgentConfig, previous_results: List[str]) -> str:
        """Execute a single agent"""
        output = []
        output.append(f"\n{'='*60}")
        output.append(f"Agent: {agent.name} ({agent.role.value})")
        output.append(f"Model: {agent.model} [{agent.provider}]")
        output.append(f"{'='*60}\n")
        
        # Build agent-specific prompt
        agent_prompt = self._build_agent_prompt(agent, previous_results)
        
        # Execute with appropriate provider
        try:
            if agent.provider == "ollama":
                result = self._run_ollama_agent(agent, agent_prompt)
            elif agent.provider == "ollama_cloud":
                result = self._run_ollama_cloud_agent(agent, agent_prompt)
            elif agent.provider == "openai":
                result = self._run_openai_agent(agent, agent_prompt)
            elif agent.provider == "anthropic":
                result = self._run_anthropic_agent(agent, agent_prompt)
            else:
                result = f"[Error: Unknown provider {agent.provider}]"
                    
            output.append(result)
        except Exception as e:
            output.append(f"[Error: {str(e)}]")
            
        return "\n".join(output)
    
    def _parse_created_agents(self, result: str, creator: AgentConfig) -> List[AgentConfig]:
        """Parse agent creation commands from creator agent output"""
        created = []
        # Look for CREATE_AGENT: name,model,provider,role
        import re
        pattern = r'CREATE_AGENT:\s*(\w+),\s*([\w:]+),\s*(\w+),\s*(\w+)'
        matches = re.findall(pattern, result)
        
        for match in matches:
            name, model, provider, role_str = match
            try:
                role = AgentRole(role_str.lower())
            except ValueError:
                role = AgentRole.CODER
            agent = self.team.create_agent(name, model, provider, role)
            created.append(agent)
            
        return created
    
    def _build_agent_prompt(self, agent: AgentConfig, previous_results: List[str]) -> str:
        """Build prompt for specific agent"""
        parts = []
        
        # System prompt
        if agent.system_prompt:
            parts.append(f"System: {agent.system_prompt}\n")
            
        # Previous results from other agents
        if previous_results:
            parts.append("Previous agent results:")
            # Join last 500 characters
            combined = "\n".join(previous_results)
            if len(combined) > 500:
                parts.append(combined[-500:])
            else:
                parts.append(combined)
            parts.append("\n")
            
        # Current task
        parts.append(f"Task: {self.prompt}")
        
        # Tools instruction
        if agent.tools_enabled:
            parts.append("\nYou can use tools: glob, grep, read, write, edit, bash")
            parts.append("Wrap tool calls in <tool>...</tool> tags")
            
        # Creator instruction
        if agent.can_create_agents:
            parts.append("\nAs a creator agent, you can create other agents by responding with:")
            parts.append("CREATE_AGENT: name,model,provider,role")
            parts.append("Example: CREATE_AGENT: researcher,phi3:mini,ollama,researcher")
            
        return "\n".join(parts)
    
    def _run_ollama_agent(self, agent: AgentConfig, prompt: str) -> str:
        """Run Ollama agent (local)"""
        try:
            result = subprocess.run(
                ["ollama", "run", agent.model, prompt],
                capture_output=True,
                text=True,
                timeout=300
            )
            return result.stdout if result.returncode == 0 else result.stderr
        except Exception as e:
            return f"Ollama error: {str(e)}"
        
    def _run_ollama_cloud_agent(self, agent: AgentConfig, prompt: str) -> str:
        """Run Ollama agent using free cloud models"""
        try:
            # Ollama cloud: `ollama run --remote modelname`
            result = subprocess.run(
                ["ollama", "run", "--remote", agent.model, prompt],
                capture_output=True,
                text=True,
                timeout=300
            )
            return result.stdout if result.returncode == 0 else result.stderr
        except Exception as e:
            return f"Ollama Cloud error: {str(e)}"
    
    def _run_openai_agent(self, agent: AgentConfig, prompt: str) -> str:
        """Run OpenAI agent"""
        try:
            import openai
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=agent.model,
                messages=[{"role": "user", "content": prompt}],
                stream=False
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"OpenAI error: {str(e)}"
    
    def _run_anthropic_agent(self, agent: AgentConfig, prompt: str) -> str:
        """Run Anthropic agent (agentic AI)"""
        try:
            import anthropic
            client = anthropic.Anthropic()
            
            # Anthropic supports tool use (agentic behavior)
            response = client.messages.create(
                model=agent.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            return f"Anthropic error: {str(e)}"


def get_available_teams() -> List[str]:
    """Get list of available team names"""
    manager = TeamManager()
    return list(manager.teams.keys())


def execute_team(team_name: str, prompt: str, project_root: str = ".") -> str:
    """Execute a team of agents"""
    manager = TeamManager()
    team = manager.get_team(team_name)
    
    if not team:
        return f"Team '{team_name}' not found"
        
    worker = MultiAgentWorker(team, prompt, project_root)
    return worker.execute()
