from riot_client import RiotAPIClient, InvalidAPIKeyError, RiotAPIError
from get_key import load_saved_key, update_key
from get_puuid import get_puuid
import match_cache
 
 
def update_match_db(cache, client, puuid: str, count: int = 20) -> None:
    """Fetch recent ranked solo/duo match IDs and cache any that are new."""

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
    print(f"Fetching ranked data for PUUID: {puuid}...")
    ranked_data = client.get_rank(puuid)
    # TODO: implement logic to store ranked_data in the cache/db as needed.
 
 
def main():
    client = RiotAPIClient(api_key=load_saved_key(), key_refresh_callback=update_key)
 
    username = input("Enter the username: ")
    tag = input("Enter the tag: ")
 
    try:
        puuid = get_puuid(username, tag, client)
        cache = match_cache.MatchCache(f"matches_{puuid}.db")
        cache_rank(client, puuid)
        update_match_db(cache, client, puuid)
        
 
    except InvalidAPIKeyError:
        print(
            "Could not authenticate with the Riot API, even after entering "
            "a new key. Double check the key is correct and try running "
            "the program again."
        )
    except RiotAPIError as e:
        print(f"Riot API request failed: {e}")
    except ValueError as e:
        # e.g. get_puuid's "username/tag must be provided" check
        print(f"Input error: {e}")
 
 
if __name__ == "__main__":
    main()