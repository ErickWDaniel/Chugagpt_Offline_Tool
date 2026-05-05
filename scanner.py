import os
import ast
import json
import re
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

# Optional UI enhancements; fallback if not installed
try:
    from rich.console import Console
    from rich.progress import Progress
    from tqdm import tqdm
    console = Console()
except ImportError:
    console = None
    Progress = None
    tqdm = None

class BaseProjectScanner:
    """Base class for project scanning and analysis with shared logic."""
    
    def __init__(self, root_path: str = ".", max_workers: int = 8):
        """Initialize scanner with root path and max workers for parallel processing."""
        self.root_path = Path(root_path)
        self.exclude_dirs = {'.git', '__pycache__', '.venv', 'venv', 'node_modules', '.idea', 'build', 'dist', 'chugagpt_env', 'chugaGPT'}
        self.cancel_event = threading.Event()
        self.progress_callback: Optional[Callable[[str], None]] = None
        self.max_workers = max_workers
        self.advanced_analysis = False
        self.advanced_class_analysis = False
        self.advanced_function_analysis = False

    def cancel_scan(self):
        """Cancel the ongoing scan operation."""
        self.cancel_event.set()

    def _get_files(self) -> List[Path]:
        """Get all files in the project, excluding certain directories."""
        try:
            files = []
            for root, dirs, filenames in os.walk(self.root_path):
                dirs[:] = [d for d in dirs if d not in self.exclude_dirs]
                for filename in filenames:
                    files.append(Path(root) / filename)
            return files
        except Exception as e:
            if console:
                console.print(f"[red]Error walking directory: {e}[/]")
            raise

    def _analyze_file(self, file_path: Path) -> Dict[str, Any]:
        """Analyze a single file and return information."""
        try:
            info = {
                'size': file_path.stat().st_size,
                'extension': file_path.suffix,
                'type': self._get_file_type(file_path)
            }

            ext = file_path.suffix.lower()
            if ext == '.py':
                info.update(self._analyze_python_file(file_path))
            elif ext in {'.js', '.ts', '.java'}:
                info.update(self._analyze_simple_code(file_path))
            else:
                info['content_preview'] = self._get_content_preview(file_path)

            return info
        except Exception as e:
            return {'error': f"Failed to analyze {file_path}: {str(e)}"}

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

    def _get_content_preview(self, file_path: Path, max_chars: int = 200) -> str:
        """Get a preview of file content."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read(max_chars)
                return content + '...' if len(content) == max_chars else content
        except:
            return "[Binary or unreadable file]"

    def _collect_ast_elements(self, tree: ast.AST) -> Dict[str, Any]:
        """Collect AST elements, with optional advanced details."""
        classes = []
        functions = []
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_info = {
                    'name': node.name,
                    'line': node.lineno,
                    'methods': [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                }
                if self.advanced_class_analysis:
                    class_info['bases'] = [base.id if hasattr(base, 'id') else str(base) for base in node.bases]
                classes.append(class_info)
            elif isinstance(node, ast.FunctionDef):
                func_info = {
                    'name': node.name,
                    'line': node.lineno,
                    'args': [arg.arg for arg in node.args.args]
                }
                if self.advanced_function_analysis:
                    func_info['complexity'] = self._calculate_function_complexity(node)
                functions.append(func_info)
            elif isinstance(node, ast.Import):
                imports.extend([alias.name for alias in node.names])
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                imports.extend([f"{module}.{alias.name}" if module else alias.name for alias in node.names])

        return {'classes': classes, 'functions': functions, 'imports': imports}

    def _analyze_python_file(self, file_path: Path) -> Dict[str, Any]:
        """Semantic analysis of Python file using AST."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            info = {
                'type': 'Python',
                'classes': [],
                'functions': [],
                'imports': [],
                'used_imports': set(),
                'variables': [],
                'constants': [],
                'exceptions_handled': [],
                'todo_count': content.count('TODO') + content.count('FIXME'),
                'line_count': len(content.splitlines()),
                'complexity': self._calculate_complexity(tree),
                'docstrings': {'total_functions': 0, 'functions': 0},
                'semantic_issues': [],
                'data_flow': {},
                'control_flow': {},
                'security_issues': [],
            }
            
            # Semantic analysis
            self._analyze_semantic_python(tree, info, content)
            
            # Original analysis
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    info['classes'].append({
                        'name': node.name,
                        'line': node.lineno,
                        'methods': [m.name for m in ast.walk(node) if isinstance(m, ast.FunctionDef)],
                        'bases': [ast.unparse(b) for b in node.bases] if hasattr(ast, 'unparse') else [],
                    })
                elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                    # Check if it's not inside a class
                    parent = self._get_parent(tree, node)
                    if not isinstance(parent, ast.ClassDef):
                        args = [a.arg for a in node.args.args]
                        info['functions'].append({
                            'name': node.name,
                            'line': node.lineno,
                            'args': args,
                        })
                
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            info['imports'].append(alias.name)
                    else:
                        module = node.module or ''
                        for alias in node.names:
                            info['imports'].append(f"{module}.{alias.name}" if module else alias.name)
            
            # Deep semantic checks
            info['unused_imports'] = self._find_unused_imports_advanced(tree, info['imports'], content)
            info['docstrings'] = self._check_docstrings_advanced(tree)
            info['semantic_issues'].extend(self._detect_semantic_issues(tree, content))
            info['security_issues'] = self._detect_security_issues_advanced(tree, content)
            info['data_flow'] = self._analyze_data_flow(tree)
            info['control_flow'] = self._analyze_control_flow(tree)
            
            # Convert set to list for JSON serialization
            info['used_imports'] = list(info['used_imports'])
            
            return info
        except SyntaxError as e:
            return {'error': f"Python syntax error in {file_path}: {str(e)}"}
        except Exception as e:
            return {'error': f"Python analysis failed: {str(e)}"}
    
    def _analyze_semantic_python(self, tree: ast.AST, info: Dict, content: str):
        """Advanced semantic analysis."""
        try:
            # Detect dead code
            info['semantic_issues'].extend(self._find_dead_code(tree))
            
            # Detect code smells
            info['semantic_issues'].extend(self._detect_code_smells(tree, content))
            
            # Detect performance issues
            info['semantic_issues'].extend(self._detect_performance_issues(tree))
            
            # Check error handling
            info['exception_handling'] = self._analyze_exception_handling(tree)
            
        except Exception as e:
            info['semantic_issues'].append(f"Semantic analysis error: {str(e)}")
    
    def _calculate_complexity(self, tree: ast.AST) -> int:
        """Calculate cyclomatic complexity using AST."""
        complexity = 1
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                complexity += 1
            elif isinstance(node, ast.ExceptHandler):
                complexity += 1
            elif isinstance(node, (ast.And, ast.Or)):
                complexity += 1
            elif isinstance(node, ast.comprehension):
                complexity += 1
        return complexity
    
    def _find_unused_imports_advanced(self, tree: ast.AST, imports: List[str], content: str) -> List[str]:
        """Find unused imports using semantic analysis."""
        unused = []
        try:
            # Build a set of names actually used
            names_used = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                    names_used.add(node.id)
                elif isinstance(node, ast.Attribute):
                    if isinstance(node.value, ast.Name):
                        names_used.add(node.value.id)
            
            # Check each import
            for imp in imports:
                # Handle "from X import Y"
                if '.' in imp:
                    module, name = imp.rsplit('.', 1)
                    if name not in names_used and module not in names_used:
                        unused.append(imp)
                else:
                    if imp not in names_used:
                        unused.append(imp)
        except Exception:
            pass
        return unused
    
    def _check_docstrings_advanced(self, tree: ast.AST) -> Dict[str, Any]:
        """Check docstring coverage with semantic understanding."""
        total = 0
        with_docstring = 0
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                total += 1
                if ast.get_docstring(node):
                    with_docstring += 1
        
        return {
            'total_functions': total,
            'functions': with_docstring,
            'coverage': f"{with_docstring/total*100:.1f}%" if total > 0 else "0%"
        }
    
    def _detect_semantic_issues(self, tree: ast.AST, content: str) -> List[str]:
        """Detect semantic issues in code."""
        issues = []
        
        try:
            # Check for mutable default arguments
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    for default in node.args.defaults:
                        if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                            issues.append(f"Mutable default argument in {node.name} (line {node.lineno})")
            
            # Check for bare except clauses
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler):
                    if node.type is None:
                        issues.append(f"Bare 'except:' clause found (line {node.lineno}) - too broad")
            
            # Check for unused variables
            assigned = set()
            used = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            assigned.add(target.id)
                elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                    used.add(node.id)
            
            unused_vars = assigned - used
            for var in unused_vars:
                if not var.startswith('_'):
                    issues.append(f"Potentially unused variable: {var}")
                    
        except Exception as e:
            issues.append(f"Semantic analysis error: {str(e)}")
            
        return issues
    
    def _detect_security_issues_advanced(self, tree: ast.AST, content: str) -> List[str]:
        """Detect security issues using semantic analysis."""
        issues = []
        
        try:
            # Check for hardcoded secrets
            secret_patterns = ['password', 'secret', 'api_key', 'token', 'credential']
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            if any(p in target.id.lower() for p in secret_patterns):
                                # Check if it's assigned a string literal
                                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                                    if len(node.value.value) > 8:
                                        issues.append(f"Potential hardcoded secret: {target.id} (line {node.lineno})")
            
            # Check for SQL injection vulnerabilities
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute) and 'execute' in str(node.func.attr):
                        # Check if SQL query uses string formatting
                        for arg in node.args:
                            if isinstance(arg, (ast.BinOp, ast.JoinedStr)):
                                issues.append(f"Potential SQL injection risk (line {node.lineno})")
            
            # Check for eval/exec usage
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id in ['eval', 'exec', '__import__']:
                        issues.append(f"Dangerous function '{node.func.id}' used (line {node.lineno})")
            
            # Check for debug statements left in code
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id in ['print', 'pdb.set_trace', 'breakpoint']:
                        issues.append(f"Debug statement '{node.func.id}' found (line {node.lineno})")
                        
        except Exception as e:
            issues.append(f"Security analysis error: {str(e)}")
            
        return issues
    
    def _analyze_data_flow(self, tree: ast.AST) -> Dict[str, Any]:
        """Analyze data flow in the code."""
        flow = {
            'variables': {},
            'assignments': [],
            'potential_uninitialized': [],
        }
        
        try:
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            flow['assignments'].append({
                                'name': target.id,
                                'line': node.lineno,
                            })
        except Exception:
            pass
        
        return flow
    
    def _analyze_control_flow(self, tree: ast.AST) -> Dict[str, Any]:
        """Analyze control flow structure."""
        flow = {
            'if_count': 0,
            'loop_count': 0,
            'try_count': 0,
            'function_count': 0,
        }
        
        try:
            for node in ast.walk(tree):
                if isinstance(node, ast.If):
                    flow['if_count'] += 1
                elif isinstance(node, (ast.For, ast.While, ast.AsyncFor)):
                    flow['loop_count'] += 1
                elif isinstance(node, ast.Try):
                    flow['try_count'] += 1
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    flow['function_count'] += 1
        except Exception:
            pass
        
        return flow
    
    def _find_dead_code(self, tree: ast.AST) -> List[str]:
        """Find potentially dead code."""
        issues = []
        try:
            for node in ast.walk(tree):
                if isinstance(node, ast.If):
                    # Check for always-true/false conditions
                    if isinstance(node.test, ast.Constant):
                        if node.test.value is False:
                            issues.append(f"Dead code: if False block (line {node.lineno})")
                        elif node.test.value is True:
                            # The else block is dead
                            if node.orelse:
                                issues.append(f"Dead code: else block after if True (line {node.lineno})")
        except Exception:
            pass
        return issues
    
    def _detect_code_smells(self, tree: ast.AST, content: str) -> List[str]:
        """Detect code smells."""
        smells = []
        
        try:
            # Long parameter list
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    args = len(node.args.args)
                    if args > 5:
                        smells.append(f"Long parameter list in {node.name} ({args} params, line {node.lineno})")
            
            # Too many local variables
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    locals_count = len([n for n in ast.walk(node) if isinstance(n, ast.Assign)])
                    if locals_count > 15:
                        smells.append(f"Too many local variables in {node.name} (line {node.lineno})")
            
            # Deep nesting
            def check_nesting(node, depth=0):
                if depth > 4:
                    smells.append(f"Deep nesting detected (depth {depth}, line {node.lineno})")
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, (ast.If, ast.For, ast.While)):
                        check_nesting(child, depth + 1)
                    else:
                        check_nesting(child, depth)
            
            check_nesting(tree)
            
        except Exception as e:
            smells.append(f"Code smell detection error: {str(e)}")
        
        return smells
    
    def _analyze_exception_handling(self, tree: ast.AST) -> Dict[str, Any]:
        """Analyze exception handling quality."""
        result = {
            'total_try_blocks': 0,
            'bare_excepts': 0,
            'specific_excepts': 0,
        }
        
        try:
            for node in ast.walk(tree):
                if isinstance(node, ast.Try):
                    result['total_try_blocks'] += 1
                    for handler in node.handlers:
                        if handler.type is None:
                            result['bare_excepts'] += 1
                        else:
                            result['specific_excepts'] += 1
        except Exception:
            pass
        
        return result
    
    def _get_parent(self, tree: ast.AST, target_node: ast.AST) -> Optional[ast.AST]:
        """Find parent node of a given node."""
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                if child is target_node:
                    return node
        return None

    def _analyze_simple_code(self, file_path: Path) -> Dict[str, Any]:
        """Regex-based analysis for non-Python code (JS/TS/Java). Note: Approximate."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Improved regex for functions (handles arrow functions, async, etc.)
            func_regex = r"(?:(?:function|def|void)\s+|const\s+\w+\s*=\s*(?:async\s*)?\(|async\s*function\s*)(\w+)"
            class_regex = r"class\s+(\w+)"

            functions = re.findall(func_regex, content)
            classes = re.findall(class_regex, content)

            # Simple complexity heuristic
            complexity = len(re.findall(r"\b(if|for|while|try)\b", content)) + 1

            return {
                'classes': [{'name': c} for c in classes],
                'functions': [{'name': f} for f in functions],
                'line_count': len(content.splitlines()),
                'complexity': complexity,
                'content_preview': content[:500] + '...' if len(content) > 500 else content
            }
        except Exception as e:
            return {'error': f"Non-Python analysis failed: {str(e)}"}

    def _calculate_complexity(self, tree: ast.AST) -> int:
        """Calculate cyclomatic complexity of the file."""
        complexity = 1
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.For, ast.While, ast.Try)):
                complexity += 1
            elif isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
                complexity += len(node.values) - 1
        return complexity

    def _calculate_function_complexity(self, func_node: ast.FunctionDef) -> int:
        """Calculate complexity of a single function."""
        complexity = 1
        for node in ast.walk(func_node):
            if isinstance(node, (ast.If, ast.For, ast.While, ast.Try)):
                complexity += 1
            elif isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
                complexity += len(node.values) - 1
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

    def _detect_unused_imports(self, tree: ast.AST) -> List[str]:
        """Detect unused imports by comparing local imported names to used identifiers."""
        used_names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)}
        
        imported = []
        has_star_import = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name.split('.')[0]
                    imported.append(name)
            elif isinstance(node, ast.ImportFrom):
                if node.names and node.names[0].name == '*':
                    has_star_import = True
                    continue
                for alias in node.names:
                    name = alias.asname or alias.name
                    imported.append(name)
        
        unused = [imp for imp in imported if imp not in used_names]
        
        if has_star_import:
            unused.append('(Skipping unused check for star imports)')
        
        return unused

class ProjectScanner(BaseProjectScanner):
    """Simple project scanner for basic file information."""
    
    def scan_directory(self, progress_callback: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
        """Scan the project directory and return basic file information."""
        self.cancel_event.clear()
        self.progress_callback = progress_callback

        if console:
            console.print("[bold cyan]Starting project scan...[/]")

        files_info = {}
        files = self._get_files()

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self._analyze_file, f): f for f in files}
            progress_iter = as_completed(futures)
            if tqdm:
                progress_iter = tqdm(progress_iter, total=len(files), desc="Scanning files")
            for i, future in enumerate(progress_iter):
                if self.cancel_event.is_set():
                    break
                file_path = futures[future]
                if self.progress_callback:
                    self.progress_callback(f"Scanning {file_path.name}... ({i+1}/{len(files)})")
                rel_path = file_path.relative_to(self.root_path)
                try:
                    files_info[str(rel_path)] = future.result()
                except Exception as e:
                    files_info[str(rel_path)] = {'error': str(e)}

        if self.progress_callback:
            if self.cancel_event.is_set():
                self.progress_callback("Scan cancelled")
            else:
                self.progress_callback("Scan completed")
        if console:
            console.print("[green]Scan completed[/]" if not self.cancel_event.is_set() else "[yellow]Scan cancelled[/]")

        return files_info

def format_scan_results(scan_results: Dict[str, Any]) -> str:
    """Format scan results for display."""
    output = "# Project Scan Results\n\n"

    for file_path, info in scan_results.items():
        output += f"📄 {file_path}\n"
        output += f"   Type: {info.get('type', 'Unknown')}\n"
        output += f"   Size: {info.get('size', 0)} bytes\n"

        if 'classes' in info:
            classes = info.get('classes', [])
            if classes:
                output += f"   Classes: {', '.join([c['name'] for c in classes])}\n"
            functions = info.get('functions', [])
            if functions:
                output += f"   Functions: {', '.join([f['name'] for f in functions])}\n"
            imports = info.get('imports', [])
            if imports:
                output += f"   Imports: {', '.join(imports[:5])}{'...' if len(imports) > 5 else ''}\n"
            output += f"   Lines: {info.get('line_count', 0)}\n"

        output += "\n"

    return output

class ProjectAnalyzer(BaseProjectScanner):
    """Advanced project analyzer with architecture, issues, suggestions, dependencies, and security analysis."""
    
    def __init__(self, root_path: str = ".", max_workers: int = 8):
        """Initialize analyzer with root path and max workers."""
        super().__init__(root_path, max_workers)
        self.advanced_analysis = True
        self.advanced_class_analysis = True
        self.advanced_function_analysis = True
        
    def analyze_project(self, progress_callback: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
        """Perform comprehensive project analysis."""
        self.cancel_event.clear()
        self.progress_callback = progress_callback
        
        if console:
            console.print("[bold cyan]Starting enhanced project analysis...[/]")
        if self.progress_callback:
            self.progress_callback("Starting project analysis...")
        
        # Get all files
        files = self._get_files()
        
        # Parallel file analysis
        file_analysis = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self._analyze_file, f): f for f in files}
            progress_iter = as_completed(futures)
            if tqdm:
                progress_iter = tqdm(progress_iter, total=len(files), desc="Analyzing files")
            for i, future in enumerate(progress_iter):
                if self.cancel_event.is_set():
                    break
                file_path = futures[future]
                if self.progress_callback:
                    self.progress_callback(f"Analyzing {file_path.name}... ({i+1}/{len(files)})")
                rel_path = file_path.relative_to(self.root_path)
                try:
                    file_analysis[str(rel_path)] = future.result()
                except Exception as e:
                    file_analysis[str(rel_path)] = {'error': str(e)}
        
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
        
        # Dependencies
        if self.progress_callback:
            self.progress_callback("Analyzing dependencies...")
        dependencies = self._analyze_dependencies()
        
        # Security scan
        if self.progress_callback:
            self.progress_callback("Performing security scan...")
        security = self._security_scan(file_analysis)
        
        # File-specific feedback
        if self.progress_callback:
            self.progress_callback("Creating file-specific feedback...")
        file_feedback = self._generate_file_feedback(file_analysis)
        
        if self.progress_callback:
            if self.cancel_event.is_set():
                self.progress_callback("Analysis cancelled")
            else:
                self.progress_callback("Analysis completed")
        if console:
            console.print("[green]Analysis completed[/]" if not self.cancel_event.is_set() else "[yellow]Analysis cancelled[/]")

        return {
            'file_analysis': file_analysis,
            'architecture': architecture,
            'issues': issues,
            'suggestions': suggestions,
            'dependencies': dependencies,
            'security': security,
            'file_feedback': file_feedback,
            'summary': self._create_summary(file_analysis, architecture, issues, dependencies, security)
        }
    
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
            lower_path = file_path.lower()
            if 'main' in lower_path or 'app' in lower_path:
                architecture['main_modules'].append(file_path)
            elif 'util' in lower_path or 'helper' in lower_path:
                architecture['utils_modules'].append(file_path)
            elif 'test' in lower_path or 'spec' in lower_path:
                architecture['test_files'].append(file_path)
            elif 'config' in lower_path or 'settings' in lower_path:
                architecture['config_files'].append(file_path)
            
        # Statistics
            total_size += info.get('size',0)
            architecture['total_lines'] += info.get('line_count', 0)
        
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
            file_type = info.get('type', 'Unknown')
            if file_type not in {'Python', 'JavaScript', 'TypeScript', 'Java'}:
                continue
                
            # High complexity files
            if info.get('complexity', 0) > 10:
                issues['high_complexity_files'].append(f"{file_path} (complexity: {info.get('complexity', 0)})")
            
            # Missing docstrings (Python only)
            if file_type == 'Python':
                docstrings = info.get('docstrings', {})
                total_funcs = docstrings.get('total_functions', 0)
                if total_funcs > 0:
                    docstring_ratio = docstrings.get('functions', 0) / total_funcs
                    if docstring_ratio < 0.5:
                        issues['missing_docstrings'].append(f"{file_path} ({docstring_ratio:.1%} functions documented)")
                
                # Unused imports
                unused = info.get('unused_imports', [])
                if unused:
                    issues['unused_imports'].append(f"{file_path}: {', '.join(unused[:3])}{'...' if len(unused) > 3 else ''}")
            
            # Large files
            if info.get('line_count', 0) > 500:
                issues['large_files'].append(f"{file_path} ({info.get('line_count', 0)} lines)")
            
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
            'maintainability': [],
            'security': []
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
    
    def _analyze_dependencies(self) -> Dict[str, Any]:
        """Analyze project dependencies from requirements.txt, package.json, or pom.xml."""
        try:
            deps = {}
            req_files = ['requirements.txt', 'package.json', 'pom.xml']
            for req_name in req_files:
                req_file = self.root_path / req_name
                if req_file.exists():
                    if req_name == 'requirements.txt':
                        with open(req_file, 'r') as f:
                            deps[req_name] = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                    elif req_name == 'package.json':
                        with open(req_file, 'r') as f:
                            pkg = json.load(f)
                            deps[req_name] = list(pkg.get('dependencies', {}).keys()) + list(pkg.get('devDependencies', {}).keys())
                    elif req_name == 'pom.xml':
                        with open(req_file, 'r') as f:
                            content = f.read()
                            artifacts = re.findall(r'<artifactId>(.*?)</artifactId>', content)
                            deps[req_name] = artifacts
            return deps
        except Exception as e:
            if console:
                console.print(f"[red]Error analyzing dependencies: {e}[/]")
            return {'error': str(e)}
    
    def _security_scan(self, file_analysis: Dict[str, Any]) -> Dict[str, List[str]]:
        """Perform security scan for dangerous patterns."""
        warnings = []
        for file_path, info in file_analysis.items():
            file_type = info.get('type', 'Unknown')
            if file_type not in {'Python', 'JavaScript', 'TypeScript', 'Java'}:
                continue
            try:
                with open(self.root_path / file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # Python-specific
                if file_type == 'Python':
                    if 'eval(' in content or 'exec(' in content:
                        warnings.append(f"{file_path}: Potential use of eval/exec")
                    if 'subprocess' in content and 'shell=True' in content:
                        warnings.append(f"{file_path}: Subprocess with shell=True")
                    if 'os.system' in content:
                        warnings.append(f"{file_path}: Use of os.system")
                # JS/TS-specific
                elif file_type in {'JavaScript', 'TypeScript'}:
                    if 'eval(' in content:
                        warnings.append(f"{file_path}: Potential use of eval")
                    if 'new Function(' in content:
                        warnings.append(f"{file_path}: Dynamic function creation")
                # Java-specific
                elif file_type == 'Java':
                    if 'Runtime.getRuntime().exec' in content:
                        warnings.append(f"{file_path}: Runtime.exec command execution")
                    if 'ProcessBuilder' in content:
                        warnings.append(f"{file_path}: ProcessBuilder command execution")
            except:
                pass
        return {'warnings': warnings}
    
    def _generate_file_feedback(self, file_analysis: Dict[str, Any]) -> Dict[str, str]:
        """Generate specific feedback for each file."""
        feedback = {}
        
        for file_path, info in file_analysis.items():
            file_feedback = f"**{file_path}**\n"
            file_feedback += f"- Type: {info.get('type', 'Unknown')}\n"
            file_feedback += f"- Size: {info.get('size', 0)} bytes\n"
            
            if 'line_count' in info:
                file_feedback += f"- Lines of code: {info.get('line_count', 0)}\n"
            
            if 'classes' in info and info.get('classes'):
                file_feedback += f"- Classes: {len(info.get('classes', []))}\n"
            
            if 'functions' in info and info.get('functions'):
                file_feedback += f"- Functions: {len(info.get('functions', []))}\n"
            
            # Specific feedback
            if info.get('complexity', 0) > 10:
                file_feedback += "- ⚠️ High complexity - consider refactoring\n"
            
            if info.get('type') == 'Python':
                docstrings = info.get('docstrings', {})
                total_funcs = docstrings.get('total_functions', 0)
                if total_funcs > 0:
                    ratio = docstrings.get('functions', 0) / total_funcs
                    if ratio < 0.5:
                        file_feedback += f"- ⚠️ Low docstring coverage ({ratio:.1%})\n"
                
                if info.get('unused_imports'):
                    file_feedback += f"- ⚠️ Potential unused imports: {len(info.get('unused_imports', []))}\n"
            
            feedback[file_path] = file_feedback
        
        return feedback
    
    def _create_summary(self, file_analysis: Dict[str, Any], architecture: Dict[str, Any], issues: Dict[str, List[str]], dependencies: Dict[str, Any], security: Dict[str, Any]) -> Dict[str, Any]:
        """Create a summary of the analysis."""
        return {
            'total_files': architecture['total_files'],
            'total_lines': architecture['total_lines'],
            'languages': architecture['languages'],
            'issues_count': sum(len(issues_list) for issues_list in issues.values()),
            'main_modules': len(architecture['main_modules']),
            'test_coverage': len(architecture['test_files']) / max(1, architecture['total_files']),
            'dependencies_count': sum(len(deps) for deps in dependencies.values()),
            'security_warnings': len(security.get('warnings', []))
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
        output += f"- **Test Coverage:** {summary['test_coverage']:.1%}\n"
        output += f"- **Dependencies Count:** {summary['dependencies_count']}\n"
        output += f"- **Security Warnings:** {summary['security_warnings']}\n\n"
        
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
        
        # Dependencies
        deps = results['dependencies']
        if deps:
            output += "## Dependencies\n"
            for file_name, dep_list in deps.items():
                output += f"### From {file_name}\n"
                output += f"{', '.join(dep_list[:10])}{'...' if len(dep_list) > 10 else ''}\n\n"
        
        # Security
        security = results['security']
        if security.get('warnings'):
            output += "## Security Warnings\n"
            for warning in security['warnings'][:10]:
                output += f"- {warning}\n"
            if len(security['warnings']) > 10:
                output += f"- ... and {len(security['warnings']) - 10} more\n\n"
        
        # Issues
        issues = results['issues']
        if any(issues.values()):
            output += "## Issues Detected\n"
            for category, issue_list in issues.items():
                if issue_list:
                    output += f"### {category.replace('_', ' ').title()}\n"
                    for issue in issue_list[:10]:
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
                if i >= 10:
                    output += f"... and {len(feedback) - 10} more files analyzed\n"
                    break
                output += f"{file_feedback}\n"
        
        return output