"""
Task sub-agent for exploration
Runs AI-powered exploration tasks in background
"""

import re
import threading
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path

class TaskResult:
    """Result from a task"""
    
    def __init__(self, task_id: str, task_type: str):
        self.task_id = task_id
        self.task_type = task_type
        self.status = "pending"
        self.result = ""
        self.error = ""
        self.data = {}
    
    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "data": self.data
        }


class ExploreTask:
    """Exploration task that runs in background"""
    
    def __init__(self):
        self.cancelled = False
    
    def cancel(self):
        self.cancelled = True


class TaskAgent:
    """Agent for running background tasks"""
    
    def __init__(self, model: str = "phi3:mini", ollama_path: str = "ollama"):
        self.model = model
        self.ollama_path = ollama_path
        self.running_tasks: Dict[str, ExploreTask] = {}
        self.completed_tasks: Dict[str, TaskResult] = {}
        self.lock = threading.Lock()
    
    def explore_codebase(self, root_path: str, pattern: str = "*.py") -> str:
        """Explore codebase and return file list"""
        task_id = f"explore_{len(self.running_tasks)}"
        
        with self.lock:
            self.running_tasks[task_id] = ExploreTask()
        
        try:
            from tools import create_tool_executor
            executor = create_tool_executor(root_path)
            result = executor.glob_tool.execute(pattern)
            
            task_result = TaskResult(task_id, "explore")
            task_result.status = "completed"
            task_result.result = result
            
            with self.lock:
                if task_id in self.running_tasks:
                    del self.running_tasks[task_id]
                self.completed_tasks[task_id] = task_result
            
            return result
        except Exception as e:
            task_result = TaskResult(task_id, "explore")
            task_result.status = "failed"
            task_result.error = str(e)
            
            with self.lock:
                if task_id in self.running_tasks:
                    del self.running_tasks[task_id]
                self.completed_tasks[task_id] = task_result
            
            return f"Error: {e}"
    
    def search_code(self, root_path: str, pattern: str, include: str = "") -> str:
        """Search code for pattern"""
        try:
            from tools import create_tool_executor
            executor = create_tool_executor(root_path)
            return executor.grep_tool.execute(pattern, include=include)
        except Exception as e:
            return f"Error: {e}"
    
    def read_file(self, root_path: str, file_path: str, limit: int = 100) -> str:
        """Read file content"""
        try:
            from tools import create_tool_executor
            executor = create_tool_executor(root_path)
            return executor.read_tool.execute(file_path, limit=limit)
        except Exception as e:
            return f"Error: {e}"
    
    def get_task_status(self, task_id: str) -> Optional[TaskResult]:
        """Get status of a task"""
        with self.lock:
            if task_id in self.running_tasks:
                result = TaskResult(task_id, "unknown")
                result.status = "running"
                return result
            return self.completed_tasks.get(task_id)
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task"""
        with self.lock:
            if task_id in self.running_tasks:
                self.running_tasks[task_id].cancel()
                return True
        return False
    
    def get_recent_results(self, limit: int = 10) -> List[Dict]:
        """Get recent completed tasks"""
        with self.lock:
            tasks = list(self.completed_tasks.values())[-limit:]
            return [t.to_dict() for t in tasks]


# Global task agent instance
_agent: Optional[TaskAgent] = None

def get_task_agent(model: str = "phi3:mini", ollama_path: str = "ollama") -> TaskAgent:
    """Get global task agent"""
    global _agent
    if _agent is None:
        _agent = TaskAgent(model, ollama_path)
    return _agent