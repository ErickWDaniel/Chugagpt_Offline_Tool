"""
Cloud Model Support for ChugaGPT
Supports OpenAI, Anthropic, and Google Gemini APIs
"""

import os
import json
from typing import Dict, Any, Optional, List
from enum import Enum


class ModelProvider(Enum):
    """Supported cloud model providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    OLLAMA = "ollama"


# Model configurations
CLOUD_MODELS = {
    ModelProvider.OPENAI.value: {
        "display_name": "OpenAI",
        "models": {
            "gpt-4o": "GPT-4o",
            "gpt-4o-mini": "GPT-4o Mini",
            "gpt-4-turbo": "GPT-4 Turbo",
            "gpt-3.5-turbo": "GPT-3.5 Turbo",
        },
        "api_key_env": "OPENAI_API_KEY",
        "api_base": "https://api.openai.com/v1",
    },
    ModelProvider.ANTHROPIC.value: {
        "display_name": "Anthropic",
        "models": {
            "claude-3-5-sonnet-20241022": "Claude 3.5 Sonnet",
            "claude-3-opus-20240229": "Claude 3 Opus",
            "claude-3-haiku-20240307": "Claude 3 Haiku",
        },
        "api_key_env": "ANTHROPIC_API_KEY",
        "api_base": "https://api.anthropic.com",
    },
    ModelProvider.GOOGLE.value: {
        "display_name": "Google",
        "models": {
            "gemini-2.0-flash-exp": "Gemini 2.0 Flash",
            "gemini-1.5-pro": "Gemini 1.5 Pro",
            "gemini-1.5-flash": "Gemini 1.5 Flash",
        },
        "api_key_env": "GOOGLE_API_KEY",
        "api_base": "https://generativelanguage.googleapis.com/v1beta",
    },
    "ollama_cloud": {
        "display_name": "Ollama Cloud (Free)",
        "models": {
            "llama3.2:1b": "Llama 3.2 1B (Cloud)",
            "llama3.2:3b": "Llama 3.2 3B (Cloud)",
            "llama3.2:70b": "Llama 3.2 70B (Cloud)",
            "qwen2.5:0.5b": "Qwen 2.5 0.5B (Cloud)",
            "qwen2.5:1.5b": "Qwen 2.5 1.5B (Cloud)",
            "phi3:mini": "Phi 3 Mini (Cloud)",
        },
        "description": "Free cloud-hosted models via Ollama --remote flag",
    },
}


class CloudModelWorker:
    """Base class for cloud model workers"""
    
    def __init__(self, model: str, prompt: str, api_key: str = ""):
        self.model = model
        self.prompt = prompt
        self.api_key = api_key
        self.stop_flag = False
        
    def stop(self):
        """Stop generation"""
        self.stop_flag = True


class OpenAIWorker(CloudModelWorker):
    """OpenAI API worker"""
    
    def generate(self):
        """Generate response using OpenAI API"""
        try:
            import openai
            
            client = openai.OpenAI(api_key=self.api_key or os.getenv("OPENAI_API_KEY"))
            
            # Convert prompt to messages format
            messages = self._parse_prompt_to_messages(self.prompt)
            
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                temperature=0.7,
            )
            
            for chunk in response:
                if self.stop_flag:
                    break
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except ImportError:
            yield "[Error: openai package not installed. Run: pip install openai]"
        except Exception as e:
            yield f"[OpenAI Error: {str(e)}]"
    
    def _parse_prompt_to_messages(self, prompt: str) -> List[Dict]:
        """Convert prompt to messages format"""
        # Simple conversion - treat entire prompt as user message
        # In production, you'd want to parse <ThoughtProcess> and <Response> tags
        return [{"role": "user", "content": prompt}]


class AnthropicWorker(CloudModelWorker):
    """Anthropic API worker"""
    
    def generate(self):
        """Generate response using Anthropic API"""
        try:
            import anthropic
            
            client = anthropic.Anthropic(api_key=self.api_key or os.getenv("ANTHROPIC_API_KEY"))
            
            response = client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": self.prompt}],
                stream=True,
            )
            
            for chunk in response:
                if self.stop_flag:
                    break
                if chunk.type == "content_block_delta":
                    yield chunk.delta.text
                    
        except ImportError:
            yield "[Error: anthropic package not installed. Run: pip install anthropic]"
        except Exception as e:
            yield f"[Anthropic Error: {str(e)}]"




class GoogleWorker(CloudModelWorker):
    """Google Gemini API worker"""
    
    def generate(self):
        """Generate response using Google API"""
        try:
            import google.generativeai as genai
            
            api_key = self.api_key or os.getenv("GOOGLE_API_KEY")
            genai.configure(api_key=api_key)
            
            model = genai.GenerativeModel(self.model)
            
            response = model.generate_content(self.prompt, stream=True)
            
            for chunk in response:
                if self.stop_flag:
                    break
                if chunk.text:
                    yield chunk.text
                    
        except ImportError:
            yield "[Error: google-generativeai package not installed. Run: pip install google-generativeai]"
        except Exception as e:
            yield f"[Google Error: {str(e)}]"


def get_model_provider(model_name: str) -> str:
    """Detect which provider a model belongs to"""
    model_lower = model_name.lower()
    
    # Check OpenAI models
    if any(m in model_lower for m in ["gpt-", "text-davinci", "text-curie"]):
        return ModelProvider.OPENAI.value
    
    # Check Anthropic models
    if "claude" in model_lower:
        return ModelProvider.ANTHROPIC.value
    
    # Check Google models
    if "gemini" in model_lower:
        return ModelProvider.GOOGLE.value
    
    # Default to Ollama
    return ModelProvider.OLLAMA.value


def create_cloud_worker(provider: str, model: str, prompt: str, api_key: str = "") -> CloudModelWorker:
    """Create appropriate cloud worker based on provider"""
    if provider == ModelProvider.OPENAI.value:
        return OpenAIWorker(model, prompt, api_key)
    elif provider == ModelProvider.ANTHROPIC.value:
        return AnthropicWorker(model, prompt, api_key)
    elif provider == ModelProvider.GOOGLE.value:
        return GoogleWorker(model, prompt, api_key)
    else:
        raise ValueError(f"Unknown provider: {provider}")


def get_all_models() -> Dict[str, List[str]]:
    """Get all available models organized by provider"""
    result = {}
    for provider, config in CLOUD_MODELS.items():
        result[config["display_name"]] = list(config["models"].keys())
    return result


def get_model_display_name(model_name: str) -> str:
    """Get display name for a model"""
    for provider, config in CLOUD_MODELS.items():
        if model_name in config["models"]:
            return config["models"][model_name]
    return model_name
