import requests
import json
import sys

from config import USERS_FILE

def get_puuid(username, tag, api_key):
    # Check if the username and tag are provided
    if not username or not tag:
        print("Error: Username and tag must be provided.")
        sys.exit(1)

    # Load cached users, or start fresh if no cache exists yet
    try:
        with open(USERS_FILE, "r") as file:
            users = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        users = {}

    # Check if the PUUID is already cached in users.txt
    if f"{username}#{tag}" in users:
        print(f"Found cached PUUID for {username}#{tag}.")
        return users[f"{username}#{tag}"]["puuid"]
    
    # If not cached, fetch the PUUID from the Riot API
    else:
        print(f"No cached PUUID found for {username}#{tag}. Fetching from Riot API...")
        puuid = fetch_puuid_from_api(username, tag, api_key)
        users[f"{username}#{tag}"] = {"puuid": puuid}
        with open(USERS_FILE, "w") as file_write:
            json.dump(users, file_write, indent=4)
        return puuid

def fetch_puuid_from_api(username, tag, api_key):
    # Construct the API URL
    api_url = f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{username}/{tag}"
    api_url_auth = api_url + "?api_key=" + api_key

    # Make the API request
    print(f"Fetching PUUID for {username}#{tag}...")
    response = requests.get(api_url_auth)

    # Check the response status code
    if response.status_code == 200:
        print("Successfully fetched PUUID.")
        data = response.json()
        puuid = data.get("puuid")
        return puuid
    else:
        print(f"Error: {response.status_code} - {response.text}")
        sys.exit(1)