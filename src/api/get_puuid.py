"""
PUUID resolution and user cache management.

Usage:
    from get_puuid import get_puuid
    puuid = get_puuid("Username", "Tag", riot_client)
"""

import json
from config import USERS_FILE


def get_puuid(username: str, tag: str, client) -> str:
    """Resolve and cache PUUID for username#tag via Riot API."""
    if not username or not tag:
        raise ValueError("Username and tag must be provided.")

    try:
        with open(USERS_FILE, "r") as file:
            users = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        users = {}

    key = f"{username}#{tag}"
    if key in users:
        print(f"Found cached PUUID for {key}.")
        return users[key]["puuid"]

    print(f"Fetching PUUID for {key} from Riot API...")
    puuid = client.get_puuid(username, tag)

    users[key] = {"puuid": puuid}
    with open(USERS_FILE, "w") as file_write:
        json.dump(users, file_write, indent=4)

    return puuid
