#!/usr/bin/env python3
"""
Download actual BIRD-SQL MiniDev SQLite databases.
Downloads from the official BIRD benchmark server.
"""

import os
import zipfile
import urllib.request
from pathlib import Path

DATABASES_URL = "https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip"
DOWNLOAD_DIR = Path("data")
ZIP_PATH = DOWNLOAD_DIR / "minidev.zip"
EXTRACT_DIR = DOWNLOAD_DIR / "minidev_databases"


def download_databases():
    """Download and extract the BIRD Mini-Dev databases."""
    if not DOWNLOAD_DIR.exists():
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # Download
    if not ZIP_PATH.exists():
        print(f"Downloading from {DATABASES_URL}...")
        print("This may take a while (~3GB)...")
        urllib.request.urlretrieve(DATABASES_URL, ZIP_PATH)
        print(f"Downloaded: {ZIP_PATH} ({ZIP_PATH.stat().st_size / 1024 / 1024:.0f} MB)")
    else:
        size = ZIP_PATH.stat().st_size / 1024 / 1024
        print(f"Zip file already exists: {ZIP_PATH} ({size:.0f} MB)")

    # Extract
    print(f"Extracting to {EXTRACT_DIR}...")
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        members = zf.namelist()
        print(f"Extracting {len(members)} files...")
        zf.extractall(EXTRACT_DIR)

    print(f"\nDone! Databases extracted to: {EXTRACT_DIR}")

    # List extracted databases
    print("\nExtracted databases:")
    for db_folder in sorted(EXTRACT_DIR.iterdir()):
        if db_folder.is_dir():
            sqlite_files = list(db_folder.glob("*.sqlite"))
            if sqlite_files:
                size = sqlite_files[0].stat().st_size
                print(f"  {db_folder.name}: {size/1024/1024:.1f} MB")


if __name__ == "__main__":
    download_databases()
