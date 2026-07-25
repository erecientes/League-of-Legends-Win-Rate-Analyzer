"""
Usage:
    from riot_client import RiotAPIClient, InvalidAPIKeyError, RiotAPIError
    from update_key import get_new_key   # see update_key.py
 
    client = RiotAPIClient(api_key=load_saved_key(), key_refresh_callback=get_new_key)
 
    try:
        puuid = client.get_puuid("Skorug", "2104")
    except InvalidAPIKeyError:
        print("Could not authenticate with Riot's API even after refreshing the key.")
    except RiotAPIError as e:
        print(f"Riot API error: {e}")
"""

from typing import cast
import requests
 
class RiotAPIError(Exception):
    """Raised for any non-2xx Riot API response that ISN'T a recoverable
    403 (e.g. 404 not found, 429 rate limited, 500 server error)."""
    def __init__(self, status_code, message):
        self.status_code = status_code
        super().__init__(f"{status_code}: {message}")

 
class InvalidAPIKeyError(Exception):
    """Raised when the API key is still invalid even after one refresh attempt."""
    pass

 
class RiotAPIClient:
    def __init__(self, api_key: str, key_refresh_callback):
        """
        api_key: the current Riot API key to use.
        key_refresh_callback: a zero-argument function that returns a NEW
            key when called (e.g. prompts the user, reads updated config,
            shows a dialog). This client doesn't care HOW you get a new
            key, only that calling this function gives you one.
        """
        self.api_key = api_key
        self._get_new_key = key_refresh_callback
 
    def _request(self, url: str, params: dict | None = None) -> dict:
        """Every endpoint method funnels through here. Handles:
          - attaching the current api_key
          - refreshing + retrying ONCE on a 403
          - raising RiotAPIError for any other failure status
        """
        params = dict(params or {})
        params["api_key"] = self.api_key
 
        response = requests.get(url, params=params)
 
        AUTH_FAILURE_CODES = (401, 403)  # 401: key missing/empty, 403: key invalid/expired
        if response.status_code in AUTH_FAILURE_CODES:
            # Key is invalid or expired. Refresh once, retry once.
            self.api_key = self._get_new_key()
            params["api_key"] = self.api_key
            response = requests.get(url, params=params)
 
            if response.status_code == 403:
                raise InvalidAPIKeyError(
                    "API key still invalid after a refresh attempt."
                )
 
        if not response.ok:
            raise RiotAPIError(response.status_code, response.text)
 
        return response.json()
 
    # ---- Endpoint methods -------------------------------------------------
 
    def get_puuid(self, username: str, tag: str) -> str:
        url = f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{username}/{tag}"
        data = self._request(url)
        return data["puuid"]
 
    def get_match_ids(self, puuid: str, count: int = 20, queue: int = 420) -> list[str]:
        url = f"https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
        result = self._request(url, params={"queue": queue, "start": 0, "count": count})
        return cast(list[str], result) 
 
    def get_match(self, match_id: str) -> dict:
        url = f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}"
        return self._request(url)
 
    def get_timeline(self, match_id: str) -> dict:
        url = f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline"
        return self._request(url)
 
    def get_match_details(self, match_id: str) -> tuple[dict, dict]:
        """Convenience wrapper: fetches match + timeline together, since
        your cache always wants both at once."""
        return self.get_match(match_id), self.get_timeline(match_id)
 
    def get_rank(self, puuid: str) -> dict:
        # NOTE: worth double-checking this endpoint -- league-v4's
        # by-summoner route expects an encrypted summonerId, not a puuid.
        # There's a separate by-puuid variant; flagging this in case it's
        # silently returning a 404/empty result rather than what you expect.
        url = f"https://na1.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"
        return self._request(url)