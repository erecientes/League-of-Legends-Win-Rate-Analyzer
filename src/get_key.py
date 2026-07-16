from config import API_KEY_FILE
 
def load_saved_key() -> str:
    """Read the currently-saved key, prompting for one if none exists yet."""
    try:
        with open(API_KEY_FILE, "r") as file:
            return file.read().strip()
    except FileNotFoundError:
        return update_key()
 
def update_key() -> str:
    """Prompt the user for a new key, persist it, and return it.
    Passes to RiotAPIClient as key_refresh_callback."""
    new_key = input(
        "Your Riot API key appears to be missing, invalid, or expired.\n"
        "Enter a new API key: "
    ).strip()
    with open(API_KEY_FILE, "w") as file:
        file.write(new_key)
    print(f"API key saved to {API_KEY_FILE}.")
    return new_key
 