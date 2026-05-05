"""
Actions for write skill - enables writing content to files
"""
from tools import create_tool_executor

def get_actions():
    """Return actions dictionary for write skill"""
    return {
        "write": lambda file_path, content: _write_file(file_path, content),
        "create_file": lambda file_path, content="": _write_file(file_path, content),
    }

def _write_file(file_path, content):
    """Write content to a file using the WriteTool"""
    try:
        # Get the project root from the current context
        import os
        root_path = os.getenv("CHUGAGPT_ROOT", ".")
        executor = create_tool_executor(root_path)
        result = executor.write_tool.execute(file_path, content)
        
        if result.get("success"):
            return f"Successfully wrote to {result.get('path')} ({result.get('lines')} lines)"
        else:
            return f"Error writing file: {result.get('error')}"
    except Exception as e:
        return f"Error: {e}"
