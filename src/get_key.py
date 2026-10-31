"""
Riot API key loader and updater backed by environment variables and .env.

Usage:
    from get_key import load_saved_key, update_key
    api_key = load_saved_key()
"""

import os
from config import ENV_FILE


def _read_env_key() -> str | None:
    """Read RIOT_API_KEY from environment or .env file."""
    if os.getenv("RIOT_API_KEY"):
        return os.environ["RIOT_API_KEY"].strip()

    if ENV_FILE.exists():
        with open(ENV_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or not line:
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    if key.strip() == "RIOT_API_KEY":
                        val = val.strip().strip("'\"")
                        if val:
                            os.environ["RIOT_API_KEY"] = val
                            return val
    return None


def load_saved_key() -> str:
    """Return active API key or prompt for a new one if missing."""
    key = _read_env_key()
    if key:
        return key
    return update_key()


def update_key() -> str:
    """Prompt for a new API key and persist to .env and environment."""
    new_key = input(
        "Riot API key is missing, invalid, or expired.\n"
        "Enter API key: "
    ).strip()

    lines = []
    found = False
    if ENV_FILE.exists():
        with open(ENV_FILE, "r") as f:
            for line in f:
                if line.strip().startswith("RIOT_API_KEY="):
                    lines.append(f"RIOT_API_KEY={new_key}\n")
                    found = True
                else:
                    lines.append(line)
    if not found:
        lines.append(f"RIOT_API_KEY={new_key}\n")

    with open(ENV_FILE, "w") as f:
        f.writelines(lines)

    os.environ["RIOT_API_KEY"] = new_key
    print(f"API key saved to {ENV_FILE}.")
    return new_key
