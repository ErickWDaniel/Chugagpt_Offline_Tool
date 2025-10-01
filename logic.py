import subprocess
import time
import os
import re
import threading
from PySide6.QtCore import QThread, Signal
from utils import clean_output, AnsiStreamSanitizer

class ResponseBuffer:
    """Buffer system for smoother response display"""

    def __init__(self, chunk_size=50, flush_interval=0.1):
        self.chunk_size = chunk_size
        self.flush_interval = flush_interval
        self.buffer = ""
        self.lock = threading.Lock()
        self.last_flush = time.time()

    def append(self, text):
        """Append text to buffer and flush if needed"""
        with self.lock:
            self.buffer += text
            current_time = time.time()

            # Flush if buffer is full or enough time has passed
            should_flush = (
                len(self.buffer) >= self.chunk_size or
                (current_time - self.last_flush) >= self.flush_interval
            )

            if should_flush:
                content = self.buffer
                self.buffer = ""
                self.last_flush = current_time
                return content
            return None

    def flush(self):
        """Force flush remaining buffer content"""
        with self.lock:
            if self.buffer:
                content = self.buffer
                self.buffer = ""
                self.last_flush = time.time()
                return content
            return None

class ResponseValidator:
    """Validates response quality and completeness"""

    def __init__(self):
        self.thinking_pattern = re.compile(r'<ThoughtProcess>(.*?)</ThoughtProcess>', re.DOTALL)
        self.response_pattern = re.compile(r'<Response>(.*?)</Response>', re.DOTALL)
        self.code_block_pattern = re.compile(r'```(\w+)?\s*\n(.*?)```', re.DOTALL)

    def validate_response(self, response):
        """Validate response structure and quality"""
        issues = []

        # Check for incomplete tags
        if '<ThoughtProcess>' in response and '</ThoughtProcess>' not in response:
            issues.append("Incomplete thinking section")
        if '<Response>' in response and '</Response>' not in response:
            issues.append("Incomplete response section")

        # Check for incomplete code blocks
        code_blocks = self.code_block_pattern.findall(response)
        for block in code_blocks:
            if block[1].strip() and not block[1].endswith('```'):
                issues.append("Incomplete code block detected")

        # Check for extremely short responses (might indicate error)
        clean_response = self.response_pattern.sub('', response)
        clean_response = self.thinking_pattern.sub('', clean_response)
        if len(clean_response.strip()) < 10:
            issues.append("Response appears to be too short")

        return issues

class EnhancedOllamaWorker(QThread):
    """Enhanced worker with chunk-based streaming and better error handling"""

    stop_requested = Signal()
    new_chunk = Signal(str)  # Changed from new_char to new_chunk
    finished_signal = Signal()
    progress_update = Signal(str)
    error_signal = Signal(str)

    def __init__(self, model, prompt, ollama_path="ollama", allow_long_analysis=False):
        super().__init__()
        self.model = model
        self.prompt = prompt
        self.ollama_path = ollama_path
        self.stop_flag = False
        self.process = None
        self.allow_long_analysis = allow_long_analysis
        self._ansi_sanitizer = AnsiStreamSanitizer()
        self.response_buffer = ResponseBuffer()
        self.validator = ResponseValidator()
        self.full_response = ""

    def stop_generation(self):
        """Stop the ongoing generation."""
        self.stop_flag = True
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                # Give it a moment to terminate gracefully
                time.sleep(0.1)
                if self.process.poll() is None:
                    self.process.kill()
            except Exception:
                pass

    def _emit_filtered(self, text: str):
        """Process and emit filtered text in chunks"""
        cleaned = self._ansi_sanitizer.push(text)
        self.full_response += cleaned

        # Check for response quality issues
        issues = self.validator.validate_response(self.full_response)
        if issues:
            self.progress_update.emit(f"Response quality: {', '.join(issues[:2])}")

        # Buffer the text and emit chunks
        chunk = self.response_buffer.append(cleaned)
        if chunk:
            self.new_chunk.emit(chunk)

    def _flush_buffer(self):
        """Flush any remaining buffered content"""
        remaining = self.response_buffer.flush()
        if remaining:
            self.new_chunk.emit(remaining)

    def run(self):
        try:
            args = [self.ollama_path, "run", self.model, self.prompt]
            # Reduce ANSI noise when possible
            env = os.environ.copy()
            env.setdefault("OLLAMA_NO_COLOR", "1")
            env.setdefault("NO_COLOR", "1")
            env.setdefault("CLICOLOR", "0")
            env.setdefault("TERM", "dumb")

            if os.name == "posix":
                # Use a pseudo-tty to encourage real-time streaming from Ollama
                try:
                    import pty, select
                    master_fd, slave_fd = pty.openpty()
                    self.process = subprocess.Popen(
                        args,
                        stdout=slave_fd,
                        stderr=subprocess.STDOUT,
                        stdin=subprocess.DEVNULL,
                        env=env,
                        close_fds=True,
                    )
                    process = self.process
                    os.close(slave_fd)
                    try:
                        start_time = time.time()
                        timeout = None if self.allow_long_analysis else 300
                        chunk_buffer = ""

                        while True:
                            # Check for stop request
                            if self.stop_flag:
                                self.new_chunk.emit("\n[Generation Stopped]\n")
                                process.terminate()
                                break

                            # Check for timeout
                            if timeout is not None and time.time() - start_time > timeout:
                                self.new_chunk.emit(f"\n[Timeout] Response took too long, terminating...\n")
                                process.terminate()
                                break

                            # If process exited and no more data, break
                            if process.poll() is not None:
                                r, _, _ = select.select([master_fd], [], [], 0)
                                if not r:
                                    break
                            r, _, _ = select.select([master_fd], [], [], 0.05)
                            if not r:
                                continue
                            data = os.read(master_fd, 8192)  # Read in larger chunks
                            if not data:
                                if process.poll() is not None:
                                    break
                                continue
                            text = data.decode(errors="ignore")
                            self._emit_filtered(text)
                    finally:
                        try:
                            os.close(master_fd)
                        except OSError:
                            pass
                except Exception:
                    # Fallback to PIPE below if PTY is unavailable or fails
                    process = None
            else:
                process = None

            if process is None:
                # Enhanced fallback: use PIPE with chunk-based reading
                self.process = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=8192,  # Larger buffer
                    env=env,
                )
                process = self.process
                start_time = time.time()
                timeout = None if self.allow_long_analysis else 300

                while True:
                    # Check for stop request
                    if self.stop_flag:
                        self.new_chunk.emit("\n[Generation Stopped]\n")
                        process.terminate()
                        break

                    # Check for timeout
                    if timeout is not None and time.time() - start_time > timeout:
                        self.new_chunk.emit(f"\n[Timeout] Response took too long, terminating...\n")
                        process.terminate()
                        break

                    # Read in chunks instead of character by character
                    chunk = process.stdout.read(512)  # Read 512 chars at once
                    if chunk:
                        self._emit_filtered(chunk)
                    elif process.poll() is not None:
                        break
                    else:
                        time.sleep(0.01)  # Reduced sleep time

                # Ensure process completes
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    self.new_chunk.emit(f"\n[Error] Process did not terminate cleanly\n")

            # Flush any remaining buffer content
            self._flush_buffer()
            self.finished_signal.emit()

        except Exception as e:
            error_msg = f"[Error] {str(e)}\n"
            self.new_chunk.emit(error_msg)
            self.error_signal.emit(str(e))
            self.finished_signal.emit()

# Keep the old class for backward compatibility
class OllamaTypingWorker(EnhancedOllamaWorker):
    """Legacy class for backward compatibility - now uses enhanced implementation"""
    pass

class TextChangeMonitor:
    """Monitors text input changes and triggers completion requests."""

    def __init__(self, completion_engine):
        self.completion_engine = completion_engine
        self.last_text = ""
        self.last_cursor_pos = 0

    def on_text_changed(self, new_text: str, cursor_position: int):
        """Called when text changes in the input field."""
        # Only trigger completion if text actually changed and cursor moved
        if new_text == self.last_text and cursor_position == self.last_cursor_pos:
            return

        self.last_text = new_text
        self.last_cursor_pos = cursor_position

        # Create completion context
        context = self._create_completion_context(new_text, cursor_position)

        # Update completion engine
        self.completion_engine.set_context(context)

    def _create_completion_context(self, text: str, cursor_pos: int):
        """Create a completion context from current text and cursor position."""
        from completion import CompletionContext

        context = CompletionContext()

        # Split text into lines
        lines = text.split('\n')

        # Find current line
        current_line_idx = 0
        char_count = 0
        for i, line in enumerate(lines):
            if char_count + len(line) >= cursor_pos:
                current_line_idx = i
                break
            char_count += len(line) + 1  # +1 for newline

        # Set current line and cursor position within line
        if current_line_idx < len(lines):
            context.current_line = lines[current_line_idx]
            context.cursor_position = cursor_pos - char_count

        # Set lines before and after
        context.lines_before = lines[:current_line_idx]
        context.lines_after = lines[current_line_idx + 1:]

        # Set language (basic detection)
        context.language = self._detect_language(text)

        return context

    def _detect_language(self, text: str) -> str:
        """Basic language detection based on file extensions or content."""
        # For now, default to python
        # Could be enhanced to detect based on syntax patterns
        return "python"
