#!/usr/bin/env python3
"""
Download the phi-3.5-mini-instruct GGUF model.
This script uses the huggingface_hub library to download a quantized version.
"""

import os
from pathlib import Path
from huggingface_hub import hf_hub_download


def download_model():
    """Download the Phi-3.5-mini-instruct GGUF model."""
    model_dir = Path(__file__).parent.parent / "models"
    model_dir.mkdir(exist_ok=True)

    # Use a known GGUF file from Hugging Face
    # We'll use a Q4_K_M version for good balance of size and quality
    repo_id = "Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF"
    filename = "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"

    print(f"Downloading {filename} from {repo_id}...")
    model_path = hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        local_dir=model_dir,
        local_dir_use_symlinks=False,
    )
    print(f"Model downloaded to: {model_path}")


if __name__ == "__main__":
    download_model()
