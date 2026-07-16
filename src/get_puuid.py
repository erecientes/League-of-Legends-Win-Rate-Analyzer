import json
 
from config import USERS_FILE
 
 
def get_puuid(username: str, tag: str, client) -> str:
    """client: a RiotAPIClient instance (see riot_client.py)."""
    if not username or not tag:
        raise ValueError("Username and tag must be provided.")
 
    # Load cached users, or start fresh if no cache exists yet
    try:
        with open(USERS_FILE, "r") as file:
            users = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        users = {}
 
    key = f"{username}#{tag}"
 
    # Check if the PUUID is already cached
    if key in users:
        print(f"Found cached PUUID for {key}.")
        return users[key]["puuid"]
 
    # Not cached -- fetch it from the Riot API via the shared client.
    # Any 403 (bad/expired key) is already handled inside client._request --
    # it'll refresh and retry automatically. RiotAPIError/InvalidAPIKeyError
    # propagate up to whoever called get_puuid, for them to handle.
    print(f"No cached PUUID found for {key}. Fetching from Riot API...")
    puuid = client.get_puuid(username, tag)
 
    users[key] = {"puuid": puuid}
    with open(USERS_FILE, "w") as file_write:
        json.dump(users, file_write, indent=4)
 
    print("Successfully fetched PUUID.")
    return puuid