"""
Enhanced Response Handler for chugaGPT
Provides chunk-based streaming, advanced formatting, and better user experience
"""

import re
import time
import threading
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import QTextEdit
from PySide6.QtGui import QTextCursor

class ResponseBuffer:
    """Buffer system for smoother response display"""
    
    def __init__(self, chunk_size=100, flush_interval=0.05):
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

class ResponseFormatter:
    """Advanced response formatting with markdown support"""
    
    def __init__(self):
        self.code_block_pattern = re.compile(r'```(\w+)?\s*\n(.*?)```', re.DOTALL)
        self.inline_code_pattern = re.compile(r'`([^`]+)`')
        self.bold_pattern = re.compile(r'\*\*(.*?)\*\*')
        self.italic_pattern = re.compile(r'\*(.*?)\*')
        self.list_pattern = re.compile(r'^(\d+\.|\*|\-)\s+', re.MULTILINE)
    
    def format_response(self, text):
        """Format response text with enhanced styling"""
        formatted = text
        
        # Handle code blocks
        formatted = self._format_code_blocks(formatted)
        
        # Handle inline code
        formatted = self._format_inline_code(formatted)
        
        # Handle bold text
        formatted = self._format_bold_text(formatted)
        
        # Handle italic text
        formatted = self._format_italic_text(formatted)
        
        # Handle lists
        formatted = self._format_lists(formatted)
        
        return formatted
    
    def _format_code_blocks(self, text):
        """Format code blocks with syntax highlighting and interactive features"""
        def replace_code_block(match):
            language = match.group(1) or 'text'
            code = match.group(2)
            
            # Language-specific styling
            lang_styles = {
                'python': '#ff6600',
                'javascript': '#f7df1e',
                'html': '#e34c26',
                'css': '#1572b6',
                'json': '#292929',
                'bash': '#4eaa25',
                'sql': '#336791',
                'default': '#00ff99'
            }
            
            lang_color = lang_styles.get(language.lower(), lang_styles['default'])
            
            return f'''
            <div style="background: linear-gradient(135deg, #0f141a 0%, #1a1f2e 100%);
                        border: 1px solid #2a3140;
                        border-radius: 8px;
                        margin: 16px 0;
                        overflow: hidden;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.4);">
                <div style="background: linear-gradient(90deg, #2a3140 0%, #1f2630 100%);
                            padding: 12px 16px;
                            display: flex;
                            justify-content: space-between;
                            align-items: center;
                            border-bottom: 1px solid #2a3140;">
                    <div style="display: flex; align-items: center;">
                        <span style="font-size: 14px; margin-right: 8px;">💻</span>
                        <span style="color: {lang_color}; font-weight: bold; font-size: 13px;">{language.upper()}</span>
                    </div>
                    <button onclick="copyToClipboard(this)" 
                            style="background: #00ffa3; 
                                   color: #0f141a; 
                                   border: none; 
                                   border-radius: 4px; 
                                   padding: 4px 8px; 
                                   font-size: 11px; 
                                   cursor: pointer;
                                   font-weight: bold;">📋 Copy</button>
                </div>
                <pre style="background-color: #0f141a; 
                           color: #c0caf5; 
                           padding: 16px; 
                           margin: 0; 
                           overflow-x: auto; 
                           font-family: 'Fira Code', 'Consolas', monospace;
                           font-size: 13px;
                           line-height: 1.4;"><code>{code}</code></pre>
            </div>
            <script>
            function copyToClipboard(button) {{
                const codeBlock = button.parentElement.parentElement.querySelector('code');
                const textArea = document.createElement('textarea');
                textArea.value = codeBlock.textContent;
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);
                
                // Visual feedback
                const originalText = button.textContent;
                button.textContent = '✅ Copied!';
                button.style.background = '#00ff99';
                setTimeout(() => {{
                    button.textContent = originalText;
                    button.style.background = '#00ffa3';
                }}, 1500);
            }}
            </script>'''
        
        return self.code_block_pattern.sub(replace_code_block, text)
    
    def _format_inline_code(self, text):
        """Format inline code with improved styling"""
        def replace_inline_code(match):
            code = match.group(1)
            return f'<code style="background: linear-gradient(135deg, #2a3140 0%, #1f2630 100%); color: #ff6600; padding: 3px 6px; border-radius: 4px; font-family: monospace; font-weight: bold; border: 1px solid #3a4150;">{code}</code>'
        
        return self.inline_code_pattern.sub(replace_inline_code, text)
    
    def _format_bold_text(self, text):
        """Format bold text with enhanced styling"""
        def replace_bold(match):
            content = match.group(1)
            return f'<b style="color: #ffffff; font-weight: bold; text-shadow: 0 1px 2px rgba(0,0,0,0.5);">{content}</b>'
        
        return self.bold_pattern.sub(replace_bold, text)
    
    def _format_italic_text(self, text):
        """Format italic text with enhanced styling"""
        def replace_italic(match):
            content = match.group(1)
            return f'<i style="color: #7aa2f7; font-style: italic;">{content}</i>'
        
        return self.italic_pattern.sub(replace_italic, text)
    
    def _format_lists(self, text):
        """Format lists with enhanced styling"""
        lines = text.split('\n')
        formatted_lines = []
        
        for line in lines:
            if self.list_pattern.match(line):
                # This is a list item with enhanced styling
                formatted_lines.append(f'<div style="margin-left: 20px; color: #c0caf5; display: flex; align-items: flex-start; margin-bottom: 4px;"><span style="color: #00ffa3; margin-right: 8px; font-weight: bold;">▶</span> {line}</div>')
            else:
                formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)

class SimpleResponseHandler(QObject):
    """Simple response handler that displays text immediately"""

    # Signals for UI updates
    new_content = Signal(str)  # Emitted when new content is ready to display
    progress_update = Signal(str)  # Progress updates
    error_signal = Signal(str)  # Error notifications
    finished_signal = Signal()  # Response complete

    def __init__(self, chat_area):
        super().__init__()
        self.chat_area = chat_area
        self.response_buffer = ResponseBuffer()
        self.formatter = ResponseFormatter()
        self.is_thinking = False
        self.is_answer = False
        self.pending_text = ""
        self.full_response = ""
        
        # Timer for periodic UI updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._flush_buffer)
        self.update_timer.start(50)  # Update every 50ms
    
    def handle_chunk(self, chunk: str):
        """Handle incoming response chunk with enhanced animations"""
        if not chunk:
            return
        
        self.full_response += chunk
        
        # Add to buffer for processing
        buffered_content = self.response_buffer.append(chunk)
        if buffered_content:
            self._process_buffered_content(buffered_content)
    
    def _process_buffered_content(self, content: str):
        """Process buffered content for formatting and display with animations"""
        self.pending_text += content
        
        # Check for complete sections
        if "<ThoughtProcess>" in self.pending_text and "</ThoughtProcess>" in self.pending_text:
            self._handle_thinking_section()
        elif "<Response>" in self.pending_text and "</Response>" in self.pending_text:
            self._handle_response_section()
        elif self.is_answer:
            # Format and display normal text with fade-in animation
            formatted = self.formatter.format_response(content)
            animated_html = f'''
            <div class="fade-in" style="animation: fadeIn 0.5s ease-in-out;">{formatted}</div>
            <style>
            @keyframes fadeIn {{
                from {{ opacity: 0; transform: translateY(10px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}
            .fade-in {{
                opacity: 0;
                animation-fill-mode: forwards;
            }}
            </style>'''
            self.new_content.emit(animated_html)
    
    def _handle_thinking_section(self):
        """Handle complete thinking sections"""
        parts = self.pending_text.split("</ThoughtProcess>", 1)
        thinking_content = parts[0].replace("<ThoughtProcess>", "")
        
        # Format thinking content with enhanced styling
        formatted = self.formatter.format_response(thinking_content)
        thinking_html = f'''
        <div style="background: linear-gradient(135deg, #2a3140 0%, #1f2630 100%);
                    border-left: 5px solid #7aa2f7;
                    border-radius: 0 12px 12px 0;
                    margin: 12px 0;
                    padding: 16px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
            <div style="display: flex; align-items: center; margin-bottom: 12px;">
                <span style="font-size: 16px; margin-right: 8px;">🤔</span>
                <span style="color: #7aa2f7; font-weight: bold; font-size: 14px;">THINKING PROCESS</span>
            </div>
            <div style="color: #9aa5ce; font-style: italic; line-height: 1.5;">{formatted}</div>
        </div>'''
        
        self.new_content.emit(thinking_html)
        
        # Process remaining text
        self.pending_text = parts[1] if len(parts) > 1 else ""
        if self.pending_text:
            self._process_buffered_content("")
    
    def _handle_response_section(self):
        """Handle complete response sections with collapsible functionality"""
        parts = self.pending_text.split("</Response>", 1)
        response_content = parts[0].replace("<Response>", "")
        
        # Format response content
        formatted = self.formatter.format_response(response_content)
        
        # Check if response is long (more than 1000 characters)
        is_long_response = len(response_content.strip()) > 1000
        
        if is_long_response:
            response_html = f'''
            <div class="response-section" style="background: linear-gradient(135deg, #1a2130 0%, #0f1a25 100%);
                                                border: 2px solid #00ffa3;
                                                border-radius: 12px;
                                                margin: 12px 0;
                                                overflow: hidden;
                                                box-shadow: 0 6px 20px rgba(0,255,163,0.1);">
                <div style="background: linear-gradient(90deg, #00ffa3 0%, #00cc7a 100%);
                           padding: 16px 20px;
                           display: flex;
                           justify-content: space-between;
                           align-items: center;
                           cursor: pointer;
                           user-select: none;">
                    <div style="display: flex; align-items: center;">
                        <span style="font-size: 18px; margin-right: 10px;">✨</span>
                        <span style="color: #0f141a; font-weight: bold; font-size: 16px;">RESPONSE</span>
                        <span style="color: #0f141a; font-size: 12px; margin-left: 12px; opacity: 0.8;">
                            ({len(response_content)} chars)
                        </span>
                    </div>
                    <span class="toggle-icon" style="color: #0f141a; font-size: 14px; transition: transform 0.3s ease;">▼</span>
                </div>
                <div class="response-content" style="padding: 20px; color: #c0caf5; line-height: 1.6; display: block;">
                    {formatted}
                </div>
            </div>
            <script>
            document.addEventListener('DOMContentLoaded', function() {{
                const sections = document.querySelectorAll('.response-section');
                sections.forEach(section => {{
                    const header = section.querySelector('.response-section > div');
                    const content = section.querySelector('.response-content');
                    const icon = section.querySelector('.toggle-icon');
                    
                    header.addEventListener('click', function() {{
                        const isCollapsed = content.style.display === 'none';
                        content.style.display = isCollapsed ? 'block' : 'none';
                        icon.style.transform = isCollapsed ? 'rotate(0deg)' : 'rotate(180deg)';
                        icon.textContent = isCollapsed ? '▼' : '▶';
                    }});
                }});
            }});
            </script>'''
        else:
            response_html = f'''
            <div style="background: linear-gradient(135deg, #1a2130 0%, #0f1a25 100%);
                        border: 2px solid #00ffa3;
                        border-radius: 12px;
                        margin: 12px 0;
                        padding: 20px;
                        box-shadow: 0 6px 20px rgba(0,255,163,0.1);">
                <div style="display: flex; align-items: center; margin-bottom: 16px;">
                    <span style="font-size: 18px; margin-right: 10px;">✨</span>
                    <span style="color: #00ffa3; font-weight: bold; font-size: 16px;">RESPONSE</span>
                </div>
                <div style="color: #c0caf5; line-height: 1.6;">{formatted}</div>
            </div>'''
        
        self.new_content.emit(response_html)
        
        # Process remaining text
        self.pending_text = parts[1] if len(parts) > 1 else ""
        if self.pending_text:
            self._process_buffered_content("")
    
    def _flush_buffer(self):
        """Flush any remaining buffered content"""
        remaining = self.response_buffer.flush()
        if remaining:
            self._process_buffered_content(remaining)
    
    def finish_response(self):
        """Called when response is complete"""
        self._flush_buffer()
        self.update_timer.stop()
        self.finished_signal.emit()
    
    def reset_state(self):
        """Reset handler state for new response"""
        self.is_thinking = False
        self.is_answer = False
        self.pending_text = ""
        self.full_response = ""
        self.response_buffer = ResponseBuffer()
    
    def get_response_quality_score(self):
        """Get quality score for the current response"""
        if not self.full_response:
            return 0
        
        score = 100
        
        # Check for incomplete sections
        if "<ThoughtProcess>" in self.full_response and "</ThoughtProcess>" not in self.full_response:
            score -= 30
        if "<Response>" in self.full_response and "</Response>" not in self.full_response:
            score -= 30
        
        # Check for minimum length
        clean_response = re.sub(r'<.*?>', '', self.full_response)
        if len(clean_response.strip()) < 50:
            score -= 20
        
        # Check for code blocks
        code_blocks = self.code_block_pattern.findall(self.full_response)
        if code_blocks:
            score += 10  # Bonus for including code
        
        return max(0, min(100, score))

class ResponseQualityValidator:
    """Validates response quality and provides feedback"""
    
    def __init__(self):
        self.min_response_length = 50
        self.max_response_length = 50000
    
    def validate_response(self, response):
        """Validate response and return issues list"""
        issues = []
        
        # Check length
        if len(response.strip()) < self.min_response_length:
            issues.append("Response appears to be too short")
        elif len(response.strip()) > self.max_response_length:
            issues.append("Response appears to be too long")
        
        # Check for incomplete tags
        if "<ThoughtProcess>" in response and "</ThoughtProcess>" not in response:
            issues.append("Incomplete thinking section detected")
        if "<Response>" in response and "</Response>" not in response:
            issues.append("Incomplete response section detected")
        
        # Check for code blocks
        code_pattern = re.compile(r'```(\w+)?\s*\n(.*?)```', re.DOTALL)
        code_blocks = code_pattern.findall(response)
        for block in code_blocks:
            if block[1].strip() and not block[1].endswith('```'):
                issues.append("Incomplete code block detected")
        
        # Check for repetitive content
        lines = response.split('\n')
        if len(lines) > 10:
            repetitive_lines = 0
            for i in range(1, min(10, len(lines))):
                if lines[i].strip() == lines[0].strip():
                    repetitive_lines += 1
            if repetitive_lines > 3:
                issues.append("Response contains repetitive content")
        
        return issues
    
    def get_quality_score(self, response):
        """Calculate quality score (0-100)"""
        if not response:
            return 0
        
        score = 100
        issues = self.validate_response(response)
        
        # Deduct points for issues
        for issue in issues:
            if "incomplete" in issue.lower():
                score -= 25
            elif "repetitive" in issue.lower():
                score -= 15
            elif "short" in issue.lower():
                score -= 20
            elif "long" in issue.lower():
                score -= 10
        
        # Bonus for structured content
        if "<ThoughtProcess>" in response and "</ThoughtProcess>" in response:
            score += 10
        if "```" in response:
            score += 5
        
        return max(0, min(100, score))

# Keep the old name for backward compatibility
EnhancedResponseHandler = SimpleResponseHandler
