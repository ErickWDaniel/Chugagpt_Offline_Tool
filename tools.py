import subprocess
import re
import os
import fnmatch
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
import threading

class GlobTool:
    def __init__(self, root_path: str = "."):
        self.root_path = Path(root_path)
        self.exclude_dirs = {'.git', '__pycache__', '.venv', 'node_modules', '.idea', 'build', 'dist', '.pytest_cache'}
        self.exclude_patterns = {'*.pyc', '*.pyo', '*.so', '*.dylib', '.DS_Store'}

    def execute(self, pattern: str, path: str = ".") -> str:
        try:
            search_path = self.root_path / path if path else self.root_path
            results = []
            
            for root, dirs, files in os.walk(search_path):
                dirs[:] = [d for d in dirs if d not in self.exclude_dirs]
                
                for filename in files:
                    if self._matches_pattern(filename, pattern):
                        rel_path = Path(root) / filename
                        try:
                            rel_path = rel_path.relative_to(self.root_path)
                        except ValueError:
                            rel_path = Path(root).joinpath(filename)
                        results.append(str(rel_path))
            
            results.sort()
            return self._format_results(results, pattern)
        except Exception as e:
            return f"Error: {str(e)}"

    def _matches_pattern(self, filename: str, pattern: str) -> bool:
        return fnmatch.fnmatch(filename.lower(), pattern.lower()) or fnmatch.fnmatch(filename, pattern)

    def _format_results(self, results: List[str], pattern: str) -> str:
        if not results:
            return f"No files matching '{pattern}'"
        
        output = f"# Glob: {pattern}\n\n"
        for r in results[:100]:
            output += f"{r}\n"
        
        if len(results) > 100:
            output += f"\n... and {len(results) - 100} more\n"
        
        return output


class GrepTool:
    def __init__(self, root_path: str = "."):
        self.root_path = Path(root_path)
        self.exclude_dirs = {'.git', '__pycache__', '.venv', 'node_modules', '.idea', 'build', 'dist'}
        self.file_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.c', '.cpp', '.h', '.go', '.rs', '.md', '.txt', '.json', '.yaml', '.yml', '.xml', '.sh', '.bash'}

    def execute(self, pattern: str, path: str = ".", include: str = "") -> str:
        try:
            search_path = self.root_path / path if path else self.root_path
            
            if include:
                exts = [f".{e.strip('.')}" for e in include.split(',')]
            else:
                exts = list(self.file_extensions)
            
            results = []
            filesearch = threading.Semaphore(8)
            
            def search_file(file_path: Path) -> Optional[Tuple[str, int, str]]:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                    
                    matches = []
                    regex = re.compile(pattern, re.IGNORECASE)
                    
                    for i, line in enumerate(lines, 1):
                        if regex.search(line):
                            matches.append((i, line.rstrip()))
                            if len(matches) >= 3:
                                break
                    
                    if matches:
                        return file_path, matches
                    return None
                except:
                    return None
            
            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = []
                for root, dirs, files in os.walk(search_path):
                    dirs[:] = [d for d in dirs if d not in self.exclude_dirs]
                    
                    for filename in files:
                        ext = Path(filename).suffix.lower()
                        if ext in exts or not include:
                            file_path = Path(root) / filename
                            futures.append(executor.submit(search_file, file_path))
                
                for future in futures:
                    result = future.result()
                    if result:
                        file_path, matches = result
                        try:
                            rel_path = file_path.relative_to(self.root_path)
                        except ValueError:
                            rel_path = file_path
                        
                        for line_num, line in matches[:3]:
                            results.append((str(rel_path), line_num, line))
            
            return self._format_results(results, pattern)
        except Exception as e:
            return f"Error: {str(e)}"

    def _format_results(self, results: List[Tuple[str, int, str]], pattern: str) -> str:
        if not results:
            return f"No matches found for '{pattern}'"
        
        output = f"# Grep: {pattern}\n\n"
        prev_file = None
        
        for file_path, line_num, line in results[:50]:
            if file_path != prev_file:
                output += f"\n{file_path}:\n"
                prev_file = file_path
            
            safe_line = line[:200] if len(line) > 200 else line
            output += f"  {line_num}: {safe_line}\n"
        
        if len(results) > 50:
            output += f"\n... and {len(results) - 50} more matches\n"
        
        return output


class ReadTool:
    def __init__(self, root_path: str = "."):
        self.root_path = Path(root_path)

    def execute(self, file_path: str, limit: int = 100, offset: int = 1) -> str:
        try:
            full_path = self.root_path / file_path
            
            if not full_path.exists():
                return f"Error: File not found: {file_path}"
            
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            total_lines = len(lines)
            end = min(offset - 1 + limit, total_lines)
            selected = lines[offset-1:end]
            
            output = f"# Read: {file_path} (lines {offset}-{end} of {total_lines})\n\n"
            
            for i, line in enumerate(selected, offset):
                safe_line = line.rstrip()
                if len(safe_line) > 200:
                    safe_line = safe_line[:200] + "..."
                output += f"{i}: {safe_line}\n"
            
            return output
        except Exception as e:
            return f"Error: {str(e)}"


class WriteTool:
    def __init__(self, root_path: str = "."):
        self.root_path = Path(root_path)

    def execute(self, file_path: str, content: str) -> Dict[str, Any]:
        try:
            full_path = self.root_path / file_path
            
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            lines = content.count('\n') + 1
            return {"success": True, "path": str(full_path), "lines": lines}
        except Exception as e:
            return {"success": False, "error": str(e)}


class EditTool:
    def __init__(self, root_path: str = "."):
        self.root_path = Path(root_path)

    def execute(self, file_path: str, oldString: str, newString: str, replaceAll: bool = False) -> Dict[str, Any]:
        try:
            full_path = self.root_path / file_path
            
            if not full_path.exists():
                return {"success": False, "error": "File not found"}
            
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if oldString not in content:
                return {"success": False, "error": "Text not found in file"}
            
            if replaceAll:
                new_content = content.replace(oldString, newString)
                count = content.count(oldString)
            else:
                new_content = content.replace(oldString, newString, 1)
                count = 1
            
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            return {"success": True, "path": str(full_path), "replacements": count}
        except Exception as e:
            return {"success": False, "error": str(e)}


class BashTool:
    def __init__(self, root_path: str = "."):
        self.root_path = Path(root_path)
    
    def execute(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.root_path,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            output = result.stdout
            if result.stderr:
                output += "\n" + result.stderr
            
            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": output[:5000],
                "stderr": result.stderr[:1000] if result.stderr else ""
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Command timed out after {timeout}s"}
        except Exception as e:
            return {"success": False, "error": str(e)}


class WebSearchTool:
    def execute(self, query: str, num_results: int = 5) -> str:
        try:
            result = subprocess.run(
                ["w3m", "-dump", f"https://ddg.gg/?q={query}"],
                capture_output=True,
                text=True,
                timeout=15
            )
            
            if result.returncode == 0:
                return f"# Search: {query}\n\n{result.stdout[:3000]}"
            else:
                return f"Search not available (w3m not installed)"
        except FileNotFoundError:
            return "Search not available (w3m not installed)"
        except Exception as e:
            return f"Search error: {str(e)}"


class WebFetchTool:
    def execute(self, url: str, format: str = "text") -> str:
        try:
            result = subprocess.run(
                ["curl", "-s", url],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                if format == "markdown":
                    return f"# Fetched: {url}\n\n{result.stdout[:10000]}"
                return result.stdout[:10000]
            else:
                return f"Fetch error: {result.stderr}"
        except FileNotFoundError:
            return "Fetch not available (curl not installed)"
        except Exception as e:
            return f"Fetch error: {str(e)}"


class ToolExecutor:
    def __init__(self, root_path: str = "."):
        self.root_path = Path(root_path)
        
        self.glob_tool = GlobTool(root_path)
        self.grep_tool = GrepTool(root_path)
        self.read_tool = ReadTool(root_path)
        self.write_tool = WriteTool(root_path)
        self.edit_tool = EditTool(root_path)
        self.bash_tool = BashTool(root_path)
        self.websearch_tool = WebSearchTool()
        self.webfetch_tool = WebFetchTool()
    
    def parse_and_execute(self, command: str) -> Dict[str, Any]:
        command = command.strip()
        
        # Parse glob command
        glob_match = re.match(r'^glob\s+(.+)$', command, re.IGNORECASE)
        if glob_match:
            pattern = glob_match.group(1).strip().strip('"').strip("'")
            return {"type": "glob", "result": self.glob_tool.execute(pattern)}
        
        # Parse grep command
        grep_match = re.match(r'^grep\s+["\'](.+)["\']\s*(?:--include\s+(.+))?$', command, re.IGNORECASE)
        if grep_match:
            pattern = grep_match.group(1)
            include = grep_match.group(2) or ""
            return {"type": "grep", "result": self.grep_tool.execute(pattern, include=include)}
        
        # Parse read command
        read_match = re.match(r'^read\s+(.+?)(?:\s+(\d+))?(?:\s+(\d+))?$', command, re.IGNORECASE)
        if read_match:
            file_path = read_match.group(1).strip()
            limit = int(read_match.group(2)) if read_match.group(2) else 100
            offset = int(read_match.group(3)) if read_match.group(3) else 1
            return {"type": "read", "result": self.read_tool.execute(file_path, limit, offset)}
        
        # Parse write command
        write_match = re.match(r'^write\s+(.+?)\s+["\'](.+?)["\']$', command, re.IGNORECASE)
        if write_match:
            file_path = write_match.group(1).strip()
            content = write_match.group(2)
            result = self.write_tool.execute(file_path, content)
            return {"type": "write", "result": f"Wrote to {result.get('path', file_path)} ({result.get('lines', 0)} lines)" if result.get('success') else result.get('error')}
        
        # Parse edit command
        edit_match = re.match(r'^edit\s+(.+?)\s+["\'](.*?)["\']\s+["\'](.*?)["\']$', command, re.IGNORECASE)
        if edit_match:
            file_path = edit_match.group(1).strip()
            oldString = edit_match.group(2)
            newString = edit_match.group(3)
            result = self.edit_tool.execute(file_path, oldString, newString)
            return {"type": "edit", "result": f"Edited {result.get('path', file_path)} ({result.get('replacements', 0)} replacements)" if result.get('success') else result.get('error')}
        
        # Parse bash command
        bash_match = re.match(r'^bash\s+(.+)$', command, re.IGNORECASE)
        if bash_match:
            cmd = bash_match.group(1).strip()
            result = self.bash_tool.execute(cmd)
            output = result.get("stdout", "") or result.get("stderr", "")
            return {"type": "bash", "result": output if result.get("success") else f"Error: {result.get('error', 'failed')}\n{output}"}
        
        # Parse websearch command
        ws_match = re.match(r'^websearch\s+(.+)$', command, re.IGNORECASE)
        if ws_match:
            query = ws_match.group(1).strip()
            return {"type": "websearch", "result": self.websearch_tool.execute(query)}
        
        # Parse webfetch command
        wf_match = re.match(r'^webfetch\s+(.+)$', command, re.IGNORECASE)
        if wf_match:
            url = wf_match.group(1).strip()
            return {"type": "webfetch", "result": self.webfetch_tool.execute(url)}
        
        return {"type": "unknown", "result": "Unknown command"}
    
    def get_tool_help(self) -> str:
        return """# Available CLI Tools

## glob
Find files matching a pattern.
Usage: glob **/*.py

## grep
Search for text patterns in files.
Usage: grep "function" --include *.py
Usage: grep "class" src/

## read
Read a file with optional line range.
Usage: read src/main.py
Usage: read src/main.py 50 10

## write
Write content to a file.
Usage: write path/to/file.py "content"

## edit
Replace text in a file.
Usage: edit path/to/file.py "old text" "new text"

## bash
Execute a shell command.
Usage: bash ls -la
Usage: bash git status

## websearch
Search the web (requires w3m or similar).
Usage: websearch python best practices

## webfetch
Fetch a URL (requires curl).
Usage: webfetch https://example.com
"""


def create_tool_executor(root_path: str = ".") -> ToolExecutor:
    return ToolExecutor(root_path)