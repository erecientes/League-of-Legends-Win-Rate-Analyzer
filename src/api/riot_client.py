"""
Riot API client with automatic authentication and key refresh.

Usage:
    from riot_client import RiotAPIClient
    client = RiotAPIClient(api_key="...", key_refresh_callback=update_key_fn)
    puuid = client.get_puuid("Username", "Tag")
    match_ids = client.get_match_ids(puuid, count=20)
"""

from typing import cast
import requests


class RiotAPIError(Exception):
    """Raised when the Riot API returns an unrecoverable non-2xx status code."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"{status_code}: {message}")


class InvalidAPIKeyError(Exception):
    """Raised when authentication fails even after refreshing the API key."""
    pass


class RiotAPIClient:
    """Wrapper around Riot Games API endpoints with automatic 401/403 token refresh."""

    def __init__(self, api_key: str, key_refresh_callback):
        self.api_key = api_key
        self._get_new_key = key_refresh_callback

    def _request(self, url: str, params: dict | None = None) -> dict:
        """Execute HTTP GET with auth. Refresh and retry once on 401/403."""
        params = dict(params or {})
        params["api_key"] = self.api_key

        response = requests.get(url, params=params)

        if response.status_code in (401, 403):
            self.api_key = self._get_new_key()
            params["api_key"] = self.api_key
            response = requests.get(url, params=params)

            if response.status_code in (401, 403):
                raise InvalidAPIKeyError("API key invalid after refresh.")

        if not response.ok:
            raise RiotAPIError(response.status_code, response.text)

        return response.json()

    def get_puuid(self, username: str, tag: str) -> str:
        """Fetch account PUUID by Riot ID (gameName and tagLine)."""
        url = f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{username}/{tag}"
        data = self._request(url)
        return data["puuid"]

    def get_match_ids(self, puuid: str, count: int = 20, queue: int = 420) -> list[str]:
        """Fetch list of match IDs for a PUUID, filtered by queue ID."""
        url = f"https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
        result = self._request(url, params={"queue": queue, "start": 0, "count": count})
        return cast(list[str], result)

    def get_match(self, match_id: str) -> dict:
        """Fetch full match payload by match ID."""
        url = f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}"
        return self._request(url)

    def get_timeline(self, match_id: str) -> dict:
        """Fetch match timeline events by match ID."""
        url = f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline"
        return self._request(url)

    def get_match_details(self, match_id: str) -> tuple[dict, dict]:
        """Fetch both match and timeline payloads together."""
        return self.get_match(match_id), self.get_timeline(match_id)

    def get_rank(self, puuid: str) -> dict:
        """Fetch ranked tier, division, and LP entries for a PUUID."""
        url = f"https://na1.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"
        return self._request(url)
