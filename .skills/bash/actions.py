"""
Actions for bash skill - enables executing shell commands
"""
from tools import create_tool_executor

def get_actions():
    """Return actions dictionary for bash skill"""
    return {
        "bash": lambda command: _run_bash(command),
        "execute": lambda command: _run_bash(command),
        "run": lambda command: _run_bash(command),
    }

def _run_bash(command):
    """Execute a bash command using the BashTool"""
    try:
        # Get the project root from the current context
        import os
        root_path = os.getenv("CHUGAGPT_ROOT", ".")
        executor = create_tool_executor(root_path)
        result = executor.bash_tool.execute(command)
        
        if result.get("success"):
            output = result.get("stdout", "")
            if result.get("stderr"):
                output += "\n" + result.get("stderr")
            return output[:2000]  # Limit output length
        else:
            return f"Error executing command: {result.get('error', 'unknown error')}"
    except Exception as e:
        return f"Error: {e}"
