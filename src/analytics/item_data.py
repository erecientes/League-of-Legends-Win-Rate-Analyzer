"""
Item classification and display formatting logic. Pure data processing with zero network I/O.

Usage:
    from analytics.item_data import classify_item, get_item_name, patch_from_game_version
    category = classify_item(3078, item_data)
    name = get_item_name(3078, item_data)
"""

CATEGORY_LEGENDARY = "legendary"
CATEGORY_BOOTS = "boots"


def patch_from_game_version(game_version: str) -> str:
    """Format gameVersion (e.g. '14.14.567.1234') into Data Dragon patch format ('14.14.1')."""
    major, minor, *_ = game_version.split(".")
    return f"{major}.{minor}.1"


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
