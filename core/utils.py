"""
General Utility Module.

This module provides a collection of helper functions and shared resources used throughout
the application. It handles:
1.  **API Caching:** Wrapper functions (`fetch_clan`, `fetch_player`) to retrieve and cache 
    Clash of Clans API data, reducing rate limits and latency.
2.  **Data Processing:** Utilities for string manipulation (tag extraction), data structure 
    conversion (flattening lists, reversing dicts), and numeric formatting.
3.  **Discord UI Helpers:** Generators for progress bars, color constants, and standard 
    Embeds/Buttons used across different extensions.
4.  **Bot Management:** Functions for dynamic extension loading and process restarting.

Dependencies:
    - interactions (Discord interactions)
    - coc (Clash of Clans API wrapper)
    - aiohttp (Network requests for image validation)
    - core (Internal configuration and emoji management)
"""

import inspect
import json
import re
import sys
import os
from typing import Iterable, Coroutine, Callable
from core import server_setup as sc

import aiohttp
import coc
import copy
import interactions as ipy
import random
from coc import utils

from core.models import InvalidTagError
from core.emojis_manager import *

# ==========================================
# GLOBAL CACHE & CONSTANTS
# ==========================================

# In-memory storage to reduce API calls for frequently accessed data
clan_cache = {}
player_cache = {}
overwrites_cache = {}

# Standard color for Embeds (Gold/Tan)
COLOR = 0xD8AF60

# Static Banner URLs for Embeds
# Note: CLAN_BANNER_URL appears twice; the second assignment effectively overwrites the first.
CLAN_BANNER_URL = "https://cdn.discordapp.com/attachments/1410359521636909098/1410360368865214656/AFO_-_PARTNER_Apply_Channel.png?ex=68b0bbf3&is=68af6a73&hm=211c572ba6061125ed412f8d94f5f7c85f913a1052e6cecf77a9849cdf0b2115&"

PARTNER_BANNER_URL = "https://cdn.discordapp.com/attachments/1410359521636909098/1410360368865214656/AFO_-_PARTNER_Apply_Channel.png?ex=68b0bbf3&is=68af6a73&hm=211c572ba6061125ed412f8d94f5f7c85f913a1052e6cecf77a9849cdf0b2115&"
CHAMPIONS_BANNER_URL = "https://cdn.discordapp.com/attachments/1410359521636909098/1410360524079632466/AFO_-_CHAMPIONS_Apply_Channel.png?ex=68b0bc18&is=68af6a98&hm=b41797320e45e657ffc60b3995131d461048751137e0ef09cb37b397d7f7ab22&"
CLAN_BANNER_URL = "https://cdn.discordapp.com/attachments/1410359521636909098/1410360141966086256/AFO_-_CLAN_Apply_Channel.png?ex=68b0bbbd&is=68af6a3d&hm=ee9598ec8f7f6f0c492eac4a3ae4db934c96d855c4fca247fd931d79c9c26339&"
COACHING_BANNER_URL = "https://cdn.discordapp.com/attachments/1410359521636909098/1410360948178292826/AFO_-_COACHING_Channel.png?ex=68b0bc7d&is=68af6afd&hm=226932206c671e782b6659c57706dd3ce5d4d2b68b9118acaf6f3e8114958790&"
SUPPORT_BANNER_URL = "https://cdn.discordapp.com/attachments/1410359521636909098/1410361966836322575/AFO_-_AFO_SUPPORT_Channel.png?ex=68b0bd70&is=68af6bf0&hm=ce07856b0f94b4df069d05620cd29192592665b732a8a673eceaeeb1e757c0b9&"
STAFF_BANNER_URL = "https://cdn.discordapp.com/attachments/1410359521636909098/1410360262598328461/AFO_-_STAFF_Apply_Channel.png?ex=68b0bbd9&is=68af6a59&hm=650d0d76d11e25af11754c46da4cab2517ce7a4944fc8aa6c56bd60c46c9f07e&"
FWA_BANNER_URL = "https://cdn.discordapp.com/attachments/1410359521636909098/1410360674256814101/AFO_-_FWA_Apply_Channel.png?ex=68b0bc3b&is=68af6abb&hm=6663cf5ce43d2f1f4744aa327ef9fd5acffc44ca22b129dd11e2efe109f7e88d&"

LINE_URL = "https://cdn.discordapp.com/attachments/881073424884199435/1069179365302227075/animated-line-image-0379.gif?ex=67613ce1&is=675feb61&hm=e63343839bc38e500aabe5950d4c2e040ce003bedbc4c285fcab60cf3c83e0f1&"

FAMILY_ICON_URL = "https://cdn.discordapp.com/attachments/881073424884199435/890287615968948244/699834141931339777.png?ex=6761b3f4&is=67606274&hm=1fc7a58d38acff631aacb76f7266a28564fe94a3b7fbdb7c8e8a4d2aebc76f91&"
STAFF_SERVER_URL = "https://discord.gg/gY5wc8sXdF"

# Mapping for Clan configurations
CLAN_TYPE_DICT = {
    "open": "Open",
    "closed": "Closed",
    "inviteOnly": "Invite Only"
}

CLAN_TYPE_DATA = {
    "comp": "competitive",
    "fwa": "FWA",
    "cwl": "CWL"
}

# Mapping ASCII characters to Mathematical Bold Serif Unicode characters
# Used for stylizing channel names (e.g., "ticket" -> "𝐭𝐢𝐜𝐤𝐞𝐭")
PREFIX_DICT = {
    ord("a"): "𝐚", ord("b"): "𝐛", ord("c"): "𝐜", ord("d"): "𝐝", ord("e"): "𝐞", ord("f"): "𝐟", ord("g"): "𝐠",
    ord("h"): "𝐡", ord("i"): "𝐢", ord("j"): "𝐣", ord("k"): "𝐤", ord("l"): "𝐥", ord("m"): "𝐦", ord("n"): "𝐧",
    ord("o"): "𝐨", ord("p"): "𝐩", ord("q"): "𝐪", ord("r"): "𝐫", ord("s"): "𝐬", ord("t"): "𝐭", ord("u"): "𝐮",
    ord("v"): "𝐯", ord("w"): "𝐰", ord("x"): "𝐱", ord("y"): "𝐲", ord("z"): "𝐳",
    ord("A"): "𝐀", ord("B"): "𝐁", ord("C"): "𝐂", ord("D"): "𝐃", ord("E"): "𝐄", ord("F"): "𝐅", ord("G"): "𝐆",
    ord("H"): "𝐇", ord("I"): "𝐈", ord("J"): "𝐉", ord("K"): "𝐊", ord("L"): "𝐋", ord("M"): "𝐌", ord("N"): "𝐍",
    ord("O"): "𝐎", ord("P"): "𝐏", ord("Q"): "𝐐", ord("R"): "𝐑", ord("S"): "𝐒", ord("T"): "𝐓", ord("U"): "𝐔",
    ord("V"): "𝐕", ord("W"): "𝐖", ord("X"): "𝐗", ord("Y"): "𝐘", ord("Z"): "𝐙"
}

# Helper mappings for ordinals and numbers
NUMBER_DICT = {1: "`1st`", 2: "`2nd`", 3: "`3rd`"}

NUMBER_EMOJIS = {
    1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣",
    6: "6️⃣", 7: "7️⃣", 8: "8️⃣", 9: "9️⃣", 10: "🔟"
}

# --- Standardized Embeds & Components ---

FAIL_EMBED = ipy.Embed(
    title=f"**Interview Ended**",
    description=f"{get_app_emoji('error')} Your responses are invalid for more than 3 times, the interview has now ended.",
    footer=ipy.EmbedFooter(
        text="Press \"Human Support\" if further supports are needed."
    ),
    color=COLOR
)

TIMEOUT_EMBED = ipy.Embed(
    title=f"**Command Timed Out**",
    description=f"{get_app_emoji('error')} It took you too long to respond correctly.",
    footer=ipy.EmbedFooter(
        text="Press \"Human Support\" for further assistance."),
    color=COLOR
)

REPORT_BUTTON = ipy.Button(
    style=ipy.ButtonStyle.DANGER,
    label="Report Bug",
    custom_id="report_bug_button",
    emoji=ipy.PartialEmoji(name="📢")
)

CLAN_RESTART_BUTTON = ipy.Button(
    style=ipy.ButtonStyle.SECONDARY,
    label="Restart",
    custom_id="clan_start_button",
    emoji=ipy.PartialEmoji(name="↩️")
)

FWA_RESTART_BUTTON = ipy.Button(
    style=ipy.ButtonStyle.SECONDARY,
    label="Restart",
    custom_id="fwa_start_button",
    emoji=ipy.PartialEmoji(name="↩️")
)

BUG_RESPOND_BUTTON = ipy.Button(
    style=ipy.ButtonStyle.SECONDARY,
    label="Respond",
    custom_id="bug_respond_button",
    emoji=ipy.PartialEmoji(name="StaffIcon", id=1318289342736629902)
)

# ==========================================
# SYSTEM UTILITIES
# ==========================================

def get_extensions(root_folder: str) -> list[str]:
    """
    Recursively finds all Python extensions (cogs) in the given root folder.
    Excludes any files starting with '_'.

    Args:
        root_folder (str): The base directory to search.

    Returns:
        list[str]: A list of module paths in dot notation (e.g., 'cogs.general.tickets').
    """
    extensions = []
    
    for root, dirs, files in os.walk(root_folder):
        for filename in files:
            if filename.endswith(".py") and not filename.startswith("_"):
                # Join path and normalize to dot notation for import
                file_path = os.path.join(root, filename)
                # Remove .py extension and replace OS-specific separators with dots
                module_path = file_path[:-3].replace(os.path.sep, ".")
                extensions.append(module_path)

    return extensions

def progress_bar(percent: float, length: int = 12, symbol: str = "▓", empty_symbol: str = "░",
                 show_percent: bool = True) -> str:
    """
    Generates a text-based progress bar.

    Args:
        percent (float): Progress value between 0.0 and 1.0.
        length (int): Total character length of the bar.
        symbol (str): Character for filled portion.
        empty_symbol (str): Character for empty portion.
        show_percent (bool): Whether to append the percentage text at the end.

    Returns:
        str: The formatted progress bar string.
    """
    filled_length = int(length * percent)
    empty_length = length - filled_length

    progress = symbol * filled_length + empty_symbol * empty_length

    if show_percent:
        percent_formatted = f'{percent * 100:.2f}%'
        progress += ' ' + percent_formatted

    return progress

def translate_clan_type(clan_type: str):
    """Translates API clan type values (e.g., 'inviteOnly') to readable text."""
    for key, value in CLAN_TYPE_DICT.items():
        if clan_type == key:
            return value

def bot_restart():
    """Restarts the current Python process."""
    os.execv(sys.executable, ['python'] + sys.argv)

from typing import Iterable, Any

def flatten(lst: Iterable[Any]) -> Iterable[Any]:
    """
    Generator that flattens a nested iterable into a single sequence.
    Handles arbitrary nesting depth.
    """
    for item in lst:
        if isinstance(item, Iterable) and not isinstance(item, (str, bytes)):
            for x in flatten(item):
                yield x
        else:
            yield item

def reverse_dict(dictionary):
    """
    Inverts a dictionary where values are lists.
    Maps {key: [val1, val2]} to {val1: [key], val2: [key]}.
    """
    reversed_dict = dict()
    for key in dictionary:

        for item in dictionary[key]:

            if item not in reversed_dict:
                reversed_dict[item] = [key]
            else:
                reversed_dict[item].append(key)

    return reversed_dict

def replace_special_char(str_input: str, replacement: str):
    """Replaces non-alphanumeric characters in a string with a specified replacement."""
    return ''.join(c if c.isalpha() or c.isnumeric() else replacement for c in str_input)

def extract_alphabets(input_string: str) -> str:
    """Removes all non-alphabet characters and converts to lowercase (keeps spaces as dashes)."""
    alphabets_only = re.sub(r'[^a-z]', '', input_string.lower())
    alphabets_only = alphabets_only.replace(' ', '-')
    return alphabets_only

def extract_integer(input_string: str, index: int = 0) -> int | None:
    """
    Extracts integers from a string using regex.
    
    Args:
        input_string (str): The source string.
        index (int): Which integer match to return (default 0 for the first one).
    
    Returns:
        int | None: The extracted integer or None if no match found.
    """
    if not input_string:
        return None

    match = re.findall(r'\d+', input_string)
    if match:
        return int(match[index])
    return None

def get_func_params(func: Coroutine | Callable) -> list[str]:
    """Inspects a function and returns a list of its parameter names."""
    sig = inspect.signature(func)
    params = [name for name, param in sig.parameters.items()]
    return params

def hex_to_rgb_integer(hex_code: str) -> int:
    """Converts a hex color code (e.g., #FFFFFF) to a base-10 integer."""
    if not hex_code:
        return None

    hex_code = hex_code.replace("#", "")

    r = int(hex_code[0:2], 16)
    g = int(hex_code[2:4], 16)
    b = int(hex_code[4:6], 16)

    rgb_integer = (r << 16) + (g << 8) + b
    return rgb_integer

async def extract_tags(client: coc.Client, str_input: str,
                       context: ipy.SlashContext | ipy.ContextMenuContext | ipy.ModalContext = None,
                       extract_type: str = "player") -> list[str] | list:
    """
    Extracts and validates Clash of Clans tags from a raw string.

    Splits the string by special characters/spaces, then attempts to fetch each potential
    tag from the CoC API to verify existence.

    Args:
        client (coc.Client): API client for validation.
        str_input (str): The input string containing tags.
        context (ipy.Context, optional): Context to report errors to the user.
        extract_type (str): "player" or "clan" to specify validation endpoint.

    Returns:
        list[str]: A list of valid, formatted tags.
    """
    valid_tags = []
    sections = replace_special_char(str_input, " ").split(" ")

    for s in sections:
        if not utils.is_valid_tag(s):
            continue

        try:
            await fetch_player(client, s) if extract_type == "player" else await fetch_clan(client, s)
        except coc.errors.NotFound:
            if context:
                await context.send(f"<:error:827078558140334100> `{s}` is invalid.", ephemeral=True)

            continue

        valid_tags.append(utils.correct_tag(s))

    return valid_tags

async def is_url_image(image_url):
    """
    Verifies if a URL points to a valid image file by checking Content-Type headers.
    """
    image_formats = ("image/png", "image/jpeg", "image/jpg")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(image_url) as r:
                content_type = r.headers.get("content-type")
                if content_type in image_formats:
                    return True
                return False
    except:
        return False


# ==========================================
# API CACHING WRAPPERS
# ==========================================

async def fetch_clan(client: coc.Client, clan_tag: str, update: bool = False) -> coc.Clan:
    """
    Retrieves clan data from the API, using a local cache to minimize requests.

    Args:
        client (coc.Client): The API client.
        clan_tag (str): The clan tag to fetch.
        update (bool): If True, bypasses cache and forces an API request.

    Returns:
        coc.Clan: The clan object.
    
    Raises:
        InvalidTagError: If the tag is malformed or not found.
    """
    cache_key = coc.utils.correct_tag(clan_tag)

    if not update and cache_key in clan_cache:
        return clan_cache[cache_key]

    try:
        result = await client.get_clan(cache_key)
    except coc.errors.NotFound:
        raise InvalidTagError(cache_key, "clan")

    clan_cache[cache_key] = result

    return result


async def fetch_player(client: coc.Client, player_tag: str, update: bool = False) -> coc.Player:
    """
    Retrieves player data from the API, using a local cache to minimize requests.

    Args:
        client (coc.Client): The API client.
        player_tag (str): The player tag to fetch.
        update (bool): If True, bypasses cache and forces an API request.

    Returns:
        coc.Player: The player object.
    
    Raises:
        InvalidTagError: If the tag is malformed or not found.
    """
    cache_key = coc.utils.correct_tag(player_tag)

    if not update and cache_key in player_cache:
        return player_cache[cache_key]

    try:
        result = await client.get_player(cache_key)
    except coc.errors.NotFound:
        raise InvalidTagError(cache_key, "player")

    player_cache[cache_key] = result

    return result

async def fetch_overwrites(bot: ipy.Client, channel_id: int, update: bool = False):
    """
    Retrieves and caches permission overwrites for a specific channel.
    Useful for creating new channels with identical permissions (templating).
    """
    cache_key = int(channel_id)

    if not update and cache_key in overwrites_cache:
        return copy.deepcopy(overwrites_cache[cache_key])

    try:
        channel = await bot.fetch_channel(channel_id, force=True)
    except ipy.errors.NotFound:
        return []

    overwrite_ids = []
    channel_overwrites = []
    # Flatten overwrites to ensure we get a simple list
    for overwrite in flatten(channel.permission_overwrites):
        if overwrite.id not in overwrite_ids:
            channel_overwrites.append(overwrite)
            overwrite_ids.append(overwrite.id)

    overwrites_cache[cache_key] = channel_overwrites

    return copy.deepcopy(channel_overwrites)

async def initialize_cache(bot: ipy.Client, client: coc.Client, apply_categories: list[int]):
    """
    Performs startup caching operations.
    Loads all configured alliance clans and fetches application emojis.
    """
    # Load Alliance Data
    clans_config = json.load(open(f"data/clans_config.json", "r"))
    for clan_tag in clans_config:
        await fetch_clan(client, clan_tag)

    # Load Application Emojis
    print("➤ Fetching Application Emojis...")
    await fetch_emojis(bot, get_type=1) 
    
    print("➤ All necessary cache initialized")

async def remove_player_duplicates(bot: ipy.Client, main_guild_id: int):
    """
    Maintenance task to clean up linked accounts.
    If multiple Discord users claim to own the same CoC account, this function
    prioritizes the user who is actually present in the main Discord guild.
    """
    player_links = json.load(open("data/member_tags.json", "r"))
    guild = await bot.fetch_guild(main_guild_id, force=True)
    guild_member_ids = [str(member.id) for member in guild.members]

    # Check reversed dict (Tag -> [UserIDs])
    for key, player_ids in reverse_dict(player_links).items():
        if len(player_ids) > 1:
            # Check which user ID is actually in the server
            membership_status = {player_id: player_id in guild_member_ids for player_id in player_ids}

            # Prioritize the member in the guild
            members_in_guild = [k for k, v in membership_status.items() if v]
            target_member = members_in_guild[0] if members_in_guild else list(membership_status.keys())[0]
            
            # Remove link from other users
            player_links[str(target_member)].remove(key)

    with open("data/member_tags.json", "w") as file:
        json.dump(player_links, file, indent=4)

async def sort_clans_by_merit(client: coc.Client, clans_config: dict) -> dict:
    """Randomizes clan order. Logic implies merit-based sorting might be added later."""
    items = list(clans_config.items())
    random.shuffle(items)
    return dict(items)

def sort_clans_by_th(clans: dict) -> dict:
    """Sorts a dictionary of clans based on their Town Hall requirement (Descending)."""
    return dict(
        sorted(clans.items(), key=lambda x: int(x[1]["requirement"].replace("TH", "").replace("+", "")), reverse=True))


def get_member_allowed_accounts(member: ipy.Member) -> int:
    """
    Determines how many accounts a user can link based on their roles (Boosters/VIPs).
    Note: Contains hardcoded role IDs for legacy/specific server support.
    """
    # Note: These are legacy IDs for Boosters/VIPs. 
    # If these are not in server_configs.json, they remain hardcoded for now.
    user_roles = {int(role.id) for role in member.roles}
    if 1113877724675715203 in user_roles:
        return 2

    if {1113878840880660550, 1113880338796650496}.intersection(user_roles):
        return 3

    return 1


def list_difference(list1: list, list2: list) -> list:
    """Returns elements in list2 that are not in list1, handling duplicates."""
    diff = []
    for item in list2:
        if item not in list1 or list2.count(item) > list1.count(item):
            diff.append(item)
    return diff


def custom_dict_to_list(input_dict: dict) -> list:
    """
    Expands a dictionary {item: count} into a list [item, item, ...].
    """
    result_list = []
    for key, value in input_dict.items():
        result_list.extend([key] * value)

    return result_list


def has_roles(*role_keys):
    """
    Decorator for checking if a user has specific roles defined in server_setup.
    Allows for dynamic role checking based on configuration keys.
    """
    async def check(ctx):
        config = sc.get_config(ctx.guild_id)
        allowed_ids = []
        for key in role_keys:
            role_id = getattr(config, key, None)
            if role_id:
                allowed_ids.append(role_id)
        
        if not allowed_ids:
            return False
        return any(int(role.id) in allowed_ids for role in ctx.author.roles)
    return ipy.check(check)