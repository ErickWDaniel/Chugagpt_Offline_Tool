"""
Skill Loader for offline capabilities
Allows loading skill definitions from local directory for extended functionality
"""

import os
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable

class Skill:
    """Represents a single skill with triggers and actions"""
    
    def __init__(self, name: str, description: str = "", triggers: List[str] = None, 
                 actions: Dict[str, Callable] = None, metadata: Dict = None):
        self.name = name
        self.description = description
        self.triggers = triggers or []
        self.actions = actions or {}
        self.metadata = metadata or {}
    
    def matches(self, prompt: str) -> bool:
        """Check if prompt matches any trigger"""
        prompt_lower = prompt.lower()
        for trigger in self.triggers:
            if trigger.lower() in prompt_lower:
                return True
        return False
    
    def execute(self, action_name: str, *args, **kwargs) -> Any:
        """Execute a named action"""
        if action_name in self.actions:
            return self.actions[action_name](*args, **kwargs)
        return None


class SkillLoader:
    """Load and manage skills from local files"""
    
    def __init__(self, skills_dir: str = ".skills"):
        self.skills_dir = Path(skills_dir)
        self.skills: Dict[str, Skill] = {}
        self._loaded = False
    
    def load_skills(self) -> List[str]:
        """Load all skills from the skills directory"""
        loaded = []
        
        if not self.skills_dir.exists():
            return loaded
        
        for item in self.skills_dir.iterdir():
            if item.is_dir():
                skill = self._load_skill(item)
                if skill:
                    self.skills[skill.name] = skill
                    loaded.append(skill.name)
            elif item.suffix == '.json':
                skill = self._load_skill_json(item)
                if skill:
                    self.skills[skill.name] = skill
                    loaded.append(skill.name)
        
        self._loaded = True
        return loaded
    
    def _load_skill(self, skill_dir: Path) -> Optional[Skill]:
        """Load a skill from directory"""
        # Check for skill.json
        skill_file = skill_dir / "skill.json"
        if not skill_file.exists():
            return None
        
        try:
            with open(skill_file, 'r') as f:
                data = json.load(f)
            
            name = data.get('name', skill_dir.name)
            description = data.get('description', '')
            triggers = data.get('triggers', [])
            
            # Load actions if available
            actions = {}
            actions_file = skill_dir / "actions.py"
            if actions_file.exists():
                import importlib.util
                spec = importlib.util.spec_from_file_location(f"{name}_actions", actions_file)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, 'get_actions'):
                    actions = module.get_actions()
            
            return Skill(name, description, triggers, actions, data)
        except Exception as e:
            print(f"Error loading skill {skill_dir}: {e}")
            return None
    
    def _load_skill_json(self, skill_file: Path) -> Optional[Skill]:
        """Load a skill from a single JSON file"""
        try:
            with open(skill_file, 'r') as f:
                data = json.load(f)
            
            name = data.get('name', skill_file.stem)
            description = data.get('description', '')
            triggers = data.get('triggers', [])
            
            return Skill(name, description, triggers, {}, data)
        except Exception as e:
            print(f"Error loading skill {skill_file}: {e}")
            return None
    
    def get_skill(self, name: str) -> Optional[Skill]:
        """Get a skill by name"""
        return self.skills.get(name)
    
    def find_matching_skills(self, prompt: str) -> List[Skill]:
        """Find all skills that match the prompt"""
        return [s for s in self.skills.values() if s.matches(prompt)]
    
    def get_available_skills(self) -> List[str]:
        """Get list of available skill names"""
        return list(self.skills.keys())
    
    def get_skill_help(self) -> str:
        """Get help text for all skills"""
        if not self.skills:
            return "No skills loaded. Add skills to .skills directory."
        
        help_text = "# Available Skills\n\n"
        for name, skill in self.skills.items():
            help_text += f"## {name}\n"
            help_text += f"{skill.description}\n"
            help_text += f"Triggers: {', '.join(skill.triggers)}\n\n"
        
        return help_text


class OpenCodeSkills:
    """Pre-configured skills similar to opencode"""
    
    @staticmethod
    def create_skills(root_path: str = ".") -> SkillLoader:
        """Create skill loader with built-in skills"""
        loader = SkillLoader(os.path.join(root_path, ".skills"))
        
        # Add built-in skills
        built_in_skills = {
            "explore": Skill(
                "explore",
                "Explore codebase with glob, read, and grep tools",
                ["explore", "find files", "search code", "what files", "show structure"],
                {
                    "glob": lambda p, ptn: f"# Files matching {ptn}\n" + str(list(Path(p).glob(ptn))),
                    "grep": lambda p, pattern: f"# Search: {pattern}",
                }
            ),
            "code_analysis": Skill(
                "code_analysis",
                "Analyze code quality, complexity, and issues",
                ["analyze code", "review code", "check quality", "lint"],
                {}
            ),
            "read_file": Skill(
                "read_file",
                "Read and display file contents",
                ["read", "show", "view", "cat"],
                {}
            ),
        }
        
        # Merge with loaded skills
        loader.load_skills()
        for name, skill in built_in_skills.items():
            if name not in loader.skills:
                loader.skills[name] = skill
        
        return loader


# Global skill loader instance
_global_loader: Optional[SkillLoader] = None

def get_skill_loader(root_path: str = ".") -> SkillLoader:
    """Get global skill loader instance"""
    global _global_loader
    if _global_loader is None:
        _global_loader = OpenCodeSkills.create_skills(root_path)
    return _global_loader