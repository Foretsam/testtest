"""
Emoji Management System.

This module provides a centralized service for managing and retrieving custom emojis 
used throughout the bot. It maintains a global dictionary `emoji_cache` to store 
emoji strings (formatted as `<:name:id>`) for quick access.

Key Features:
1.  **Global Cache:** Stores all application emojis in memory to prevent repeated API calls.
2.  **Dynamic Fetching:** Can fetch emojis from the bot's application context on demand.
3.  **Fallback Mechanism:** Provides a default string if a requested emoji is missing, 
    preventing `KeyError` crashes in UI components.

Dependencies:
    - interactions (Discord interactions)
"""

import interactions as ipy

# Global storage for emoji strings
emoji_cache = {}

async def fetch_emojis(bot: ipy.Client, update: bool = False) -> dict:
    """
    Retrieves all custom emojis available to the bot application.

    This function populates the `emoji_cache` dictionary. It acts as a singleton-like
    accessor, only hitting the API if the cache is empty or if a forced update is requested.

    Args:
        bot (ipy.Client): The main bot instance used to fetch application emojis.
        update (bool): If True, forces a refresh of the cache from the Discord API.

    Returns:
        dict: A dictionary mapping emoji names to their Discord string representation.
    """
    global emoji_cache

    # Return existing cache if populated and no update requested
    if emoji_cache and not update:
        return emoji_cache

    # Fetch fresh list of emojis from the application
    application_emojis = await bot.fetch_application_emojis()
    
    # Update cache with formatted strings: <:Name:ID> or <a:Name:ID> (animated logic handled by library str())
    for emoji in application_emojis:
        emoji_cache[emoji.name] = str(emoji)

    return emoji_cache


def get_app_emoji(emoji_name: str) -> str:
    """
    Safe accessor for retrieving an emoji string from the cache.

    Args:
        emoji_name (str): The name of the emoji to retrieve.

    Returns:
        str: The formatted emoji string if found, otherwise a fallback string ("emoji_name").
             This ensures that missing emojis don't break message formatting, just visual style.
    """
    global emoji_cache
    
    # Return the cached emoji or fall back to the plain text name
    return emoji_cache.get(emoji_name, emoji_name)