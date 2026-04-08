#!/usr/bin/env python3
"""
Download Bird-SQL dataset from Hugging Face.

This script downloads the JSON test cases from the Bird-SQL dataset.
Note: The actual SQLite databases must be downloaded separately from
https://bird-bench.github.io/ and placed in the databases_dir.

Usage:
    python scripts/download_bird.py                    # Download dev set
    python scripts/download_bird.py --subset train     # Download train set
    python scripts/download_bird.py --output my_data   # Custom output dir
"""

import argparse
import sys
from pathlib import Path


def download_bird(output_dir: Path = Path("data"), subset: str = "dev"):
    """Download Bird-SQL dataset from Hugging Face.
    
    Args:
        output_dir: Directory to save the dataset
        subset: Dataset subset to download (dev, train, test)
    """
    try:
        from datasets import load_dataset
    except ImportError:
        print("Error: 'datasets' package not installed.")
        print("Install with: pip install datasets")
        sys.exit(1)
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    dataset_name = "birdsql/bird-critic-1.0-sqlite"
    
    print(f"Downloading {dataset_name} (subset: {subset})...")
    
    try:
        dataset = load_dataset(dataset_name, split=subset, trust_remote_code=True)
    except Exception as e:
        print(f"Error downloading dataset: {e}")
        print("\nPossible solutions:")
        print("1. Check your internet connection")
        print("2. Verify Hugging Face token: huggingface-cli login")
        print("3. Check dataset name is correct")
        sys.exit(1)
    
    # Save to JSON
    json_path = output_dir / f"bird_{subset}.json"
    dataset.to_json(str(json_path))
    
    print(f"\nDownloaded {len(dataset)} test cases")
    print(f"Saved to: {json_path}")
    print(f"\nNext steps:")
    print(f"1. Download SQLite databases from https://bird-bench.github.io/")
    print(f"2. Place databases in: data/bird_databases/")
    print(f"3. Structure: data/bird_databases/{{db_id}}/{{db_id}}.sqlite")
    print(f"4. Update config.json 'databases_dir' if needed")
    print(f"5. Run benchmark: python -m rag_agent.benchmark")


def main():
    parser = argparse.ArgumentParser(description="Download Bird-SQL dataset")
    parser.add_argument(
        "--output", 
        default="data", 
        help="Output directory (default: data)"
    )
    parser.add_argument(
        "--subset", 
        default="dev", 
        choices=["dev", "train", "test"],
        help="Dataset subset to download"
    )
    args = parser.parse_args()
    
    download_bird(Path(args.output), args.subset)


if __name__ == "__main__":
    main()
