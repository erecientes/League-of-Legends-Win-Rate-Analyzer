from pathlib import Path

# LOL_API/src/config.py -> parent is src/, parent.parent is LOL_API/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = PROJECT_ROOT / "data"
DB_DIR = PROJECT_ROOT / "db"

DATA_DIR.mkdir(exist_ok=True)
DB_DIR.mkdir(exist_ok=True)

API_KEY_FILE = DATA_DIR / "api_key.txt"
USERS_FILE = DATA_DIR / "users.txt"