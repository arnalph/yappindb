"""
Centralized configuration for DBarf RAG Agent.
Handles model selection, auto-download, and HF API configuration.
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Default configuration
DEFAULT_CONFIG = {
    # Model mode: "gguf" or "hf_api"
    "model_mode": "gguf",
    
    # GGUF model configuration
    "gguf": {
        "model_name": "qwen2.5-coder-3b-instruct-q4_k_m.gguf",
        "hf_repo": "Qwen/Qwen2.5-Coder-3B-Instruct-GGUF",
        "n_ctx": 8192,
        "n_threads": 8,
        "n_gpu_layers": 0,
    },
    
    # Hugging Face Inference API configuration
    "hf_api": {
        "model_id": "Qwen/Qwen2.5-Coder-32B-Instruct",
        "api_key": "",
        "max_new_tokens": 1024,
        "temperature": 0.1,
        "top_p": 0.9,
    },
    
    # Generation parameters (shared)
    "generation": {
        "max_tokens": 512,
        "temperature": 0.1,
        "top_p": 0.9,
        "top_k": 40,
    },
    
    # Debug options
    "debug": {
        "print_schema": True,
        "log_queries": True,
    },
}

# Known GGUF models with their HuggingFace repos
KNOWN_GGUF_MODELS = {
    "qwen2.5-coder-3b-instruct-q4_k_m.gguf": {
        "repo": "Qwen/Qwen2.5-Coder-3B-Instruct-GGUF",
        "size_gb": 2.1,
    },
    "qwen2.5-coder-3b-instruct-q5_k_m.gguf": {
        "repo": "Qwen/Qwen2.5-Coder-3B-Instruct-GGUF",
        "size_gb": 2.5,
    },
    "phi-3-mini-4k-instruct-q4.gguf": {
        "repo": "microsoft/Phi-3-mini-4k-instruct-gguf",
        "size_gb": 2.4,
    },
    "deepseek-coder-1.3b-instruct.q4_k_m.gguf": {
        "repo": "TheBloke/deepseek-coder-1.3b-instruct-GGUF",
        "size_gb": 0.8,
    },
    "sqlcoder-7b-2-q4_k_m.gguf": {
        "repo": "TheBloke/SQLCoder-7B-2-GGUF",
        "size_gb": 4.4,
    },
}


class Config:
    """
    Configuration manager for DBarf.
    
    Loads configuration from:
    1. config.json file (if exists)
    2. Environment variables (override config.json)
    3. Default values
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration.
        
        Args:
            config_path: Path to config.json file (default: ./config.json)
        """
        self.config_path = Path(config_path) if config_path else Path(__file__).parent.parent / "config.json"
        self.config = DEFAULT_CONFIG.copy()
        
        # Load from config.json if exists
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                file_config = json.load(f)
                self._merge_config(file_config)
        
        # Override with environment variables
        self._load_env_vars()
        
        # Create models directory
        self.models_dir = Path(__file__).parent.parent / "models"
        self.models_dir.mkdir(parents=True, exist_ok=True)
    
    def _merge_config(self, file_config: Dict[str, Any]):
        """Merge file config with defaults."""
        for key, value in file_config.items():
            if key in self.config and isinstance(value, dict):
                self.config[key].update(value)
            else:
                self.config[key] = value
    
    def _load_env_vars(self):
        """Load configuration from environment variables."""
        # Model mode
        if os.getenv("DBARF_MODEL_MODE"):
            self.config["model_mode"] = os.getenv("DBARF_MODEL_MODE").lower()

        # GGUF settings
        if os.getenv("GGUF_MODEL_NAME"):
            self.config["gguf"]["model_name"] = os.getenv("GGUF_MODEL_NAME")
        if os.getenv("GGUF_N_CTX"):
            self.config["gguf"]["n_ctx"] = int(os.getenv("GGUF_N_CTX"))
        if os.getenv("GGUF_N_THREADS"):
            self.config["gguf"]["n_threads"] = int(os.getenv("GGUF_N_THREADS"))

        # HF API settings
        if os.getenv("HF_MODEL_ID"):
            self.config["hf_api"]["model_id"] = os.getenv("HF_MODEL_ID")
        if os.getenv("HF_API_KEY"):
            self.config["hf_api"]["api_key"] = os.getenv("HF_API_KEY")
        if os.getenv("HF_MAX_NEW_TOKENS"):
            self.config["hf_api"]["max_new_tokens"] = int(os.getenv("HF_MAX_NEW_TOKENS"))

        # Debug settings
        if os.getenv("DEBUG_PRINT_SCHEMA"):
            self.config["debug"]["print_schema"] = os.getenv("DEBUG_PRINT_SCHEMA").lower() == "true"
    
    @property
    def model_mode(self) -> str:
        """Get current model mode ('gguf' or 'hf_api')."""
        return self.config["model_mode"]
    
    @property
    def use_hf_api(self) -> bool:
        """Check if HF API mode is enabled."""
        return self.model_mode == "hf_api"
    
    @property
    def hf_api_token(self) -> Optional[str]:
        """Get HF API token from environment or config."""
        # First check environment variable
        env_token = os.getenv("HF_API_TOKEN")
        if env_token:
            return env_token
        # Then check config file
        return self.config["hf_api"].get("api_key", "")
    
    @property
    def hf_model_id(self) -> str:
        """Get HF model ID."""
        return self.config["hf_api"]["model_id"]
    
    @property
    def gguf_model_path(self) -> Path:
        """Get path to GGUF model file."""
        model_name = self.config["gguf"]["model_name"]
        return self.models_dir / model_name
    
    @property
    def gguf_model_exists(self) -> bool:
        """Check if GGUF model file exists."""
        return self.gguf_model_path.exists()
    
    @property
    def gguf_config(self) -> Dict[str, Any]:
        """Get GGUF configuration."""
        return self.config["gguf"]
    
    @property
    def hf_config(self) -> Dict[str, Any]:
        """Get HF API configuration."""
        return self.config["hf_api"]
    
    @property
    def generation_config(self) -> Dict[str, Any]:
        """Get generation configuration."""
        return self.config["generation"]
    
    @property
    def debug_config(self) -> Dict[str, Any]:
        """Get debug configuration."""
        return self.config["debug"]
    
    def get_gguf_model_info(self, model_name: str = None) -> Optional[Dict[str, Any]]:
        """
        Get information about a GGUF model.
        
        Args:
            model_name: Model filename (default: current configured model)
            
        Returns:
            Model info dict with repo, size_gb, or None if unknown.
        """
        name = model_name or self.config["gguf"]["model_name"]
        return KNOWN_GGUF_MODELS.get(name)
    
    def download_gguf_model(self, force: bool = False) -> Path:
        """
        Download GGUF model from HuggingFace.
        
        Args:
            force: Force re-download even if file exists.
            
        Returns:
            Path to downloaded model file.
            
        Raises:
            ValueError: If model is not in known models list.
            RuntimeError: If download fails.
        """
        model_name = self.config["gguf"]["model_name"]
        model_path = self.gguf_model_path
        
        # Check if already downloaded
        if model_path.exists() and not force:
            print(f"Model already exists: {model_path}")
            return model_path
        
        # Get model info
        model_info = self.get_gguf_model_info(model_name)
        if not model_info:
            raise ValueError(
                f"Unknown model: {model_name}\n"
                f"Known models: {', '.join(KNOWN_GGUF_MODELS.keys())}\n"
                f"Add your model to KNOWN_GGUF_MODELS in config.py or set custom repo in config.json"
            )
        
        # Download using huggingface_hub
        try:
            from huggingface_hub import hf_hub_download
            
            print(f"Downloading {model_name} from {model_info['repo']}...")
            print(f"Size: ~{model_info['size_gb']}GB")
            
            model_path = hf_hub_download(
                repo_id=model_info["repo"],
                filename=model_name,
                local_dir=self.models_dir,
                local_dir_use_symlinks=False,
            )
            
            print(f"Model downloaded to: {model_path}")
            return Path(model_path)
            
        except ImportError:
            raise RuntimeError(
                "huggingface_hub not installed. Install with: pip install huggingface_hub"
            )
        except Exception as e:
            raise RuntimeError(f"Download failed: {str(e)}")
    
    def create_sample_config(self, output_path: str = None):
        """
        Create a sample config.json file.
        
        Args:
            output_path: Path to write config file (default: ./config.json)
        """
        output_path = Path(output_path) if output_path else self.config_path
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        print(f"Sample config created: {output_path}")
    
    def create_sample_env(self, output_path: str = None):
        """
        Create a sample .env file.
        
        Args:
            output_path: Path to write .env file (default: ./.env)
        """
        output_path = Path(output_path) if output_path else Path(__file__).parent.parent / ".env"
        
        env_content = """# DBarf Configuration

# Model mode: 'gguf' (local) or 'hf_api' (Hugging Face Inference API)
DBARF_MODEL_MODE=gguf

# GGUF Model Settings (only used if DBARF_MODEL_MODE=gguf)
GGUF_MODEL_NAME=qwen2.5-coder-3b-instruct-q4_k_m.gguf
GGUF_N_CTX=8192
GGUF_N_THREADS=8

# Hugging Face API Settings (only used if DBARF_MODEL_MODE=hf_api)
HF_API_TOKEN=your_huggingface_token_here
HF_MODEL_ID=defog/sqlcoder-7b-2
HF_MAX_NEW_TOKENS=512

# Debug Settings
DEBUG_PRINT_SCHEMA=true
DEBUG_LOG_QUERIES=true
"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(env_content)
        print(f"Sample .env created: {output_path}")
    
    def __repr__(self) -> str:
        """Return configuration summary."""
        mode = self.model_mode
        if mode == "gguf":
            model = self.config["gguf"]["model_name"]
            exists = "✓" if self.gguf_model_exists else "✗"
            return f"Config(mode=gguf, model={model}, exists={exists})"
        else:
            model = self.hf_model_id
            has_token = "✓" if self.hf_api_token else "✗"
            return f"Config(mode=hf_api, model={model}, token={has_token})"


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get or create global config instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def use_hf_api() -> bool:
    """Check if HF API mode is enabled."""
    return get_config().use_hf_api


def get_gguf_model_path() -> Path:
    """Get path to GGUF model file."""
    return get_config().gguf_model_path


def ensure_gguf_model() -> Path:
    """Ensure GGUF model is downloaded."""
    config = get_config()
    if not config.gguf_model_exists:
        print(f"Model not found. Downloading...")
        return config.download_gguf_model()
    return config.gguf_model_path
