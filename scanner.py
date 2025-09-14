import os
import ast
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
import threading

class ProjectScanner:
    def __init__(self, root_path: str = "."):
        self.root_path = Path(root_path)
        self.exclude_dirs = {'.git', '__pycache__', '.venv', 'node_modules', '.idea', 'build', 'dist'}
        self.cancel_event = threading.Event()
        self.progress_callback: Optional[Callable[[str], None]] = None

    def scan_directory(self, progress_callback: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
        """Scan the project directory and return file information."""
        self.cancel_event.clear()
        self.progress_callback = progress_callback

        files_info = {}
        files = self._get_files()

        for i, file_path in enumerate(files):
            if self.cancel_event.is_set():
                break

            if self.progress_callback:
                self.progress_callback(f"Scanning {file_path.name}... ({i+1}/{len(files)})")

            rel_path = file_path.relative_to(self.root_path)
            files_info[str(rel_path)] = self._analyze_file(file_path)

        if self.progress_callback:
            if self.cancel_event.is_set():
                self.progress_callback("Scan cancelled")
            else:
                self.progress_callback("Scan completed")

        return files_info

    def cancel_scan(self):
        """Cancel the ongoing scan operation."""
        self.cancel_event.set()

    def _get_files(self) -> List[Path]:
        """Get all files in the project, excluding certain directories."""
        files = []
        for root, dirs, filenames in os.walk(self.root_path):
            # Remove excluded directories
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]
            for filename in filenames:
                files.append(Path(root) / filename)
        return files

    def _analyze_file(self, file_path: Path) -> Dict[str, Any]:
        """Analyze a single file and return information."""
        info = {
            'size': file_path.stat().st_size,
            'extension': file_path.suffix,
            'type': self._get_file_type(file_path)
        }

        if file_path.suffix == '.py':
            info.update(self._analyze_python_file(file_path))
        else:
            info['content_preview'] = self._get_content_preview(file_path)

        return info

    def _get_file_type(self, file_path: Path) -> str:
        """Determine file type based on extension."""
        ext = file_path.suffix.lower()
        type_map = {
            '.py': 'Python',
            '.json': 'JSON',
            '.txt': 'Text',
            '.md': 'Markdown',
            '.html': 'HTML',
            '.css': 'CSS',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.cpp': 'C++',
            '.c': 'C',
            '.java': 'Java'
        }
        return type_map.get(ext, 'Unknown')

    def _analyze_python_file(self, file_path: Path) -> Dict[str, Any]:
        """Analyze Python file using AST."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content, filename=str(file_path))

            analysis = {
                'classes': [],
                'functions': [],
                'imports': [],
                'line_count': len(content.splitlines()),
                'content_preview': content[:500] + '...' if len(content) > 500 else content
            }

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    analysis['classes'].append({
                        'name': node.name,
                        'line': node.lineno,
                        'methods': [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                    })
                elif isinstance(node, ast.FunctionDef):
                    analysis['functions'].append({
                        'name': node.name,
                        'line': node.lineno,
                        'args': [arg.arg for arg in node.args.args]
                    })
                elif isinstance(node, ast.Import):
                    analysis['imports'].extend([alias.name for alias in node.names])
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    analysis['imports'].extend([f"{module}.{alias.name}" if module else alias.name for alias in node.names])

            return analysis
        except Exception as e:
            return {'error': str(e)}

    def _get_content_preview(self, file_path: Path, max_chars: int = 200) -> str:
        """Get a preview of file content."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read(max_chars)
                return content + '...' if len(content) == max_chars else content
        except:
            return "[Binary or unreadable file]"

def format_scan_results(scan_results: Dict[str, Any]) -> str:
    """Format scan results for display."""
    output = "Project Scan Results:\n\n"

    for file_path, info in scan_results.items():
        output += f"📄 {file_path}\n"
        output += f"   Type: {info.get('type', 'Unknown')}\n"
        output += f"   Size: {info['size']} bytes\n"

        if 'classes' in info:
            if info['classes']:
                output += f"   Classes: {', '.join([c['name'] for c in info['classes']])}\n"
            if info['functions']:
                output += f"   Functions: {', '.join([f['name'] for f in info['functions']])}\n"
            if info['imports']:
                output += f"   Imports: {', '.join(info['imports'][:5])}{'...' if len(info['imports']) > 5 else ''}\n"
            output += f"   Lines: {info.get('line_count', 0)}\n"

        output += "\n"

    return output

class ProjectAnalyzer:
    """Advanced project analyzer with architecture analysis, issue detection, and improvement suggestions."""
    
    def __init__(self, root_path: str = "."):
        self.root_path = Path(root_path)
        self.exclude_dirs = {'.git', '__pycache__', '.venv', 'node_modules', '.idea', 'build', 'dist', '__pycache__'}
        self.cancel_event = threading.Event()
        self.progress_callback: Optional[Callable[[str], None]] = None
        
    def analyze_project(self, progress_callback: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
        """Perform comprehensive project analysis."""
        self.cancel_event.clear()
        self.progress_callback = progress_callback
        
        if self.progress_callback:
            self.progress_callback("Starting project analysis...")
        
        # Get all files
        files = self._get_files()
        
        # Basic file analysis
        file_analysis = {}
        for i, file_path in enumerate(files):
            if self.cancel_event.is_set():
                break
            if self.progress_callback:
                self.progress_callback(f"Analyzing {file_path.name}... ({i+1}/{len(files)})")
            rel_path = file_path.relative_to(self.root_path)
            file_analysis[str(rel_path)] = self._analyze_file(file_path)
        
        # Architecture analysis
        if self.progress_callback:
            self.progress_callback("Analyzing project architecture...")
        architecture = self._analyze_architecture(file_analysis)
        
        # Issue detection
        if self.progress_callback:
            self.progress_callback("Detecting potential issues...")
        issues = self._detect_issues(file_analysis)
        
        # Improvement suggestions
        if self.progress_callback:
            self.progress_callback("Generating improvement suggestions...")
        suggestions = self._generate_suggestions(file_analysis, architecture, issues)
        
        # File-specific feedback
        if self.progress_callback:
            self.progress_callback("Creating file-specific feedback...")
        file_feedback = self._generate_file_feedback(file_analysis)
        
        if self.progress_callback:
            if self.cancel_event.is_set():
                self.progress_callback("Analysis cancelled")
            else:
                self.progress_callback("Analysis completed")
        
        return {
            'file_analysis': file_analysis,
            'architecture': architecture,
            'issues': issues,
            'suggestions': suggestions,
            'file_feedback': file_feedback,
            'summary': self._create_summary(file_analysis, architecture, issues)
        }
    
    def cancel_scan(self):
        """Cancel the ongoing analysis operation."""
        self.cancel_event.set()
    
    def _get_files(self) -> List[Path]:
        """Get all files in the project, excluding certain directories."""
        files = []
        for root, dirs, filenames in os.walk(self.root_path):
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]
            for filename in filenames:
                files.append(Path(root) / filename)
        return files
    
    def _analyze_file(self, file_path: Path) -> Dict[str, Any]:
        """Analyze a single file and return information."""
        info = {
            'size': file_path.stat().st_size,
            'extension': file_path.suffix,
            'type': self._get_file_type(file_path)
        }
        
        if file_path.suffix == '.py':
            info.update(self._analyze_python_file(file_path))
        else:
            info['content_preview'] = self._get_content_preview(file_path)
        
        return info
    
    def _get_file_type(self, file_path: Path) -> str:
        """Determine file type based on extension."""
        ext = file_path.suffix.lower()
        type_map = {
            '.py': 'Python',
            '.json': 'JSON',
            '.txt': 'Text',
            '.md': 'Markdown',
            '.html': 'HTML',
            '.css': 'CSS',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.cpp': 'C++',
            '.c': 'C',
            '.java': 'Java'
        }
        return type_map.get(ext, 'Unknown')
    
    def _analyze_python_file(self, file_path: Path) -> Dict[str, Any]:
        """Analyze Python file using AST."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content, filename=str(file_path))
            
            analysis = {
                'classes': [],
                'functions': [],
                'imports': [],
                'line_count': len(content.splitlines()),
                'content_preview': content[:500] + '...' if len(content) > 500 else content,
                'complexity': self._calculate_complexity(tree),
                'docstrings': self._check_docstrings(tree),
                'unused_imports': self._detect_unused_imports(content, tree)
            }
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    analysis['classes'].append({
                        'name': node.name,
                        'line': node.lineno,
                        'methods': [n.name for n in node.body if isinstance(n, ast.FunctionDef)],
                        'bases': [base.id if hasattr(base, 'id') else str(base) for base in node.bases]
                    })
                elif isinstance(node, ast.FunctionDef):
                    analysis['functions'].append({
                        'name': node.name,
                        'line': node.lineno,
                        'args': [arg.arg for arg in node.args.args],
                        'complexity': self._calculate_function_complexity(node)
                    })
                elif isinstance(node, ast.Import):
                    analysis['imports'].extend([alias.name for alias in node.names])
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    analysis['imports'].extend([f"{module}.{alias.name}" if module else alias.name for alias in node.names])
            
            return analysis
        except Exception as e:
            return {'error': str(e)}
    
    def _calculate_complexity(self, tree: ast.AST) -> int:
        """Calculate cyclomatic complexity of the file."""
        complexity = 1  # Base complexity
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.For, ast.While, ast.Try)):
                complexity += 1
            elif isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And):
                complexity += len(node.values) - 1
        return complexity
    
    def _calculate_function_complexity(self, func_node: ast.FunctionDef) -> int:
        """Calculate complexity of a single function."""
        complexity = 1
        for node in ast.walk(func_node):
            if isinstance(node, (ast.If, ast.For, ast.While, ast.Try)):
                complexity += 1
        return complexity
    
    def _check_docstrings(self, tree: ast.AST) -> Dict[str, int]:
        """Check if functions and classes have docstrings."""
        docstrings = {'functions': 0, 'classes': 0, 'total_functions': 0, 'total_classes': 0}
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                docstrings['total_functions'] += 1
                if ast.get_docstring(node):
                    docstrings['functions'] += 1
            elif isinstance(node, ast.ClassDef):
                docstrings['total_classes'] += 1
                if ast.get_docstring(node):
                    docstrings['classes'] += 1
        
        return docstrings
    
    def _detect_unused_imports(self, content: str, tree: ast.AST) -> List[str]:
        """Detect potentially unused imports."""
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend([alias.name for alias in node.names])
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                imports.extend([f"{module}.{alias.name}" if module else alias.name for alias in node.names])
        
        # Simple heuristic: check if import names appear in the content
        unused = []
        for imp in imports:
            base_name = imp.split('.')[-1]
            if base_name not in content:
                unused.append(imp)
        
        return unused
    
    def _get_content_preview(self, file_path: Path, max_chars: int = 200) -> str:
        """Get a preview of file content."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read(max_chars)
                return content + '...' if len(content) == max_chars else content
        except:
            return "[Binary or unreadable file]"
    
    def _analyze_architecture(self, file_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze the overall project architecture."""
        architecture = {
            'languages': {},
            'main_modules': [],
            'utils_modules': [],
            'test_files': [],
            'config_files': [],
            'total_files': len(file_analysis),
            'total_lines': 0,
            'avg_file_size': 0
        }
        
        total_size = 0
        for file_path, info in file_analysis.items():
            # Language distribution
            lang = info.get('type', 'Unknown')
            architecture['languages'][lang] = architecture['languages'].get(lang, 0) + 1
            
            # Categorize files
            if 'main' in file_path.lower() or 'app' in file_path.lower():
                architecture['main_modules'].append(file_path)
            elif 'util' in file_path.lower() or 'helper' in file_path.lower():
                architecture['utils_modules'].append(file_path)
            elif 'test' in file_path.lower() or 'spec' in file_path.lower():
                architecture['test_files'].append(file_path)
            elif 'config' in file_path.lower() or 'settings' in file_path.lower():
                architecture['config_files'].append(file_path)
            
            # Statistics
            total_size += info.get('size', 0)
            if 'line_count' in info:
                architecture['total_lines'] += info['line_count']
        
        if architecture['total_files'] > 0:
            architecture['avg_file_size'] = total_size / architecture['total_files']
        
        return architecture
    
    def _detect_issues(self, file_analysis: Dict[str, Any]) -> Dict[str, List[str]]:
        """Detect potential issues in the codebase."""
        issues = {
            'high_complexity_files': [],
            'missing_docstrings': [],
            'unused_imports': [],
            'large_files': [],
            'potential_bugs': []
        }
        
        for file_path, info in file_analysis.items():
            if info.get('type') != 'Python':
                continue
                
            # High complexity files
            if info.get('complexity', 0) > 10:
                issues['high_complexity_files'].append(f"{file_path} (complexity: {info['complexity']})")
            
            # Missing docstrings
            docstrings = info.get('docstrings', {})
            if docstrings.get('total_functions', 0) > 0:
                docstring_ratio = docstrings.get('functions', 0) / docstrings['total_functions']
                if docstring_ratio < 0.5:
                    issues['missing_docstrings'].append(f"{file_path} ({docstring_ratio:.1%} functions documented)")
            
            # Unused imports
            unused = info.get('unused_imports', [])
            if unused:
                issues['unused_imports'].append(f"{file_path}: {', '.join(unused[:3])}{'...' if len(unused) > 3 else ''}")
            
            # Large files
            if info.get('line_count', 0) > 500:
                issues['large_files'].append(f"{file_path} ({info['line_count']} lines)")
            
            # Potential bugs (simple heuristics)
            content = info.get('content_preview', '')
            if 'TODO' in content or 'FIXME' in content or 'XXX' in content:
                issues['potential_bugs'].append(f"{file_path} contains TODO/FIXME comments")
        
        return issues
    
    def _generate_suggestions(self, file_analysis: Dict[str, Any], architecture: Dict[str, Any], issues: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """Generate improvement suggestions."""
        suggestions = {
            'architecture': [],
            'code_quality': [],
            'performance': [],
            'maintainability': []
        }
        
        # Architecture suggestions
        if len(architecture['main_modules']) == 0:
            suggestions['architecture'].append("Consider creating a main entry point file (main.py, app.py, etc.)")
        
        if len(architecture['test_files']) == 0:
            suggestions['architecture'].append("Add unit tests to improve code reliability")
        
        # Code quality suggestions
        if issues['high_complexity_files']:
            suggestions['code_quality'].append("Refactor high-complexity functions into smaller, more focused functions")
        
        if issues['missing_docstrings']:
            suggestions['code_quality'].append("Add docstrings to all public functions and classes")
        
        if issues['unused_imports']:
            suggestions['code_quality'].append("Remove unused imports to clean up the codebase")
        
        # Performance suggestions
        if architecture['avg_file_size'] > 100000:  # 100KB
            suggestions['performance'].append("Consider breaking large files into smaller modules")
        
        # Maintainability suggestions
        if architecture['total_files'] > 50:
            suggestions['maintainability'].append("Consider organizing code into packages/submodules")
        
        return suggestions
    
    def _generate_file_feedback(self, file_analysis: Dict[str, Any]) -> Dict[str, str]:
        """Generate specific feedback for each file."""
        feedback = {}
        
        for file_path, info in file_analysis.items():
            file_feedback = f"**{file_path}**\n"
            file_feedback += f"- Type: {info.get('type', 'Unknown')}\n"
            file_feedback += f"- Size: {info.get('size', 0)} bytes\n"
            
            if info.get('type') == 'Python':
                if 'line_count' in info:
                    file_feedback += f"- Lines of code: {info['line_count']}\n"
                
                if 'classes' in info and info['classes']:
                    file_feedback += f"- Classes: {len(info['classes'])}\n"
                
                if 'functions' in info and info['functions']:
                    file_feedback += f"- Functions: {len(info['functions'])}\n"
                
                # Specific feedback
                if info.get('complexity', 0) > 10:
                    file_feedback += "- ⚠️  High complexity - consider refactoring\n"
                
                docstrings = info.get('docstrings', {})
                if docstrings.get('total_functions', 0) > 0:
                    ratio = docstrings.get('functions', 0) / docstrings['total_functions']
                    if ratio < 0.5:
                        file_feedback += f"- ⚠️  Low docstring coverage ({ratio:.1%})\n"
                
                if info.get('unused_imports'):
                    file_feedback += f"- ⚠️  Potential unused imports: {len(info['unused_imports'])}\n"
            
            feedback[file_path] = file_feedback
        
        return feedback
    
    def _create_summary(self, file_analysis: Dict[str, Any], architecture: Dict[str, Any], issues: Dict[str, List[str]]) -> Dict[str, Any]:
        """Create a summary of the analysis."""
        return {
            'total_files': architecture['total_files'],
            'total_lines': architecture['total_lines'],
            'languages': architecture['languages'],
            'issues_count': sum(len(issues_list) for issues_list in issues.values()),
            'main_modules': len(architecture['main_modules']),
            'test_coverage': len(architecture['test_files']) / max(1, architecture['total_files'])
        }
    
    def format_analysis_results(self, results: Dict[str, Any]) -> str:
        """Format the complete analysis results for display."""
        output = "# Project Analysis Report\n\n"
        
        # Summary
        summary = results['summary']
        output += "## Summary\n"
        output += f"- **Total Files:** {summary['total_files']}\n"
        output += f"- **Total Lines:** {summary['total_lines']}\n"
        output += f"- **Languages:** {', '.join([f'{lang}: {count}' for lang, count in summary['languages'].items()])}\n"
        output += f"- **Issues Found:** {summary['issues_count']}\n"
        output += f"- **Main Modules:** {summary['main_modules']}\n"
        output += f"- **Test Coverage:** {summary['test_coverage']:.1%}\n\n"
        
        # Architecture
        arch = results['architecture']
        output += "## Architecture Overview\n"
        if arch['main_modules']:
            output += f"**Main Modules:** {', '.join(arch['main_modules'][:5])}{'...' if len(arch['main_modules']) > 5 else ''}\n"
        if arch['utils_modules']:
            output += f"**Utility Modules:** {', '.join(arch['utils_modules'][:5])}{'...' if len(arch['utils_modules']) > 5 else ''}\n"
        if arch['test_files']:
            output += f"**Test Files:** {len(arch['test_files'])}\n"
        if arch['config_files']:
            output += f"**Configuration Files:** {', '.join(arch['config_files'])}\n\n"
        
        # Issues
        issues = results['issues']
        if any(issues.values()):
            output += "## Issues Detected\n"
            for category, issue_list in issues.items():
                if issue_list:
                    output += f"### {category.replace('_', ' ').title()}\n"
                    for issue in issue_list[:10]:  # Limit to 10 per category
                        output += f"- {issue}\n"
                    if len(issue_list) > 10:
                        output += f"- ... and {len(issue_list) - 10} more\n"
                    output += "\n"
        
        # Suggestions
        suggestions = results['suggestions']
        if any(suggestions.values()):
            output += "## Improvement Suggestions\n"
            for category, suggestion_list in suggestions.items():
                if suggestion_list:
                    output += f"### {category.title()}\n"
                    for suggestion in suggestion_list:
                        output += f"- {suggestion}\n"
                    output += "\n"
        
        # File-specific feedback (first 10 files)
        feedback = results['file_feedback']
        if feedback:
            output += "## File-Specific Feedback\n"
            for i, (file_path, file_feedback) in enumerate(feedback.items()):
                if i >= 10:  # Limit to first 10 files
                    output += f"... and {len(feedback) - 10} more files analyzed\n"
                    break
                output += f"{file_feedback}\n"
        
        return output
