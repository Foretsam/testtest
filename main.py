import asyncio
import sys  
import os
import json
import interactions as ipy
import coc
import truststore
from dotenv import load_dotenv
from core.utils import get_extensions

# Load environment variables
load_dotenv()

# --- SECURITY & CREDENTIALS ---
TOKEN = os.getenv("MAIN_TOKEN")
COC_EMAIL = os.getenv("COC_EMAIL")
COC_PASSWORD = os.getenv("COC_PASSWORD")

# --- INTENTS CONFIGURATION ---
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

# --- BOT SETUP ---
# Removed owner_ids hardcoding (optional: can fetch from env or keep if you prefer)
bot = ipy.Client(
    token=TOKEN,
    intents=INTENTS,
    sync_interactions=True,
    send_command_tracebacks=False,
    send_not_ready_messages=True,
    owner_ids=[324018900587118592], 
    activity=ipy.Activity(
        name="Version 3.0",
        type=ipy.ActivityType.PLAYING,
    ),
    fetch_members=True # Always True for Main
)

@ipy.listen(ipy.events.Startup)
async def on_start():
    print('Logged in as')
    print(bot.user.username)
    print(bot.user.id)
    print(f"Interactions Version: {ipy.__version__}")
    print(f"COC.py Version: {coc.__version__}")
    print('------')
    print("Mode: MAIN")

async def main():
    truststore.inject_into_ssl()

    try:
        # NOTE: Ensure 'MAIN_KEY' is the name of your key in the Developer Portal
        key_name = os.getenv("MAIN_KEY") 
        coc_client = coc.EventsClient(key_name=key_name)
        
        if not COC_EMAIL or not COC_PASSWORD:
            print("Error: COC_EMAIL or COC_PASSWORD not found in .env file.")
            return

        await coc_client.login(COC_EMAIL, COC_PASSWORD)
        print(f"Logged into Clash API as {COC_EMAIL}")

    except coc.InvalidCredentials as error:
        print("Clash API Login Failed: Invalid Credentials")
        exit(error)

    # Load Clan Updates
    try:
        with open("data/clans_config.json", "r") as f:
            clans_data = json.load(f)
            coc_client.add_clan_updates(*clans_data.keys())
    except FileNotFoundError:
        print("Warning: data/clans_config.json not found.")

    bot.coc = coc_client
    
    # Load Extensions
    # Ensure get_extensions is imported from core.utils or defined here
    for extension in get_extensions("cogs"):
        try:
            bot.load_extension(extension)
        except Exception as e:
            print(f"Failed to load {extension} extension: {e}", file=sys.stderr)

    await bot.astart()

if __name__ == "__main__":
    asyncio.run(main())