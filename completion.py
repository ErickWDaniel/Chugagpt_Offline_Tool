import subprocess
import time
import os
import re
from typing import List, Dict, Optional, Tuple
from PySide6.QtCore import QThread, Signal, QObject, QTimer
from PySide6.QtWidgets import QApplication
from utils import clean_output
import select

class CompletionSuggestion:
    """Represents a single code completion suggestion."""
    
    def __init__(self, text: str, confidence: float = 0.0, display_text: str = None):
        self.text = text
        self.confidence = confidence
        self.display_text = display_text or text
    
    def __str__(self):
        return f"CompletionSuggestion(text='{self.text}', confidence={self.confidence})"

class CompletionContext:
    """Context information for generating completions."""
    
    def __init__(self):
        self.current_line: str = ""
        self.cursor_position: int = 0
        self.lines_before: List[str] = []
        self.lines_after: List[str] = []
        self.language: str = "python"
        self.file_path: str = ""
    
    def get_context_window(self, max_lines: int = 10) -> str:
        """Get a context window around the current line."""
        context_lines = []
        
        # Add lines before current line (in reverse order)
        for line in reversed(self.lines_before[-max_lines:]):
            context_lines.insert(0, line)
        
        # Add current line
        context_lines.append(self.current_line)
        
        # Add lines after current line
        context_lines.extend(self.lines_after[:max_lines])
        
        return "\n".join(context_lines)

class CompletionEngine(QObject):
    """Main completion engine that manages suggestions and context."""
    
    suggestions_ready = Signal(list)  # List[CompletionSuggestion]
    completion_accepted = Signal(str)  # Accepted completion text
    
    def __init__(self, ollama_path: str = "ollama", model: str = "deepseek-coder:6.7b"):
        super().__init__()
        self.ollama_path = ollama_path
        self.model = model
        self.current_context = CompletionContext()
        self.is_enabled = True
        self.debounce_timer = QTimer()
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.timeout.connect(self._generate_suggestions)
        self.debounce_delay = 300  # ms
        # Track active worker and request ids to avoid stale emissions and premature destruction
        self._worker = None
        self._request_counter = 0
        self._active_workers: List[QThread] = []
    
    def set_context(self, context: CompletionContext):
        """Update the current completion context."""
        self.current_context = context
        if self.is_enabled:
            self.debounce_timer.start(self.debounce_delay)
    
    def enable(self):
        """Enable code completion."""
        self.is_enabled = True
    
    def disable(self):
        """Disable code completion."""
        self.is_enabled = False
        self.debounce_timer.stop()
    
    def accept_suggestion(self, suggestion: CompletionSuggestion):
        """Accept a completion suggestion."""
        self.completion_accepted.emit(suggestion.text)
    
    def _generate_suggestions(self):
        """Generate completion suggestions based on current context."""
        if not self.is_enabled or not self.current_context.current_line:
            return
        
        # Increment request id and cancel any previous worker
        self._request_counter += 1
        req_id = self._request_counter
        # Preserve reference to previous worker so it isn't GC'd prematurely
        old_worker = self._worker
        try:
            if old_worker and old_worker.isRunning():
                if hasattr(old_worker, "stop"):
                    old_worker.stop()
                old_worker.requestInterruption()
                # Keep old worker referenced until it finishes
                if old_worker not in self._active_workers:
                    self._active_workers.append(old_worker)
        except Exception:
            pass
        # Create and retain a worker reference so it isn't GC'd while running
        self._worker = CompletionWorker(self.current_context, self.ollama_path, self.model)
        self._active_workers.append(self._worker)
        # Route through an internal handler so we can discard stale results
        self._worker.suggestions_ready.connect(lambda suggestions, rid=req_id: self._on_worker_suggestions_ready(rid, suggestions))
        # Ensure proper cleanup: remove from active list and delete later
        self._worker.finished.connect(lambda w=self._worker: self._on_worker_finished_ref(w))
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()
    
    def _on_suggestions_ready(self, suggestions: List[CompletionSuggestion]):
        """Handle suggestions ready from worker."""
        self.suggestions_ready.emit(suggestions)
    
    def _on_worker_suggestions_ready(self, rid: int, suggestions: List[CompletionSuggestion]):
        """Emit only if this response matches the latest request id."""
        if rid == self._request_counter:
            self.suggestions_ready.emit(suggestions)
    
    def _on_worker_finished_ref(self, w: QThread):
        """Remove worker reference when finished and clear current if it matches."""
        try:
            if w in self._active_workers:
                self._active_workers.remove(w)
        except Exception:
            pass
        if self._worker is w:
            self._worker = None

    def stop_all(self):
        """Stop any running completion worker and wait briefly for clean shutdown."""
        try:
            if self._worker and self._worker.isRunning():
                if hasattr(self._worker, "stop"):
                    self._worker.stop()
                self._worker.requestInterruption()
                try:
                    self._worker.wait(2000)
                except Exception:
                    pass
            # Also stop any additional active workers
            for w in list(self._active_workers):
                try:
                    if hasattr(w, "stop"):
                        w.stop()
                    w.requestInterruption()
                    w.wait(2000)
                except Exception:
                    pass
                finally:
                    try:
                        self._active_workers.remove(w)
                    except Exception:
                        pass
        except Exception:
            pass
        finally:
            self._worker = None

class CompletionWorker(QThread):
    """Worker thread for generating completion suggestions."""
    
    suggestions_ready = Signal(list)  # List[CompletionSuggestion]
    
    def __init__(self, context: CompletionContext, ollama_path: str, model: str):
        super().__init__()
        self.context = context
        self.ollama_path = ollama_path
        self.model = model
        self._stop_flag = False
        self.process = None
    
    def run(self):
        """Generate completion suggestions."""
        try:
            suggestions = self._generate_completions()
            self.suggestions_ready.emit(suggestions)
        except Exception as e:
            # Emit empty list on error
            self.suggestions_ready.emit([])
    
    def _generate_completions(self) -> List[CompletionSuggestion]:
        """Generate completion suggestions using Ollama."""
        # Get the current line and cursor position
        line = self.context.current_line
        cursor_pos = self.context.cursor_position
        
        # Only generate if cursor is at end of line or in middle
        if cursor_pos < len(line.rstrip()):
            return []
        
        # Get prefix (text before cursor)
        prefix = line[:cursor_pos]
        
        # Skip if prefix is too short or ends with space
        if len(prefix.strip()) < 2 or prefix.endswith(' '):
            return []
        
        # Build completion prompt
        prompt = self._build_completion_prompt()
        
        if not prompt:
            return []
        
        # Get completion from Ollama
        completion_text = self._get_ollama_completion(prompt)
        
        if not completion_text:
            return []
        
        # Parse and filter suggestions
        suggestions = self._parse_completions(completion_text)
        
        return suggestions[:5]  # Limit to 5 suggestions
    
    def _build_completion_prompt(self) -> str:
        """Build a completion prompt based on context."""
        context_window = self.context.get_context_window()
        
        # Create a focused completion prompt
        prompt = f"""You are a code completion assistant. Complete the following code intelligently.

Context:
{context_window}

Complete the code above. Provide only the completion text, no explanations.
Focus on completing the current line or adding the next logical line(s).
Keep completions concise but complete."""

        return prompt
    
    def _get_ollama_completion(self, prompt: str) -> str:
        """Get completion from Ollama model."""
        try:
            args = [self.ollama_path, "run", self.model, prompt]
            # Set environment to reduce noise
            env = os.environ.copy()
            env.setdefault("OLLAMA_NO_COLOR", "1")
            env.setdefault("NO_COLOR", "1")
            env.setdefault("CLICOLOR", "0")
            env.setdefault("TERM", "dumb")
            # Launch process with PIPE to support incremental non-blocking reads
            self.process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env
            )
            process = self.process
            start_time = time.time()
            hard_timeout_sec = 10
            output_parts: List[str] = []
            while True:
                # Cooperative stop and timeout
                if self._stop_flag or self.isInterruptionRequested():
                    try:
                        process.terminate()
                    except Exception:
                        pass
                    return ""
                if time.time() - start_time > hard_timeout_sec:
                    try:
                        process.terminate()
                    except Exception:
                        pass
                    return ""
                if process.stdout is None:
                    break
                # Non-blocking readiness check
                try:
                    rlist, _, _ = select.select([process.stdout], [], [], 0.05)
                except Exception:
                    rlist = []
                if rlist:
                    chunk = process.stdout.read(1)
                    if chunk:
                        output_parts.append(chunk)
                        continue
                # If process ended and no data available, break
                if process.poll() is not None:
                    break
            return clean_output("".join(output_parts)).strip()
        except Exception:
            return ""
    
    def _parse_completions(self, completion_text: str) -> List[CompletionSuggestion]:
        """Parse completion text into suggestion objects."""
        suggestions = []
        
        if not completion_text:
            return suggestions
        
        # Split by lines and filter
        lines = completion_text.split('\n')
        
        # Take first non-empty line as primary suggestion
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('//'):
                # Clean up the completion
                completion = self._clean_completion(line)
                if completion:
                    suggestions.append(CompletionSuggestion(
                        text=completion,
                        confidence=0.8  # Default confidence
                    ))
                    break
        
        # If we have a primary suggestion, generate variations
        if suggestions:
            primary = suggestions[0].text
            # Add some common variations
            variations = self._generate_variations(primary)
            for var in variations[:4]:  # Limit variations
                suggestions.append(CompletionSuggestion(
                    text=var,
                    confidence=0.6
                ))
        
        return suggestions
    
    def _clean_completion(self, text: str) -> str:
        """Clean up completion text."""
        # Remove common artifacts
        text = re.sub(r'^[^\w]*', '', text)  # Remove leading non-word chars
        text = text.rstrip()
        
        # Limit length
        if len(text) > 100:
            text = text[:100].rstrip()
        
        return text
    
    def _generate_variations(self, base_completion: str) -> List[str]:
        """Generate variations of a completion."""
        variations = []
        
        # Add semicolon if missing (for languages that use it)
        if self.context.language in ['javascript', 'typescript', 'java', 'c', 'cpp'] and not base_completion.endswith(';'):
            variations.append(base_completion + ';')
        
        # Add closing brace for some patterns
        if base_completion.endswith('{'):
            variations.append(base_completion + '\n    \n}')
        
        return variations

    def stop(self):
        """Cooperatively stop this worker and terminate its process if running."""
        try:
            self._stop_flag = True
            if self.process and self.process.poll() is None:
                self.process.terminate()
        except Exception:
            pass