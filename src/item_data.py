"""
item_data.py

Fetches and caches Riot's Data Dragon item metadata, used to classify
purchased items into build-order categories (legendary, boots, ...).
Item definitions are specific to a patch but never change once that
patch is released, so the cache is keyed by patch version and never
needs invalidating within a single patch.
"""

import json

import requests

from config import DATA_DIR

CATEGORY_LEGENDARY = "legendary"
CATEGORY_BOOTS = "boots"
# Future categories (e.g. a CATEGORY_JUNGLE_ITEM) get added here, plus one
# rule inside classify_item below -- nothing else in this module, and
# nothing in analysis_cache.py, needs to change to support a new category.


def patch_from_game_version(game_version: str) -> str:
    """Converts a match's full gameVersion (e.g. "14.14.567.1234") into
    Data Dragon's patch-folder format (e.g. "14.14.1")."""
    major, minor, *_ = game_version.split(".")
    return f"{major}.{minor}.1"


def load_item_data(patch: str) -> dict:
    """Returns Data Dragon's item.json "data" dict for the given patch,
    keyed by item_id (as a string). Cached to disk per-patch, so repeated
    runs (and repeated matches on the same patch) never re-fetch it."""
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
    """Returns the item's build-order category, or None to exclude it
    (components, consumables, trinkets, starter items, wards, etc.).

    Legendary status is based on whether the item is built from
    components ("from" non-empty), and does not build into 
    anything else ("into" empty). Boots are classified separately.
    """
    info = item_data.get(str(item_id))
    if info is None:
        return None  # unrecognized item id -- skip rather than guess

    tags = set(info.get("tags", []))

    if "Boots" in tags:
        return CATEGORY_BOOTS

    if "into" in info:
        return None  # still buildable into something else -- not completed
    if not info.get("from"):
        return None  # nothing was combined to make this -- starter item, trinket, base component
    if tags & {"Consumable", "Trinket"}:
        return None

    return CATEGORY_LEGENDARY