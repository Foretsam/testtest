"""
Server Configuration Manager.

This module manages dynamic server settings, allowing the bot to be adaptable without
hardcoding role IDs or channel categories. It serves as the single source of truth for:
1.  **Configuration Loading:** Reads from `data/server_configs.json`.
2.  **Access Abstraction:** The `GuildConfig` class provides property-based access to settings,
    handling fallbacks and type conversion (e.g., ensuring IDs are integers).
3.  **Setup Commands:** Provides Slash Commands (`/setup_server_*`) for admins to configure the bot
    directly within Discord, updating the JSON file in real-time.

Key Components:
-   `APPLY_DATA`: Definitions for application types (prefixes, categories, messages).
-   `GuildConfig`: The primary interface for other extensions to retrieve settings.
-   `Setup` (Extension): Handles the admin commands to modify the configuration.

Dependencies:
    - interactions (Discord interactions)
    - json (Configuration persistence)
    - os (File path verification)
"""

import interactions as ipy
import json
import os

# --- Configuration Constants ---
CONFIG_FILE = 'data/server_configs.json'

# --- Default Fallback Images ---
# These URLs are used if specific images haven't been configured by the admin.
DEFAULT_IMAGES = {
    "BANNER_URL": "https://cdn.discordapp.com/attachments/1410359521636909098/1410359919286161620/AFO_-_WELCOME_Channel.png?ex=68b0bb87&is=68af6a07&hm=e8f20ad16e7247f62bd5a03844fc525d7b89dd40e14f5d8824e48b308f18de0c&",
    "CLAN_BANNER_URL": "https://cdn.discordapp.com/attachments/1410359521636909098/1410360141966086256/AFO_-_CLAN_Apply_Channel.png?ex=68b0bbbd&is=68af6a3d&hm=ee9598ec8f7f6f0c492eac4a3ae4db934c96d855c4fca247fd931d79c9c26339&",
    "PARTNER_BANNER_URL": "https://cdn.discordapp.com/attachments/1410359521636909098/1410360368865214656/AFO_-_PARTNER_Apply_Channel.png?ex=68b0bbf3&is=68af6a73&hm=211c572ba6061125ed412f8d94f5f7c85f913a1052e6cecf77a9849cdf0b2115&",
    "CHAMPIONS_BANNER_URL": "https://cdn.discordapp.com/attachments/1410359521636909098/1410360524079632466/AFO_-_CHAMPIONS_Apply_Channel.png?ex=68b0bc18&is=68af6a98&hm=b41797320e45e657ffc60b3995131d461048751137e0ef09cb37b397d7f7ab22&",
    "COACHING_BANNER_URL": "https://cdn.discordapp.com/attachments/1410359521636909098/1410360948178292826/AFO_-_COACHING_Channel.png?ex=68b0bc7d&is=68af6afd&hm=226932206c671e782b6659c57706dd3ce5d4d2b68b9118acaf6f3e8114958790&",
    "SUPPORT_BANNER_URL": "https://cdn.discordapp.com/attachments/1410359521636909098/1410361966836322575/AFO_-_AFO_SUPPORT_Channel.png?ex=68b0bd70&is=68af6bf0&hm=ce07856b0f94b4df069d05620cd29192592665b732a8a673eceaeeb1e757c0b9&",
    "STAFF_BANNER_URL": "https://cdn.discordapp.com/attachments/1410359521636909098/1410360262598328461/AFO_-_STAFF_Apply_Channel.png?ex=68b0bbd9&is=68af6a59&hm=650d0d76d11e25af11754c46da4cab2517ce7a4944fc8aa6c56bd60c46c9f07e&",
    "FWA_BANNER_URL": "https://cdn.discordapp.com/attachments/1410359521636909098/1410360674256814101/AFO_-_FWA_Apply_Channel.png?ex=68b0bc3b&is=68af6abb&hm=6663cf5ce43d2f1f4744aa327ef9fd5acffc44ca22b129dd11e2efe109f7e88d&",
    "LINE_URL": "https://cdn.discordapp.com/attachments/881073424884199435/1069179365302227075/animated-line-image-0379.gif?ex=67613ce1&is=675feb61&hm=e63343839bc38e500aabe5950d4c2e040ce003bedbc4c285fcab60cf3c83e0f1&",
    "FAMILY_ICON_URL": "https://cdn.discordapp.com/attachments/881073424884199435/890287615968948244/699834141931339777.png?ex=6761b3f4&is=67606274&hm=1fc7a58d38acff631aacb76f7266a28564fe94a3b7fbdb7c8e8a4d2aebc76f91&"
}

# ==============================
# APPLICATION CONFIGURATION
# ==============================
# Maps application types to their required resources.
# Used by `cogs/general/tickets.py` to create channels and embeds.
APPLY_DATA = {
    "clan": {
        "categories": ["CLAN_TICKETS_CATEGORY", "AFTER_CWL_CATEGORY"],
        "prefix": "𝐓𝐁𝐃",
        "msg": "Click the button `Start Application`"
    },
    "fwa": {
        "categories": ["FWA_TICKETS_CATEGORY", "AFTER_CWL_CATEGORY"],
        "prefix": "𝐅𝐖𝐀",
        "msg": "Click the button `Start Application`"
    },
    "staff": {
        "categories": ["STAFF_APPLY_CATEGORY", "STAFF_TRIALS_CATEGORY"],
        "prefix": "𝐒𝐓𝐅",
        "emoji": "👨‍💼",
        "msg": "Use the select menu below"
    },
    "champions": {
        "categories": ["CHAMPIONS_TRIALS_CATEGORY"],
        "prefix": "𝐂𝐓",
        "emoji": "👑",
        "msg": "Click the button `Start Application`"
    },
    "coaching": {
        "categories": ["COACHING_SESSIONS_CATEGORY"],
        "prefix": "𝐂𝐒",
        "emoji": "🔥",
        "msg": "Click the button `Start Application`"
    },
    "support": {
        "categories": ["SUPPORT_TICKETS_CATEGORY"],
        "prefix": "𝐒𝐓",
        "emoji": "🔐",
        "msg": "Please state the reason of the ticket below."
    },
    "partner": {
        "categories": ["PARTNER_TICKETS_CATEGORY"],
        "prefix": "𝐏𝐓𝐑",
        "emoji": "💼",
        "msg": "Please state the reason of the ticket below."
    },
}

# --- Helper Functions ---
def load_config():
    """Reads the JSON configuration file."""
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def save_config(data):
    """Writes data to the JSON configuration file."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def update_server_config_bulk(guild_id, category, updates):
    """
    Updates multiple settings within a specific configuration category.
    
    Args:
        guild_id (int): The ID of the guild being configured.
        category (str): The section key (e.g., 'roles', 'channels', 'images').
        updates (dict): Key-value pairs of settings to update.
    """
    data = load_config()
    guild_id = str(guild_id)

    # Initialize structure if missing
    if guild_id not in data:
        data[guild_id] = {"roles": {}, "channels": {}, "categories": {}, "ids": {}, "images": {}}

    if category not in data[guild_id]:
        data[guild_id][category] = {}

    changes_made = 0
    for key, value in updates.items():
        data[guild_id][category][key] = value
        changes_made += 1

    if changes_made > 0:
        save_config(data)
    
    return changes_made

class GuildConfig:
    """
    Interface for accessing guild-specific configuration.
    Wraps the raw dictionary data with properties for cleaner access code.
    """
    def __init__(self, guild_id: int):
        self.guild_id = str(guild_id)
        self._data = load_config().get(self.guild_id, {})

        # Sub-dictionaries for organized storage
        self.roles = self._data.get("roles", {})
        self.categories = self._data.get("categories", {})
        self.channels = self._data.get("channels", {})
        self.ids = self._data.get("ids", {})
        self.images = self._data.get("images", {})

    # ===== IDS & LINKS =====
    @property
    def STAFF_GUILD_ID(self):
        val = self.ids.get("STAFF_GUILD_ID")
        return int(val) if val else None

    @property
    def STAFF_SERVER_URL(self):
        return self.ids.get("STAFF_SERVER_URL")

    # ===== IMAGES (Properties with defaults) =====
    @property
    def BANNER_URL(self): return self.images.get("BANNER_URL", DEFAULT_IMAGES["BANNER_URL"])
    @property
    def CLAN_BANNER_URL(self): return self.images.get("CLAN_BANNER_URL", DEFAULT_IMAGES["CLAN_BANNER_URL"])
    @property
    def STAFF_BANNER_URL(self): return self.images.get("STAFF_BANNER_URL", DEFAULT_IMAGES["STAFF_BANNER_URL"])
    @property
    def FWA_BANNER_URL(self): return self.images.get("FWA_BANNER_URL", DEFAULT_IMAGES["FWA_BANNER_URL"])
    @property
    def CHAMPIONS_BANNER_URL(self): return self.images.get("CHAMPIONS_BANNER_URL", DEFAULT_IMAGES["CHAMPIONS_BANNER_URL"])
    @property
    def COACHING_BANNER_URL(self): return self.images.get("COACHING_BANNER_URL", DEFAULT_IMAGES["COACHING_BANNER_URL"])
    @property
    def SUPPORT_BANNER_URL(self): return self.images.get("SUPPORT_BANNER_URL", DEFAULT_IMAGES["SUPPORT_BANNER_URL"])
    @property
    def PARTNER_BANNER_URL(self): return self.images.get("PARTNER_BANNER_URL", DEFAULT_IMAGES["PARTNER_BANNER_URL"])
    @property
    def LINE_URL(self): return self.images.get("LINE_URL", DEFAULT_IMAGES["LINE_URL"])
    @property
    def FAMILY_ICON_URL(self): return self.images.get("FAMILY_ICON_URL", DEFAULT_IMAGES["FAMILY_ICON_URL"])

    # ===== ROLES (Returns ID or None) =====
    @property
    def VISITOR_ROLE(self): return self.roles.get("VISITOR_ROLE")
    @property
    def FAMILY_ROLE(self): return self.roles.get("FAMILY_ROLE")
    @property
    def FWA_MEMBER_ROLE(self): return self.roles.get("FWA_MEMBER_ROLE")
    @property
    def MODERATOR_ROLE(self): return self.roles.get("MODERATOR_ROLE")
    @property
    def SERVER_DEVELOPMENT_ROLE(self): return self.roles.get("SERVER_DEVELOPMENT_ROLE")
    @property
    def LEADER_ROLE(self): return self.roles.get("LEADER_ROLE")
    @property
    def RECRUITMENT_ROLE(self): return self.roles.get("RECRUITMENT_ROLE")
    @property
    def FWA_REP_ROLE(self): return self.roles.get("FWA_REP_ROLE")
    @property
    def COACH_ROLE(self): return self.roles.get("COACH_ROLE")
    @property
    def ADMINISTRATION_ROLE(self): return self.roles.get("ADMINISTRATION_ROLE")
    @property
    def CHAMPIONS_TESTER_ROLE(self): return self.roles.get("CHAMPIONS_TESTER_ROLE")

    def TH_ROLE(self, level: int):
        """Retrieves the role ID for a specific Town Hall level."""
        return self.roles.get(f"TOWNHALL_ROLES:{level}")

    # ===== CATEGORIES (Channel IDs) =====
    @property
    def CLAN_TICKETS_CATEGORY(self): return self.categories.get("CLAN_TICKETS_CATEGORY")
    @property
    def AFTER_CWL_CATEGORY(self): return self.categories.get("AFTER_CWL_CATEGORY")
    @property
    def STAFF_APPLY_CATEGORY(self): return self.categories.get("STAFF_APPLY_CATEGORY")
    @property
    def STAFF_TRIALS_CATEGORY(self): return self.categories.get("STAFF_TRIALS_CATEGORY")
    @property
    def FWA_TICKETS_CATEGORY(self): return self.categories.get("FWA_TICKETS_CATEGORY")
    @property
    def CHAMPIONS_TRIALS_CATEGORY(self): return self.categories.get("CHAMPIONS_TRIALS_CATEGORY")
    @property
    def COACHING_SESSIONS_CATEGORY(self): return self.categories.get("COACHING_SESSIONS_CATEGORY")
    @property
    def CHAMPIONS_TRIALS_FINISHED_CATEGORY(self): return self.categories.get("CHAMPIONS_TRIALS_FINISHED_CATEGORY")
    @property
    def SUPPORT_TICKETS_CATEGORY(self): return self.categories.get("SUPPORT_TICKETS_CATEGORY")
    @property
    def PARTNER_TICKETS_CATEGORY(self): return self.categories.get("PARTNER_TICKETS_CATEGORY")

def get_config(guild_id: int) -> GuildConfig:
    """Factory function to get a config instance for a guild."""
    return GuildConfig(guild_id)

# --- The Extension / Cog ---
class Setup(ipy.Extension):
    """
    Extension housing the administrative slash commands for bot configuration.
    """
    def __init__(self, bot):
        self.bot = bot

    async def process_setup(self, ctx, category_name, key_map, kwargs):
        """
        Generic processor for setup commands.
        Maps slash command arguments to JSON config keys and saves the data.
        """
        updates = {}
        response_lines = []

        for arg_name, value in kwargs.items():
            if value is not None and arg_name in key_map:
                json_key = key_map[arg_name]
                
                # Convert Discord objects to their storable IDs/URLs
                if isinstance(value, (ipy.Role, ipy.BaseChannel)):
                    updates[json_key] = value.id
                    response_lines.append(f"✅ Set **{json_key}** to {value.mention}")
                elif isinstance(value, ipy.Attachment):
                    updates[json_key] = value.url
                    response_lines.append(f"✅ Set **{json_key}** to [Link]({value.url})")
                else:
                    updates[json_key] = value
                    response_lines.append(f"✅ Set **{json_key}** to `{value}`")

        if not updates:
            await ctx.send(f"⚠ You didn't select any {category_name} to update.", ephemeral=True)
            return

        update_server_config_bulk(ctx.guild.id, category_name, updates)
        
        await ctx.send(f"**Updated {category_name.capitalize()}:**\n" + "\n".join(response_lines), ephemeral=True)

    # ==========================================
    # COMMAND 1: SETUP ROLES
    # ==========================================
    @ipy.slash_command(
        name="setup_server_roles", 
        description="Configure Server Roles",
        default_member_permissions=ipy.Permissions.ADMINISTRATOR # Secured: Only Admins
    )
    @ipy.slash_option(name="visitor", description="Visitor Role", opt_type=ipy.OptionType.ROLE, required=False)
    @ipy.slash_option(name="family", description="Family Member Role", opt_type=ipy.OptionType.ROLE, required=False)
    @ipy.slash_option(name="fwa_member", description="FWA Member Role", opt_type=ipy.OptionType.ROLE, required=False)
    @ipy.slash_option(name="moderator", description="Moderator Role", opt_type=ipy.OptionType.ROLE, required=False)
    @ipy.slash_option(name="developer", description="Developer Role", opt_type=ipy.OptionType.ROLE, required=False)
    @ipy.slash_option(name="leader", description="Leader Role", opt_type=ipy.OptionType.ROLE, required=False)
    @ipy.slash_option(name="recruiter", description="Recruitment Role", opt_type=ipy.OptionType.ROLE, required=False)
    @ipy.slash_option(name="fwa_rep", description="FWA Rep Role", opt_type=ipy.OptionType.ROLE, required=False)
    @ipy.slash_option(name="coach", description="Coach Role", opt_type=ipy.OptionType.ROLE, required=False)
    @ipy.slash_option(name="admin", description="Admin Role", opt_type=ipy.OptionType.ROLE, required=False)
    @ipy.slash_option(name="champ_tester", description="Champions Tester Role", opt_type=ipy.OptionType.ROLE, required=False)
    @ipy.slash_option(name="th11", description="Town Hall 11 Role", opt_type=ipy.OptionType.ROLE, required=False)
    @ipy.slash_option(name="th12", description="Town Hall 12 Role", opt_type=ipy.OptionType.ROLE, required=False)
    @ipy.slash_option(name="th13", description="Town Hall 13 Role", opt_type=ipy.OptionType.ROLE, required=False)
    @ipy.slash_option(name="th14", description="Town Hall 14 Role", opt_type=ipy.OptionType.ROLE, required=False)
    @ipy.slash_option(name="th15", description="Town Hall 15 Role", opt_type=ipy.OptionType.ROLE, required=False)
    @ipy.slash_option(name="th16", description="Town Hall 16 Role", opt_type=ipy.OptionType.ROLE, required=False)
    @ipy.slash_option(name="th17", description="Town Hall 17 Role", opt_type=ipy.OptionType.ROLE, required=False)
    @ipy.slash_option(name="th18", description="Town Hall 18 Role", opt_type=ipy.OptionType.ROLE, required=False)
    async def setup_roles_cmd(self, ctx: ipy.SlashContext, **kwargs):
        """Command to update role ID mappings."""
        key_map = {
            "visitor": "VISITOR_ROLE", "family": "FAMILY_ROLE", "fwa_member": "FWA_MEMBER_ROLE",
            "moderator": "MODERATOR_ROLE", "developer": "SERVER_DEVELOPMENT_ROLE", "leader": "LEADER_ROLE",
            "recruiter": "RECRUITMENT_ROLE", "fwa_rep": "FWA_REP_ROLE", "coach": "COACH_ROLE",
            "admin": "ADMINISTRATION_ROLE", "champ_tester": "CHAMPIONS_TESTER_ROLE",
            "th11": "TOWNHALL_ROLES:11", "th12": "TOWNHALL_ROLES:12", "th13": "TOWNHALL_ROLES:13",
            "th14": "TOWNHALL_ROLES:14", "th15": "TOWNHALL_ROLES:15", "th16": "TOWNHALL_ROLES:16",
            "th17": "TOWNHALL_ROLES:17", "th18": "TOWNHALL_ROLES:18"
        }
        await self.process_setup(ctx, "roles", key_map, kwargs)

    # ==========================================
    # COMMAND 2: SETUP CATEGORIES
    # ==========================================
    @ipy.slash_command(
        name="setup_server_categories", 
        description="Configure server categories",
        default_member_permissions=ipy.Permissions.ADMINISTRATOR # Secured: Only Admins
    )
    @ipy.slash_option(name="clan_tickets", description="Clan Tickets Category", opt_type=ipy.OptionType.CHANNEL, required=False)
    @ipy.slash_option(name="after_cwl", description="After CWL Category", opt_type=ipy.OptionType.CHANNEL, required=False)
    @ipy.slash_option(name="staff_apply", description="Staff Apply Category", opt_type=ipy.OptionType.CHANNEL, required=False)
    @ipy.slash_option(name="staff_trials", description="Staff Trials Category", opt_type=ipy.OptionType.CHANNEL, required=False)
    @ipy.slash_option(name="fwa_tickets", description="FWA Tickets Category", opt_type=ipy.OptionType.CHANNEL, required=False)
    @ipy.slash_option(name="champions_trials", description="Champions Trials Category", opt_type=ipy.OptionType.CHANNEL, required=False)
    @ipy.slash_option(name="coaching_sessions", description="Coaching Sessions Category", opt_type=ipy.OptionType.CHANNEL, required=False)
    @ipy.slash_option(name="after_champions", description="Finished Champions Trials Category", opt_type=ipy.OptionType.CHANNEL, required=False)
    @ipy.slash_option(name="support_tickets", description="Support Tickets Category", opt_type=ipy.OptionType.CHANNEL, required=False)
    @ipy.slash_option(name="partner_tickets", description="Partner Tickets Category", opt_type=ipy.OptionType.CHANNEL, required=False)
    async def setup_categories_cmd(self, ctx: ipy.SlashContext, **kwargs):
        """Command to update ticket category ID mappings."""
        key_map = {
            "clan_tickets": "CLAN_TICKETS_CATEGORY", "after_cwl": "AFTER_CWL_CATEGORY",
            "staff_apply": "STAFF_APPLY_CATEGORY", "staff_trials": "STAFF_TRIALS_CATEGORY",
            "fwa_tickets": "FWA_TICKETS_CATEGORY", "champions_trials": "CHAMPIONS_TRIALS_CATEGORY",
            "coaching_sessions": "COACHING_SESSIONS_CATEGORY", "after_champions": "CHAMPIONS_TRIALS_FINISHED_CATEGORY",
            "support_tickets": "SUPPORT_TICKETS_CATEGORY", "partner_tickets": "PARTNER_TICKETS_CATEGORY"
        }
        await self.process_setup(ctx, "categories", key_map, kwargs)

    # ==========================================
    # COMMAND 3: SETUP IDS & CONFIG
    # ==========================================
    @ipy.slash_command(
        name="setup_server_config", 
        description="Configure miscellaneous server IDs and Links",
        default_member_permissions=ipy.Permissions.ADMINISTRATOR # Secured: Only Admins
    )
    @ipy.slash_option(name="staff_guild_id", description="The ID of the Staff Server", opt_type=ipy.OptionType.STRING, required=False)
    @ipy.slash_option(name="staff_server_url", description="The Invite Link to the Staff Server", opt_type=ipy.OptionType.STRING, required=False)
    async def setup_config_cmd(self, ctx: ipy.SlashContext, **kwargs):
        """Command to update miscellaneous server IDs."""
        key_map = {
            "staff_guild_id": "STAFF_GUILD_ID",
            "staff_server_url": "STAFF_SERVER_URL"
        }
        await self.process_setup(ctx, "ids", key_map, kwargs)

    # ==========================================
    # COMMAND 4: SETUP IMAGES
    # ==========================================
    @ipy.slash_command(
        name="setup_server_images", 
        description="Configure server images/banners",
        default_member_permissions=ipy.Permissions.ADMINISTRATOR # Secured: Only Admins
    )
    @ipy.slash_option(name="welcome_banner", description="Main Welcome Banner", opt_type=ipy.OptionType.ATTACHMENT, required=False)
    @ipy.slash_option(name="clan_banner", description="Clan Application Banner", opt_type=ipy.OptionType.ATTACHMENT, required=False)
    @ipy.slash_option(name="staff_banner", description="Staff Application Banner", opt_type=ipy.OptionType.ATTACHMENT, required=False)
    @ipy.slash_option(name="partner_banner", description="Partner Application Banner", opt_type=ipy.OptionType.ATTACHMENT, required=False)
    @ipy.slash_option(name="fwa_banner", description="FWA Application Banner", opt_type=ipy.OptionType.ATTACHMENT, required=False)
    @ipy.slash_option(name="champions_banner", description="Champions Application Banner", opt_type=ipy.OptionType.ATTACHMENT, required=False)
    @ipy.slash_option(name="coaching_banner", description="Coaching Application Banner", opt_type=ipy.OptionType.ATTACHMENT, required=False)
    @ipy.slash_option(name="support_banner", description="Support Application Banner", opt_type=ipy.OptionType.ATTACHMENT, required=False)
    @ipy.slash_option(name="line_separator", description="Line Separator GIF", opt_type=ipy.OptionType.ATTACHMENT, required=False)
    @ipy.slash_option(name="family_icon", description="Family Icon URL (Upload Image)", opt_type=ipy.OptionType.ATTACHMENT, required=False)
    async def setup_images_cmd(self, ctx: ipy.SlashContext, **kwargs):
        """Command to update image URLs used in embeds."""
        key_map = {
            "welcome_banner": "BANNER_URL",
            "clan_banner": "CLAN_BANNER_URL",
            "staff_banner": "STAFF_BANNER_URL",
            "partner_banner": "PARTNER_BANNER_URL",
            "fwa_banner": "FWA_BANNER_URL",
            "champions_banner": "CHAMPIONS_BANNER_URL",
            "coaching_banner": "COACHING_BANNER_URL",
            "support_banner": "SUPPORT_BANNER_URL",
            "line_separator": "LINE_URL",
            "family_icon": "FAMILY_ICON_URL"
        }
        await self.process_setup(ctx, "images", key_map, kwargs)

def setup(bot):
    """Entry point for loading the extension."""
    Setup(bot)