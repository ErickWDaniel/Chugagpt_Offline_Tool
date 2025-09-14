import subprocess
import time
import os
from PySide6.QtCore import QThread, Signal
from utils import clean_output

class OllamaTypingWorker(QThread):
    stop_requested = Signal()
    new_char = Signal(str)
    finished_signal = Signal()

    def __init__(self, model, prompt, ollama_path="ollama"):
        super().__init__()
        self.model = model
        self.prompt = prompt
        self.ollama_path = ollama_path
        self.stop_flag = False
        self.process = None

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
        cleaned = clean_output(text)
        for ch in cleaned:
            self.new_char.emit(ch)

    def run(self):
        try:
            args = [self.ollama_path, "run", self.model, self.prompt]
            # Reduce ANSI noise when possible
            env = os.environ.copy()
            env.setdefault("OLLAMA_NO_COLOR", "1")

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
                        timeout = 300  # 5 minutes timeout
                        while True:
                            # Check for stop request
                            if self.stop_flag:
                                self.new_char.emit("\n[Generation Stopped]\n")
                                process.terminate()
                                break

                            # Check for timeout
                            if time.time() - start_time > timeout:
                                self.new_char.emit(f"\n[Timeout] Response took too long, terminating...\n")
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
                            data = os.read(master_fd, 1024)
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
                # Portable fallback: use PIPE with character-by-character reading to enable real-time streaming
                self.process = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,  # line-buffered
                    env=env,
                )
                process = self.process
                # Read character by character to enable real-time streaming
                start_time = time.time()
                timeout = 300  # 5 minutes timeout
                while True:
                    # Check for stop request
                    if self.stop_flag:
                        self.new_char.emit("\n[Generation Stopped]\n")
                        process.terminate()
                        break

                    # Check for timeout
                    if time.time() - start_time > timeout:
                        self.new_char.emit(f"\n[Timeout] Response took too long, terminating...\n")
                        process.terminate()
                        break

                    char = process.stdout.read(1)
                    if char:
                        self._emit_filtered(char)
                    elif process.poll() is not None:
                        break
                    else:
                        time.sleep(0.01)
                # Ensure process completes
                try:
                    process.wait(timeout=10)  # Wait up to 10 seconds for process to finish
                except subprocess.TimeoutExpired:
                    process.kill()
                    self.new_char.emit(f"\n[Error] Process did not terminate cleanly\n")

            self.finished_signal.emit()
        except Exception as e:
            self.new_char.emit(f"[Error] {str(e)}\n")
            self.finished_signal.emit()
