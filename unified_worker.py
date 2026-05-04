"""
Unified Worker for ChugaGPT
Handles both offline (Ollama) and cloud models (OpenAI, Anthropic, Google)
"""

import threading
from typing import Generator, Optional, Dict, Any
from PySide6.QtCore import QThread, Signal

# Import cloud model support
try:
    from cloud_models import (
        CloudModelWorker, get_model_provider, create_cloud_worker,
        ModelProvider, CLOUD_MODELS
    )
    CLOUD_AVAILABLE = True
except ImportError:
    CLOUD_AVAILABLE = False
    CLOUD_MODELS = {}


class UnifiedWorker(QThread):
    """Unified worker that handles both Ollama and cloud models"""
    
    # Signals
    stop_requested = Signal()
    new_chunk = Signal(str)
    finished_signal = Signal()
    progress_update = Signal(str)
    error_signal = Signal(str)
    
    def __init__(self, model: str, prompt: str, provider: str = "ollama", 
                 ollama_path: str = "ollama", api_key: str = "", 
                 allow_long: bool = False):
        super().__init__()
        self.model = model
        self.prompt = prompt
        self.provider = provider
        self.ollama_path = ollama_path
        self.api_key = api_key
        self.allow_long = allow_long
        self.stop_flag = False
        
        # Workers
        self._ollama_worker = None
        self._cloud_worker = None
        self._generator = None
        self._generator_thread = None
    
    def stop_generation(self):
        """Stop the ongoing generation"""
        self.stop_flag = True
        
        if self._ollama_worker:
            try:
                self._ollama_worker.stop_generation()
            except Exception:
                pass
        
        if self._cloud_worker:
            try:
                self._cloud_worker.stop()
            except Exception:
                pass
    
    def run(self):
        """Main execution method"""
        try:
            if self.provider == "ollama":
                self._run_ollama()
            elif CLOUD_AVAILABLE:
                self._run_cloud()
            else:
                self.error_signal.emit("Cloud models not available. Install required packages.")
                self.new_chunk.emit("\n[Error: Cloud model support not installed]")
                self.finished_signal.emit()
        except Exception as e:
            self.error_signal.emit(str(e))
            self.new_chunk.emit(f"\n[Error: {str(e)}]")
            self.finished_signal.emit()
    
    def _run_ollama(self):
        """Run Ollama model (local or cloud)"""
        try:
            from logic import EnhancedOllamaWorker
            
            # Check if this is a cloud model
            if self.provider == "ollama_cloud":
                # Use Ollama cloud via --remote flag
                self._ollama_worker = OllamaCloudWorker(self.model, self.prompt)
                result = self._ollama_worker.run()
                if result:
                    self.new_chunk.emit(result)
                if not self.stop_flag:
                    self.finished_signal.emit()
                return
            
            self._ollama_worker = EnhancedOllamaWorker(
                self.model, self.prompt, self.ollama_path, self.allow_long
            )
            
            # Connect signals
            self._ollama_worker.new_chunk.connect(self.new_chunk.emit)
            self._ollama_worker.progress_update.connect(self.progress_update.emit)
            self._ollama_worker.error_signal.connect(self.error_signal.emit)
            
            # Override stop
            def _check_stop():
                return self.stop_flag
            self._ollama_worker.stop_flag = self.stop_flag
            
            # Run
            self._ollama_worker.run()
            
            if not self.stop_flag:
                self.finished_signal.emit()
                
        except Exception as e:
            self.error_signal.emit(str(e))
            self.new_chunk.emit(f"\n[Ollama Error: {str(e)}]")
            self.finished_signal.emit()

    def _run_cloud(self):
        """Run cloud model"""
        try:
            # Check for Ollama cloud
            if self.provider == "ollama_cloud":
                worker = OllamaCloudWorker(self.model, self.prompt)
                result = worker.run()
                if result:
                    self.new_chunk.emit(result)
                if not self.stop_flag:
                    self.finished_signal.emit()
                return
            
            # Regular cloud providers
            worker = create_cloud_worker(
                self.provider, self.model, self.prompt, self.api_key
            )
            
            # Stream response
            for chunk in worker.generate():
                if self.stop_flag:
                    break
                if chunk:
                    self.new_chunk.emit(chunk)
            
            if not self.stop_flag:
                self.finished_signal.emit()
                
        except Exception as e:
            self.error_signal.emit(str(e))
            self.new_chunk.emit(f"\n[Cloud Model Error: {str(e)}]")
            self.finished_signal.emit()
                
        except Exception as e:
            self.error_signal.emit(str(e))
            self.new_chunk.emit(f"\n[Ollama Error: {str(e)}]")
            self.finished_signal.emit()
    
    def _run_cloud(self):
        """Run cloud model"""
        try:
            # Create cloud worker
            worker = create_cloud_worker(
                self.provider, self.model, self.prompt, self.api_key
            )
            self._cloud_worker = worker
            
            # Stream response
            for chunk in worker.generate():
                if self.stop_flag:
                    break
                if chunk:
                    self.new_chunk.emit(chunk)
            
            if not self.stop_flag:
                self.finished_signal.emit()
                
        except Exception as e:
            self.error_signal.emit(str(e))
            self.new_chunk.emit(f"\n[Cloud Model Error: {str(e)}]")
            self.finished_signal.emit()
    
    def get_available_providers() -> Dict[str, Any]:
        """Get available model providers"""
        return {
            "ollama": {
                "display_name": "Ollama (Offline)",
                "requires_key": False,
            },
            "openai": {
                "display_name": "OpenAI",
                "requires_key": True,
                "env_key": "OPENAI_API_KEY",
            },
            "anthropic": {
                "display_name": "Anthropic",
                "requires_key": True,
                "env_key": "ANTHROPIC_API_KEY",
            },
            "google": {
                "display_name": "Google Gemini",
                "requires_key": True,
                "env_key": "GOOGLE_API_KEY",
            },
        }
    
    def get_models_for_provider(provider: str) -> list:
        """Get available models for a provider"""
        if provider == "ollama":
            # Dynamically get Ollama models
            try:
                from utils import get_ollama_models
                models = get_ollama_models("ollama")
                return models if models else ["phi3:mini", "llama3:8b"]
            except Exception:
                return ["phi3:mini", "llama3:8b"]
        
        elif CLOUD_AVAILABLE and provider in CLOUD_MODELS:
            return list(CLOUD_MODELS[provider]["models"].keys())
        
        return []
