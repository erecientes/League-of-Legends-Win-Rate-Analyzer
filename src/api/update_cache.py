"""
CLI entry point to fetch and cache matches and ranked data.

Usage:
    python src/update_cache.py
"""

from api.riot_client import RiotAPIClient, InvalidAPIKeyError, RiotAPIError
from api.get_key import load_saved_key, update_key
from api.get_puuid import get_puuid
from storage.match_cache import MatchCache


def update_match_db(cache, client, puuid: str, count: int = 20) -> None:
    """Fetch recent ranked match IDs and cache missing matches/timelines."""
    print(f"Fetching match history for PUUID: {puuid}...")
    new_match_ids = client.get_match_ids(puuid, count=count)
    print(f"Found {len(new_match_ids)} recent matches.")

    for match_id in new_match_ids:
        if cache.has_match(match_id):
            print(f"Match ID {match_id} already cached. Skipping...")
            continue

        print(f"Fetching match details for Match ID: {match_id}...")
        match_data, timeline_data = client.get_match_details(match_id)
        cache.save_match(match_id, match_data, timeline_data)


def cache_rank(client, puuid: str) -> None:
    """Fetch and persist ranked league entries for a PUUID."""
    print(f"Fetching ranked data for PUUID: {puuid}...")
    ranked_data = client.get_rank(puuid)
    # TODO: store ranked snapshot in database


def main():
    """Prompt for username/tag, resolve PUUID, and sync match cache."""
    client = RiotAPIClient(api_key=load_saved_key(), key_refresh_callback=update_key)

    username = input("Enter the username: ").lower().strip()
    tag = input("Enter the tag: ").lower().strip()

    try:
        puuid = get_puuid(username, tag, client)
        cache = MatchCache(f"matches_{puuid}.db")
        cache_rank(client, puuid)
        update_match_db(cache, client, puuid)

    except InvalidAPIKeyError:
        print("Authentication failed after key refresh.")
    except RiotAPIError as e:
        print(f"Riot API request failed: {e}")
    except ValueError as e:
        print(f"Input error: {e}")


if __name__ == "__main__":
    main()
