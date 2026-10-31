"""
Configuration constants and storage paths.

Usage:
    from config import DATA_DIR, DB_DIR, ENV_FILE, USERS_FILE
"""

from pathlib import Path
import sys

# Persistent storage directory (supports frozen standalone executables)
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent.parent

PROJECT_ROOT = APP_DIR

ENV_FILE = APP_DIR / ".env"
DATA_DIR = APP_DIR / "data"
DB_DIR = APP_DIR / "db"

DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_DIR.mkdir(parents=True, exist_ok=True)

USERS_FILE = DATA_DIR / "users.txt"
