"""
Actions for edit skill - enables editing files by replacing text
"""
from tools import create_tool_executor

def get_actions():
    """Return actions dictionary for edit skill"""
    return {
        "edit": lambda file_path, oldString, newString, replaceAll=False: _edit_file(file_path, oldString, newString, replaceAll),
        "replace": lambda file_path, oldString, newString: _edit_file(file_path, oldString, newString, False),
        "replace_all": lambda file_path, oldString, newString: _edit_file(file_path, oldString, newString, True),
    }

def _edit_file(file_path, oldString, newString, replaceAll=False):
    """Edit a file by replacing text using the EditTool"""
    try:
        # Get the project root from the current context
        import os
        root_path = os.getenv("CHUGAGPT_ROOT", ".")
        executor = create_tool_executor(root_path)
        result = executor.edit_tool.execute(file_path, oldString, newString, replaceAll)
        
        if result.get("success"):
            return f"Successfully edited {result.get('path')} ({result.get('replacements')} replacements)"
        else:
            return f"Error editing file: {result.get('error')}"
    except Exception as e:
        return f"Error: {e}"
