"""
Application Entry Point.

This module serves as the primary entry point for the Discord bot. It initializes
both the Discord interactions client and the Clash of Clans (CoC) API client.
It is responsible for:
1. Loading environment variables and credentials.
2. Configuring bot intents and privileges.
3. Establishing the connection to the Clash of Clans API.
4. Loading application extensions (Cogs) dynamically.
5. Managing the main application lifecycle via asyncio.

Dependencies:
    - interactions (discord client)
    - coc (Clash of Clans API wrapper)
    - truststore (SSL certificate handling)
    - python-dotenv (Environment configuration)
"""

import asyncio
import sys
import os
import json
import interactions as ipy
import coc
import truststore
from dotenv import load_dotenv
from core.utils import get_extensions

# Initialize environment variables from .env file
load_dotenv()

# Global Configuration Constants
TOKEN = os.getenv("MAIN_TOKEN")
COC_EMAIL = os.getenv("COC_EMAIL")
COC_PASSWORD = os.getenv("COC_PASSWORD")

# Define the privileged intents required for the bot's operation.
# These intents must be enabled in the Discord Developer Portal.
INTENTS = ipy.Intents.new(
    guilds=True,
    guild_emojis_and_stickers=True,
    guild_presences=True,
    guild_members=True,
    guild_moderation=True,
    guild_messages=True,
    direct_messages=True,
    message_content=True,
)

# Initialize the Discord Client
# owner_ids are strictly typed to ensure access to administrative commands.
# fetch_members is enabled to ensure the member cache is populated on startup.
bot = ipy.Client(
    token=TOKEN,
    intents=INTENTS,
    sync_interactions=True,
    send_command_tracebacks=False,
    send_not_ready_messages=True,
    owner_ids=[324018900587118592],  # owner_ids need better handling in the future in order to support multi servers
    activity=ipy.Activity(
        name="Version 3.0",
        type=ipy.ActivityType.PLAYING,
    ),
    fetch_members=True
)

@ipy.listen(ipy.events.Startup)
async def on_start():
    """
    Event listener triggered when the bot has successfully logged in and is ready.
    
    Logs the bot's identity and library versions to the console for debugging purposes.
    """
    print('Logged in as')
    print(bot.user.username)
    print(bot.user.id)
    print(f"Interactions Version: {ipy.__version__}")
    print(f"COC.py Version: {coc.__version__}")
    print('------')
    print("Mode: MAIN")

async def main():
    """
    Main asynchronous execution entry point.
    
    Performs the following initialization sequence:
    1. Injects truststore to handle SSL certificates (fixes common SSL errors).
    2. Initializes and authenticates the CoC EventsClient.
    3. Loads clan configurations and registers them for API updates.
    4. Dynamically loads all extension modules (Cogs) from the 'cogs' directory.
    5. Starts the Discord bot session.
    """
    # Inject system certificate store to resolve potential SSL handshake issues
    truststore.inject_into_ssl()

    try:
        # Retrieve the specific API key name required for the CoC client
        key_name = os.getenv("MAIN_KEY") 
        coc_client = coc.EventsClient(key_name=key_name)
        
        # specific validation for critical credentials
        if not COC_EMAIL or not COC_PASSWORD:
            print("Error: COC_EMAIL or COC_PASSWORD not found in .env file.")
            return

        await coc_client.login(COC_EMAIL, COC_PASSWORD)
        print(f"Logged into Clash API as {COC_EMAIL}")

    except coc.InvalidCredentials as error:
        print("Clash API Login Failed: Invalid Credentials")
        # Exit immediately if API access is impossible
        exit(error)

    # Load Clan Configuration and register for updates
    # This allows the bot to track events for specific clans defined in the JSON config.
    try:
        with open("data/clans_config.json", "r") as f:
            clans_data = json.load(f)
            # Unpack clan tags and add them to the client's update watcher
            coc_client.add_clan_updates(*clans_data.keys())
    except FileNotFoundError:
        print("Warning: data/clans_config.json not found. Clan updates will not be tracked.")

    # Attach the authenticated CoC client to the bot instance for global access in Cogs
    bot.coc = coc_client
    
    # Dynamically load extensions
    # Iterates through modules found in the 'cogs' directory via core.utils.get_extensions
    for extension in get_extensions("cogs"):
        try:
            bot.load_extension(extension)
        except Exception as e:
            # Log failure to stderr to distinguish from standard logs, but continue loading others
            print(f"Failed to load {extension} extension: {e}", file=sys.stderr)

    # Begin the Discord Gateway connection
    await bot.astart()

if __name__ == "__main__":
    asyncio.run(main())