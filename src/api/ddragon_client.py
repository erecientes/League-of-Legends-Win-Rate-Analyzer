"""
Data Dragon CDN client for static League assets (metadata JSON and image icons).

Usage:
    from api.ddragon_client import DDragonClient
    client = DDragonClient()
    latest_patch = client.get_latest_patch()
    item_data = client.get_item_data(latest_patch)
    icon_path = client.get_item_icon_path(3078, latest_patch)
"""

import json
from pathlib import Path
import requests

from config import DATA_DIR


class DDragonClient:
    """Client for fetching and local-caching static League data and assets from Riot's Data Dragon CDN."""

    def __init__(self, base_url: str = "https://ddragon.leagueoflegends.com"):
        self.base_url = base_url.rstrip("/")

    def get_latest_patch(self) -> str:
        """Fetch the latest active League patch version from Data Dragon, falling back to local cache if offline."""
        url = f"{self.base_url}/api/versions.json"
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            versions = response.json()
            if versions and isinstance(versions, list):
                return versions[0]
        except requests.RequestException:
            pass

        # Fallback to newest cached patch file on disk
        cached_patches = sorted(DATA_DIR.glob("item_data_*.json"))
        if cached_patches:
            filename = cached_patches[-1].stem  # e.g. item_data_16.14.1
            return filename.replace("item_data_", "")

        return "16.14.1"

    def get_item_data(self, patch: str) -> dict:
        """Fetch and disk-cache Data Dragon item metadata for a specific patch."""
        cache_path = DATA_DIR / f"item_data_{patch}.json"
        if cache_path.exists():
            with open(cache_path) as file:
                return json.load(file)

        url = f"{self.base_url}/cdn/{patch}/data/en_US/item.json"
        response = requests.get(url)
        response.raise_for_status()
        item_data = response.json()["data"]

        with open(cache_path, "w") as file:
            json.dump(item_data, file)

        return item_data

    def get_item_icon_path(self, item_id: int, patch: str) -> Path:
        """Return local filesystem path to an item icon PNG, downloading from CDN if not cached."""
        icon_path = DATA_DIR / f"img/items/{item_id}.png"
        if icon_path.exists():
            return icon_path

        url = f"{self.base_url}/cdn/{patch}/img/item/{item_id}.png"
        response = requests.get(url)
        response.raise_for_status()

        icon_path.parent.mkdir(parents=True, exist_ok=True)
        with open(icon_path, "wb") as file:
            file.write(response.content)

        return icon_path

