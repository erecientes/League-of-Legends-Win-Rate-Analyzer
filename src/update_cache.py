import sys
import requests

from get_puuid import get_puuid
import match_cache
from config import API_KEY_FILE

def get_solo_duo_match_history(puuid, api_key, count=20):
    # Construct the match history API URL
    match_api_url = f"https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?queue=420&start=0&count={count}&api_key={api_key}"

    # Make the match history API request
    print(f"Fetching match history for PUUID: {puuid}...")
    match_response = requests.get(match_api_url)

    # Check the match history response status code
    if match_response.status_code == 200:
        print("Successfully fetched match history.")
        match_data = match_response.json()
        return match_data
    else:
        print(f"Error: {match_response.status_code} - {match_response.text}")
        sys.exit(1)

def get_match_details(match_id, api_key):
    # Construct the match details API URL
    match_details_url = f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}?api_key={api_key}"

    # Make the match details API request
    print(f"Fetching match details for Match ID: {match_id}...")
    match_details_response = requests.get(match_details_url)

    # Check the match details response status code
    if match_details_response.status_code == 200:
        print("Successfully fetched match details.")
        match_details_data = match_details_response.json()
        return match_details_data
    else:
        print(f"Error: {match_details_response.status_code} - {match_details_response.text}")
        sys.exit(1)

def update_cache(cache, puuid, api_key):
    # Get the match history for the given PUUID
    new_matches = get_solo_duo_match_history(puuid, api_key)

    for match_id in new_matches:
        if not cache.has_match(match_id):
            match_data = get_match_details(match_id, api_key)
            cache.save_match(match_id, match_data)
        else:
            print(f"Match ID {match_id} already exists in cache. Skipping...")

def main():
    # Get the API key from a file
    with open(API_KEY_FILE, "r") as file:
        api_key = file.read().strip()

    # Get the username and tag from user input
    username = input("Enter the username: ")
    tag = input("Enter the tag: ")
    # username = "Skorug"
    # tag = "2104"

    # Get the PUUID for the given username and tag
    puuid = get_puuid(username, tag, api_key)

    # Initialize the match cache
    cache = match_cache.MatchCache(f"matches_{puuid}.db")

    # Update the cache with new matches
    update_cache(cache, puuid, api_key)

if __name__ == "__main__":
    main()