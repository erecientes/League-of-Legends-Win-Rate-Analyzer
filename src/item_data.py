"""
Data Dragon item metadata loader and item category classifier.

Usage:
    from item_data import load_item_data, classify_item, get_item_name, get_item_icon_path, patch_from_game_version
    item_data = load_item_data("14.14.1")
    category = classify_item(3078, item_data)
    name = get_item_name(3078, item_data)
    icon_path = get_item_icon_path(3078, "14.14.1")
"""

import json
import requests
from pathlib import Path
from config import DATA_DIR

CATEGORY_LEGENDARY = "legendary"
CATEGORY_BOOTS = "boots"


def patch_from_game_version(game_version: str) -> str:
    """Format gameVersion (e.g. '14.14.567.1234') into Data Dragon patch format ('14.14.1')."""
    major, minor, *_ = game_version.split(".")
    return f"{major}.{minor}.1"


def load_item_data(patch: str) -> dict:
    """Fetch and disk-cache Data Dragon item metadata for a specific patch."""
    cache_path = DATA_DIR / f"item_data_{patch}.json"
    if cache_path.exists():
        with open(cache_path) as file:
            return json.load(file)

    url = f"https://ddragon.leagueoflegends.com/cdn/{patch}/data/en_US/item.json"
    response = requests.get(url)
    response.raise_for_status()
    item_data = response.json()["data"]

    with open(cache_path, "w") as file:
        json.dump(item_data, file)

    return item_data


def classify_item(item_id: int, item_data: dict) -> str | None:
    """Classify completed items (boots or legendaries); returns None for components/consumables."""
    info = item_data.get(str(item_id))
    if info is None:
        return None

    tags = set(info.get("tags", []))
    if "Boots" in tags:
        return CATEGORY_BOOTS

    if "into" in info:
        return None
    if not info.get("from"):
        return None
    if tags & {"Consumable", "Trinket"}:
        return None

    return CATEGORY_LEGENDARY


def get_item_name(item_id: int, item_data: dict) -> str:
    """Return the display name of an item ID or a fallback string if missing."""
    item = item_data.get(str(item_id))
    if item is None:
        return f"Unknown Item ({item_id})"
    return item.get("name", f"Unknown Item ({item_id})")


def get_item_icon_path(item_id: int, patch: str) -> Path:
    """Return local filesystem path to an item icon PNG, downloading if not cached."""
    icon_path = DATA_DIR / f"img/items/{item_id}.png"
    if icon_path.exists():
        return icon_path

    url = f"https://ddragon.leagueoflegends.com/cdn/{patch}/img/item/{item_id}.png"
    response = requests.get(url)
    response.raise_for_status()

    icon_path.parent.mkdir(parents=True, exist_ok=True)
    with open(icon_path, "wb") as file:
        file.write(response.content)

    return icon_path
