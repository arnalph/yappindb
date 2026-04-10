#!/usr/bin/env python3
"""
Convert BIRD-SQL database CSV files to populated SQLite databases.
The minidev dataset ships CSV files in database_description/ folders.
This script creates proper SQLite databases with data.
"""

import os
import csv
import sqlite3
from pathlib import Path

BASE_DIR = Path("data/minidev_databases")


def csv_to_sqlite(db_folder: Path):
    """Convert all CSV files in database_description/ to SQLite tables."""
    csv_dir = db_folder / "database_description"
    db_file = db_folder / f"{db_folder.name}.sqlite"

    if not csv_dir.exists():
        print(f"  Skipping {db_folder.name}: no database_description folder")
        return

    # Remove existing empty database
    if db_file.exists() and db_file.stat().st_size == 0:
        db_file.unlink()

    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()

    csv_files = list(csv_dir.glob("*.csv"))
    print(f"  Converting {len(csv_files)} CSV files → {db_file.name}")

    for csv_file in csv_files:
        table_name = csv_file.stem.lower()
        print(f"    {table_name}...")

        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            headers = next(reader, None)

            if not headers:
                continue

            # Create table
            columns = ", ".join([f'"{h}" TEXT' for h in headers])
            cursor.execute(f"DROP TABLE IF EXISTS \"{table_name}\"")
            cursor.execute(f"CREATE TABLE \"{table_name}\" ({columns})")

            # Insert data
            placeholders = ", ".join(["?" for _ in headers])
            rows = list(reader)
            if rows:
                cursor.executemany(
                    f"INSERT INTO \"{table_name}\" VALUES ({placeholders})",
                    rows
                )
            print(f"      {len(rows)} rows inserted")

    conn.commit()
    conn.close()
    print(f"  ✓ {db_file.name} created")


def main():
    if not BASE_DIR.exists():
        print(f"Error: {BASE_DIR} not found")
        return

    db_folders = [d for d in BASE_DIR.iterdir() if d.is_dir()]
    print(f"Converting {len(db_folders)} databases...\n")

    for db_folder in sorted(db_folders):
        csv_to_sqlite(db_folder)
        print()

    print("Done! All databases converted.")


if __name__ == "__main__":
    main()
