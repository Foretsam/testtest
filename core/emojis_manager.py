import interactions as ipy

emojis_cache = {}

async def fetch_emojis(bot: ipy.Client, get_type: int = 1, update: bool = False):
    """
    Fetches Application Emojis (Developer Portal) and caches them.
    
    get_type 0: Returns {name: id} (int)
    get_type 1: Returns {name: "<:name:id>"} (str) - DEFAULT
    get_type 2: Returns {name: EmojiObject} (full object)
    """
    cache_key = "APP_EMOJIS"

    # Return cached version if we have it and aren't forcing an update
    # Note: We cache the full object list effectively, but for simplicity 
    # in this transition, we will rebuild the dict format requested.
    if not update and cache_key in emojis_cache:
        cached_data = emojis_cache[cache_key]
        # If the cache is already in the format we want, return it.
        # Otherwise, we proceed to re-fetch/re-format.
        return cached_data

    # Fetch emojis directly from the application (Developer Portal)
    app_emojis = await bot.fetch_application_emojis()
    
    formatted_emojis = {}
    for emoji in app_emojis:
        if get_type == 0:
            formatted_emojis[emoji.name] = int(emoji.id)
        elif get_type == 1:
            # We store the formatted string so it's ready to use in f-strings
            formatted_emojis[emoji.name] = str(emoji) 
        elif get_type == 2:
            formatted_emojis[emoji.name] = emoji

    # Update the cache
    emojis_cache[cache_key] = formatted_emojis
    return formatted_emojis

# Add this helper function to make using them easier in your commands
def get_app_emoji(name: str):
    """Safely gets an app emoji, returns the name as text if not found"""
    # This helper assumes the cache is stored as Type 1 (formatted strings)
    return emojis_cache.get("APP_EMOJIS", {}).get(name, f":{name}:")
