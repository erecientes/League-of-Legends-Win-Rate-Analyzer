"""
Riot API key loader and updater backed by environment variables and .env.

Usage:
    from api.get_key import load_saved_key, update_key
    api_key = load_saved_key()
"""

import os
import sys
from config import ENV_FILE


def _read_env_key() -> str | None:
    """Read RIOT_API_KEY from .env file first, then system environment."""
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

    if os.getenv("RIOT_API_KEY"):
        return os.environ["RIOT_API_KEY"].strip()

    return None


def load_saved_key() -> str:
    """Return active API key or prompt for a new one if missing."""
    key = _read_env_key()
    if key:
        return key
    return update_key()


def update_key() -> str:
    """Prompt for a new API key via GUI dialog or terminal, then persist to .env."""
    new_key = None

    # Check if running without a console (e.g. PyInstaller --noconsole)
    if sys.stdin is None or not hasattr(sys.stdin, "isatty") or not sys.stdin.isatty():
        try:
            import customtkinter as ctk
            dialog = ctk.CTkInputDialog(
                text="Your Riot API key is missing or expired.\nEnter API key:",
                title="Riot API Key Required"
            )
            val = dialog.get_input()
            if val:
                new_key = val.strip()
        except Exception:
            pass

    if not new_key:
        try:
            new_key = input(
                "Riot API key is missing, invalid, or expired.\nEnter API key: "
            ).strip()
        except (RuntimeError, EOFError):
            new_key = ""

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
