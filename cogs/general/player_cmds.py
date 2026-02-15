"""
Player Management Commands Module.

This extension provides the interface for connecting Discord users to their Clash of Clans
accounts. It serves as the primary bridge between the two platforms.

Key Features:
1.  **Identity Management (Whois):** Allows users to look up the in-game accounts linked to any Discord member,
    displaying detailed stats (Heroes, Pets, War Stars, Donation ratios).
2.  **Account Linking/Unlinking:** Manages the persistent association between Discord IDs and Clash Player Tags
    stored in `data/member_tags.json`.
3.  **Automated Verification:** A critical system that:
    - Scans a user's linked accounts.
    - Verifies their membership in alliance clans.
    - Automatically updates their Discord Nickname to match standard formatting (Name | Clan).
    - Synchronizes Discord roles (Town Hall levels, Clan Member roles, Visitor status).
    - Handles "on-boarding" logic for new members in interview tickets (Welcome messages, Webhooks).

Dependencies:
    - interactions (Discord interactions)
    - coc (Clash of Clans API wrapper)
    - core (Internal utilities, models, and emoji management)
"""

import interactions as ipy
import json
import copy
import asyncio
import coc
import random
import emoji

# Explicit imports to maintain code clarity
from core.utils import *
from core.models import *
from core.emojis_manager import *
from core import server_setup as sc

class PlayerCmds(ipy.Extension):
    """
    Extension class housing slash commands and context menus for player management.
    """

    def __init__(self, bot: ipy.Client):
        self.bot = bot

    @ipy.slash_command(name="player", description="Player utility for All For One family")
    async def player_base(self, ctx: ipy.SlashContext):
        """Base command group for player utilities."""
        pass

    @player_base.subcommand(sub_cmd_name="whois", sub_cmd_description="Check the Clash of Clans accounts linked to a user")
    @ipy.slash_option(
        name="user",
        description="Choose a user from this server",
        opt_type=ipy.OptionType.USER,
        required=True
    )
    @ipy.slash_option(
        name="hidden",
        description="Make the message hidden?",
        opt_type=ipy.OptionType.BOOLEAN
    )
    async def player_whois(self, ctx: ipy.SlashContext, user: ipy.Member, hidden: bool = True):
        """
        Retrieves and displays detailed information about a Discord user's linked Clash of Clans accounts.
        
        This command fetches fresh data from the CoC API for every linked tag. 
        It supports pagination (via a dropdown menu) if the user has multiple accounts linked.
        """
        await ctx.defer(ephemeral=True if hidden else False)

        player_links = json.load(open("data/member_tags.json", "r"))

        # Validation: User existence check
        if isinstance(user, str):
            await ctx.send(
                f"{get_app_emoji('error')} Cannot get this user object. The user does not share any server with the bot.",
                ephemeral=True)
            return

        # Validation: Link existence check
        if not player_links.get(str(user.id)):
            await ctx.send(f"{get_app_emoji('error')} No account is linked to this user!", ephemeral=True)
            return

        player_profiles = []
        player_options = []
        count = 0
        player_summary = ""

        # Iterate through all tags linked to the user
        # We use a deepcopy to safely iterate while potentially modifying the source list (removing invalid tags)
        for tag in copy.deepcopy(player_links[str(user.id)]):
            try:
                player = await fetch_player(self.bot.coc, tag)
            except coc.errors.NotFound:
                # Cleanup: Automatically remove tags that no longer exist in the API
                player_links[str(user.id)].remove(tag)
                continue

            count += 1
            
            # --- Data Formatting Section ---
            townhall = f"{get_app_emoji(f'Townhall{player.town_hall}')}`{player.town_hall}`"

            # Format Pets (Only relevant for TH14+)
            pets = ""
            if player.town_hall >= 14:
                pet_count = 0
                for pet in player.pets:
                    pet_count += 1
                    if pet_count == 5:
                        pets += "\n" # formatting line break for visual aesthetics
                    
                    clean_pet_name = pet.name.replace(".", "").replace(" ", "")
                    pets += f"{get_app_emoji(clean_pet_name)}`{pet.level}`"

            war = f"{get_app_emoji('coc_star')}`{player.war_stars}`"

            # Format Heroes with shorthand names (BK, AQ, GW, RC)
            heroes = ""
            hsum = 0
            hero_name_map = {
                "Barbarian King": "BK", 
                "Archer Queen": "AQ", 
                "Grand Warden": "GW", 
                "Royal Champion": "RC", 
                "Minion Prince": "MP"
            }

            for scan in player.heroes:
                if scan.is_home_base:
                    short_name = hero_name_map.get(scan.name, scan.name.replace(" ", ""))
                    heroes += f"{get_app_emoji(short_name)}`{scan.level}`"
                    hsum += scan.level

            # External Links Generation
            click_emoji = get_app_emoji('click')
            # Sanitize name for URL (ClashOfStats format)
            clean_name_url = "".join(i for i in player.name if not emoji.is_emoji(i))
            link = f"https://www.clashofstats.com/players/{clean_name_url}-{player.tag.replace('#', '')}/summary/"
            
            xplvl = f"{get_app_emoji('experience')}{player.exp_level}"

            # Build Embed Fields
            fields = [
                ipy.EmbedField(
                    name=f"**General Information**",
                    value=f"**Townhall:**\n{townhall}\n"
                        f"**Experience:**\n{xplvl}\n"
                        f"**War Stars:**\n{war}\n",
                    inline=False)
            ]

            progress_value = ""
            if heroes: progress_value += f"**Heroes:**\n{heroes}\n"
            if pets: progress_value += f"**Pets:**\n{pets}\n"

            fields.append(
                ipy.EmbedField(
                    name=f"**Progress Information**",
                    value=progress_value,
                    inline=False
                )
            )

            townhall_emoji = ipy.PartialEmoji.from_str(get_app_emoji(f"Townhall{player.town_hall}"))

            # Logic for Clan Status (In Clan vs No Clan)
            if not player.clan:
                fields.append(
                    ipy.EmbedField(
                        name="**Season Information**",
                        value=f"**Donations:**\n{get_app_emoji('donated')}`{player.donations}` {get_app_emoji('received')}`{player.received}`\n"
                            f"**Multiplayer:**\n{get_app_emoji('attack')}`{player.attack_wins}` {get_app_emoji('defense')}`{player.defense_wins}`\n"
                            f"**Clan:**\n{get_app_emoji('clan_logo')} Not in a clan",
                        inline=False)
                )
                player_option = ipy.StringSelectOption(label=f"{player.name} ({player.tag})",
                                                    value=str(count),
                                                    description=f"Not in a clan",
                                                    emoji=townhall_emoji)

                player_summary += f"{townhall_emoji} [{player.name} ({player.tag})]({player.share_link})\n"
                if heroes: player_summary += f"{heroes}\n"
                player_summary += f"Not in a clan\n\n"

            else:
                fields.append(
                    ipy.EmbedField(
                        name="**Season Information**",
                        value=f"**Donations:**\n{get_app_emoji('donated')}{player.donations} {get_app_emoji('received')}{player.received}\n"
                            f"**Attacks&Defenses:**\n{get_app_emoji('attack')}{player.attack_wins} {get_app_emoji('defense')}{player.defense_wins}\n"
                            f"**Clan:**\n{get_app_emoji('clan_logo')}[{player.clan}]({player.clan.share_link}) ({player.role})",
                        inline=False)
                )
                player_option = ipy.StringSelectOption(label=f"{player.name} ({player.tag})",
                                                    value=str(count),
                                                    description=f"{player.role} of {player.clan}",
                                                    emoji=townhall_emoji)

                player_summary += f"{townhall_emoji} [{player.name} ({player.tag})]({player.share_link})\n"
                if heroes: player_summary += f"{heroes}\n"
                player_summary += f"{player.role} of {player.clan}\n\n"

            player_options.append(player_option)

            # Create individual profile embed for this account
            embed = ipy.Embed(
                title=f"**{player.name}** `{player.tag}`",
                description=f"{click_emoji} [Clash of Stats Profile]({link})\n"
                            f"{click_emoji} [In Game Profile]({player.share_link})",
                fields=fields,
                author=ipy.EmbedAuthor(
                    name=f"{user.username}",
                    icon_url=user.avatar.url
                ),
                footer=ipy.EmbedFooter(
                    text=f"Requested by {ctx.author.username}",
                    icon_url=ctx.author.avatar.url
                ),
                timestamp=ipy.Timestamp.utcnow(),
                color=COLOR
            )
            player_profiles.append(embed)

        # Update JSON if any stale tags were removed
        with open("data/member_tags.json", "w") as file:
            json.dump(player_links, file, indent=4)

        # Construct the "Main Menu" embed (Summary of all accounts)
        footer = ipy.EmbedFooter(
            text=f"{count} account linked in total!" if count == 1 else f"{count} accounts linked in total!"
        )

        embed = ipy.Embed(
            title=f"**Player Summary**",
            description=player_summary,
            author=ipy.EmbedAuthor(
                name=f"{user.username}",
                icon_url=user.avatar.url
            ),
            footer=footer,
            color=COLOR,
        )

        # Option to return to summary view
        player_option = ipy.StringSelectOption(
            label=f"Player Summary",
            value="0",
            description=f"A summary showing all accounts linked to this user",
            emoji=ipy.PartialEmoji(name="📖")
        )

        player_options.append(player_option)
        player_profiles.append(embed)

        # UI Component: Dropdown to switch between profiles
        player_select = ipy.StringSelectMenu(
            *player_options,
            placeholder="👤 Select account profiles here",
            custom_id="account_select"
        )

        msg = await ctx.send(embeds=[embed], components=player_select)

        # Interaction Loop for dropdown navigation
        async def check(event: ipy.events.Component):
            if int(event.ctx.author.id) == int(ctx.author.id):
                return True
            await event.ctx.send(f"{get_app_emoji('error')} You cannot interact with other user's components.", ephemeral=True)
            return False

        while True:
            try:
                res: ipy.ComponentContext = (await self.bot.wait_for_component(components=player_select, check=check,
                                                                        messages=int(msg.id), timeout=180)).ctx
            except asyncio.TimeoutError:
                raise ComponentTimeoutError(message=msg)

            # Update message with the selected profile (Note: Logic assumes '0' is summary which is appended last in list)
            # Adjusting index logic based on code flow: Summary was appended LAST to `player_profiles`.
            # If value is '0', it refers to summary. Other values are 1-based index.
            # *Correction*: In this specific implementation, Summary was appended LAST to `player_profiles`.
            # The dropdown values are 1, 2... and then 0.
            # `player_profiles[int(res.values[0]) - 1]` suggests 1-based indexing for profiles.
            # If '0' is selected, index becomes -1, which is the last element (the summary). This logic is clever.
            await res.edit_origin(embeds=[player_profiles[int(res.values[0]) - 1]], components=player_select)

    @player_base.subcommand(sub_cmd_name="link", sub_cmd_description="Link Clash of Clans accounts to a user")
    @has_roles("RECRUITMENT_ROLE", "SERVER_DEVELOPMENT_ROLE", "LEADER_ROLE")
    @ipy.slash_option(
        name="user",
        description="Choose a user from this server",
        opt_type=ipy.OptionType.USER,
        required=True
    )
    @ipy.slash_option(
        name="player_tags",
        description="Separate the tags with a comma",
        opt_type=ipy.OptionType.STRING,
        required=True
    )
    async def player_link(self, ctx: ipy.SlashContext, user: ipy.Member, player_tags: str):
        """
        Manually links one or more Clash of Clans player tags to a Discord user.
        Restricted to specific staff roles.
        """
        await ctx.defer(ephemeral=True)

        player_links = json.load(open("data/member_tags.json", "r"))
        player_links_reversed = reverse_dict(player_links)

        # Parse and validate the provided tags via API
        valid_tags = await extract_tags(self.bot.coc, player_tags, context=ctx)

        if not valid_tags:
            # Error handling handled within extract_tags usually, or returns empty list
            return

        if isinstance(user, str):
            await ctx.send(
                f"{get_app_emoji('error')} Cannot get this user object. The user does not share any server with the bot.",
                ephemeral=True)
            return

        for tag in valid_tags:
            # Check 1: Already linked to this user
            if tag in player_links.get(str(user.id), []):
                await ctx.send(f"{get_app_emoji('error')} `{tag}` is already linked to this user.", ephemeral=True)
                continue

            # Check 2: Already linked to SOMEONE ELSE
            if tag in player_links_reversed:
                await ctx.send(f"{get_app_emoji('error')} `{tag}` is already linked to another user.", ephemeral=True)
                continue

            # Success: Link the tag
            player_links.setdefault(str(user.id), []).append(tag)
            await ctx.send(f"{get_app_emoji('success')} `{tag}` is successfully linked.", ephemeral=True)

        with open("data/member_tags.json", "w") as file:
            json.dump(player_links, file, indent=4)


    @ipy.message_context_menu(name="Link Accounts")
    @has_roles("RECRUITMENT_ROLE", "SERVER_DEVELOPMENT_ROLE", "LEADER_ROLE")
    async def Link_Accounts(self, ctx: ipy.ContextMenuContext):
        """
        Context Menu version of the link command. 
        Scans the selected message for player tags and links them to the message author.
        """
        await ctx.defer(ephemeral=True)

        # Fetch the message author as a Member object within the guild context
        user = await self.bot.fetch_member(ctx.target.author.id, ctx.guild_id, force=True)

        player_links = json.load(open("data/member_tags.json", "r"))
        player_links_reversed = reverse_dict(player_links)

        # Extract tags from message content
        valid_tags = await extract_tags(self.bot.coc, ctx.target.content, context=ctx)

        if not valid_tags:
            await ctx.send(f"{get_app_emoji('error')} No valid player tags found.", ephemeral=True)
            return

        if isinstance(user, str):
            await ctx.send(
                f"{get_app_emoji('error')} Cannot get this user object. The user does not share any server with the bot.",
                ephemeral=True)
            return

        for tag in valid_tags:
            if tag in player_links.get(str(user.id), []):
                await ctx.send(f"{get_app_emoji('error')} `{tag}` is already linked to this user.", ephemeral=True)
                continue

            if tag in player_links_reversed:
                await ctx.send(f"{get_app_emoji('error')} `{tag}` is already linked to another user.", ephemeral=True)
                continue

            player_links.setdefault(str(user.id), []).append(tag)
            await ctx.send(f"{get_app_emoji('success')} `{tag}` is successfully linked.", ephemeral=True)

        with open("data/member_tags.json", "w") as file:
            json.dump(player_links, file, indent=4)


    @player_base.subcommand(sub_cmd_name="unlink", sub_cmd_description="Unlink Clash of Clans accounts to a user")
    @has_roles("RECRUITMENT_ROLE", "SERVER_DEVELOPMENT_ROLE", "LEADER_ROLE")
    @ipy.slash_option(
        name="user",
        description="Choose a user from this server",
        opt_type=ipy.OptionType.USER,
        required=True
    )
    @ipy.slash_option(
        name="player_tag",
        description="Clash of Clans player tag",
        opt_type=ipy.OptionType.STRING,
        required=True,
        autocomplete=True
    )
    @ipy.slash_option(
        name="user_id",
        description="Type the user id, which will override the user selection.",
        opt_type=ipy.OptionType.STRING,
    )
    async def player_unlink(self, ctx: ipy.SlashContext, user: ipy.Member, player_tag: str, user_id: str = None):
        """
        Unlinks specific Clash of Clans accounts (or all) from a user.
        Supports unlinking via User object or direct User ID input.
        """
        await ctx.defer(ephemeral=True)

        player_links = json.load(open("data/member_tags.json", "r"))

        # Verify tag existence via API, unless "all" option is selected
        player = None
        try:
            player = await fetch_player(self.bot.coc, player_tag)
        except coc.errors.NotFound:
            if player_tag != "all":
                raise

        # Determine target user ID (Override logic)
        if not user_id:
            if isinstance(user, str):
                await ctx.send(f"{get_app_emoji('error')} Cannot get this user object, please try again using "
                            f"the option `user_id`.", ephemeral=True)
                return
            user_id = str(user.id)

        # Determine if unlinking specific tag or ALL tags
        tags = player_links[str(user_id)] if player_tag == "all" else [player.tag]
        
        for tag in tags:
            if tag not in player_links.get(str(user.id), []):
                await ctx.send(f"{get_app_emoji('error')} The account `{tag}` is not linked to the user.", ephemeral=True)
                continue

            player_links[str(user_id)].remove(tag)
            await ctx.send(f"{get_app_emoji('success')} `{tag}` is successfully removed.", ephemeral=True)

        with open("data/member_tags.json", "w") as file:
            json.dump(player_links, file, indent=4)


    @player_unlink.autocomplete(option_name="player_tag")
    async def player_tag_autocomplete(self, ctx: ipy.AutocompleteContext):
        """
        Autocomplete for unlinking. Suggests tags currently linked to the selected user.
        """
        if "user" not in ctx.kwargs and "user_id" not in ctx.kwargs:
            tag_choice = [{"name": "Please choose a user first", "value": "None"}]
            await ctx.send(tag_choice)
            return

        user_id = ctx.kwargs["user_id"] if "user_id" in ctx.kwargs else ctx.kwargs["user"]
        player_links = json.load(open("data/member_tags.json", "r"))

        if not player_links.get(user_id, []):
            tag_choice = [{"name": "No accounts linked to this player", "value": "None"}]
            await ctx.send(tag_choice)
            return

        tag_choices = []
        # Create choices for each linked tag
        for tag in copy.deepcopy(player_links[user_id]):
            try:
                player = await fetch_player(self.bot.coc, tag)
            except coc.errors.NotFound:
                player_links[ctx.kwargs["user"]].remove(tag)
                continue

            name = f"[TH{player.town_hall}] {player.name} ({player.tag})"
            tag_choices.append({"name": name, "value": tag})

        # Add the 'Delete All' option
        tag_choices.append({"name": "Unlink all accounts", "value": "all"})

        await ctx.send(tag_choices)

        # Persist cleanup of invalid tags if any occurred during loop
        with open("data/member_tags.json", "w") as file:
            json.dump(player_links, file, indent=4)


    @ipy.message_context_menu(name="Unlink Accounts")
    @has_roles("RECRUITMENT_ROLE", "SERVER_DEVELOPMENT_ROLE", "LEADER_ROLE")
    async def Unlink_Accounts(self, ctx: ipy.ContextMenuContext):
        """
        Context Menu version of unlink. 
        Scans message for tags and unlinks them from the author.
        """
        await ctx.defer(ephemeral=True)

        user = await self.bot.fetch_member(ctx.target.author.id, ctx.guild_id, force=True)
        player_links = json.load(open("data/member_tags.json", "r"))

        tags = await extract_tags(self.bot.coc, ctx.target.content, context=ctx)

        if not tags:
            await ctx.send(f"{get_app_emoji('error')} Please provide at least one valid player tag.", ephemeral=True)
            return

        for tag in tags:
            if tag not in player_links.get(str(user.id), []):
                await ctx.send(f"{get_app_emoji('error')} `{tag}` is not linked to this user.", ephemeral=True)
                continue

            player_links[str(user.id)].remove(tag)
            await ctx.send(f"{get_app_emoji('success')} `{tag}` is successfully removed.", ephemeral=True)

        with open("data/member_tags.json", "w") as file:
            json.dump(player_links, file, indent=4)


    @player_base.subcommand(sub_cmd_name="verify", sub_cmd_description="Set roles and edit nickname of a user")
    @has_roles("RECRUITMENT_ROLE", "SERVER_DEVELOPMENT_ROLE", "LEADER_ROLE")
    @ipy.cooldown(bucket=ipy.Buckets.USER, rate=1, interval=5)
    @ipy.slash_option(
        name="user",
        description="Choose a user from this server",
        opt_type=ipy.OptionType.USER,
        required=True
    )
    @ipy.slash_option(
        name="player_tags",
        description="Separate the tags with a comma",
        opt_type=ipy.OptionType.STRING,
    )
    @ipy.slash_option(
        name="player_nickname",
        description="Choose the nickname of the player",
        opt_type=ipy.OptionType.STRING,
        autocomplete=True
    )
    @ipy.slash_option(
        name="finish_interview",
        description="Interview process finished?",
        opt_type=ipy.OptionType.BOOLEAN,
    )
    async def player_verify(self, ctx: ipy.SlashContext, user: ipy.Member, player_tags: str = None, player_nickname: str = None,
                            finish_interview: bool = False):
        """
        The Master Verification Command.
        
        This command performs the following actions:
        1.  **Account Validation:** Verifies the tags provided (or linked tags if none provided).
        2.  **Role Synchronization:** Checks if the user's accounts are in alliance clans. 
            - If YES: Assigns Clan Role, Town Hall Role, and Family Role.
            - If NO: Assigns Visitor Role.
        3.  **Nickname Update:** Enforces standard nickname format (Name | Clan Name) or uses custom nickname if valid.
        4.  **Interview Completion (Optional):** If `finish_interview` is True:
            - Posts welcome messages via Webhook in the new clan's chat channel.
            - Posts final closure messages in the ticket.
        """
        await ctx.defer(ephemeral=True)

        player_links = json.load(open("data/member_tags.json", "r"))
        player_links_reversed = reverse_dict(player_links)

        try:
            member = await self.bot.fetch_member(user.id, ctx.guild_id, force=True)
        except ipy.errors.NotFound:
            await ctx.send(f"{get_app_emoji('error')} User is not in the server, cannot verify.")
            return

        if not member:
            await ctx.send(f"{get_app_emoji('error')} User is not in the server, cannot verify.")
            return

        clans_config: dict[str, AllianceClanData] = json.load(open("data/clans_config.json", "r"))
        member_roles = [int(role.id) for role in member.roles]
        # Identify all possible clan-related roles to potentially remove invalid ones
        clan_roles = set([clans_config[key]["role"] for key in clans_config.keys()])

        # --- Tag Resolution ---
        if not player_tags:
            # If no tags provided, look up linked tags
            if not player_links.get(str(member.id)):
                await ctx.send(f"{get_app_emoji('error')} No account linked to the player, must provide player tag.")
                return
            corrected_tags = player_links[str(member.id)]
        else:
            # If tags provided, parse and validate them
            corrected_tags = await extract_tags(self.bot.coc, player_tags, context=ctx)

        if not corrected_tags:
            return

        valid_tags = []
        valid_roles = []
        joined_clans = []
        player_townhalls = []
        
        config: sc.GuildConfig = sc.get_config(ctx.guild.id)

        # --- Account Analysis Loop ---
        for player_tag in corrected_tags:
            player = await fetch_player(self.bot.coc, player_tag, update=True)
            
            # Determine Town Hall Role
            th_role = config.TH_ROLE(player.town_hall)
            if th_role:
                player_townhalls.append(th_role)

            # Auto-link if not already linked
            if player_tag not in player_links_reversed:
                player_links.setdefault(str(member.id), []).append(player.tag)

            # Check if player is in a clan
            if not player.clan:
                await ctx.send(f"{get_app_emoji('error')} `{player.name} ({player.tag})` is not in any clan!",
                            ephemeral=True, delete_after=4)
                continue

            # Check if player is in an ALLIANCE clan
            if player.clan.tag not in clans_config.keys():
                await ctx.send(f"{get_app_emoji('error')} `{player.name} ({player.tag})` is not in any alliance clans!",
                            ephemeral=True, delete_after=4)
                continue

            # If verified as alliance member:
            joined_clans.append(player.clan.tag)
            valid_tags.append(player.tag)
            valid_roles.append(clans_config[player.clan.tag]["role"])

        # Save any auto-links created
        with open("data/member_tags.json", "w") as file:
            json.dump(player_links, file, indent=4)
        
        valid_roles += player_townhalls
        
        # Calculate roles to remove (old clan roles that are no longer valid)
        invalid_roles = list(set(member_roles).intersection(clan_roles) - set(valid_roles))

        # --- Role & Nickname Application ---
        if valid_tags:
            # Player IS in the alliance
            player = await fetch_player(self.bot.coc, valid_tags[0], update=True)
            clan_tag = player.clan.tag

            if clans_config[clan_tag]['type'] == "FWA":
                if config.FWA_MEMBER_ROLE:
                    valid_roles.append(config.FWA_MEMBER_ROLE)
            
            if config.FAMILY_ROLE:
                valid_roles.append(config.FAMILY_ROLE)

            # Default Nickname: "Name | Clan Name"
            new_name = f"{player.name} | {player.clan.name}"[:32]

            await ctx.send(
                f"{get_app_emoji('success')} The player's account(s) that are part of *All For One* is/are successfully verified, "
                f"and all roles are set!",
                ephemeral=True)
        else:
            # Player is NOT in the alliance -> Visitor
            if config.VISITOR_ROLE:
                valid_roles.append(config.VISITOR_ROLE)
            
            # Remove Family/FWA roles if they are being demoted to visitor
            if config.FAMILY_ROLE:
                invalid_roles.append(config.FAMILY_ROLE)
            if config.FWA_MEMBER_ROLE:
                invalid_roles.append(config.FWA_MEMBER_ROLE)

            player = await fetch_player(self.bot.coc, corrected_tags[0], update=True)
            new_name = f"{player.name} | Visitor"[:32]

            await ctx.send(f"{get_app_emoji('error')} The player's account(s) is/are not part of *All For One*!", ephemeral=True)    

        # Override name if custom one provided
        new_name = player_nickname if player_nickname else new_name

        # Execute Discord changes
        await member.add_roles(valid_roles, reason=f"{ctx.author} {ctx.author.id} used /player verify")

        try:
            await member.remove_roles(invalid_roles, reason=f"{ctx.author} {ctx.author.id} used /player verify")
            if ctx.author.top_role.position > member.top_role.position:
                await member.edit(nickname=new_name, reason=f"{ctx.author} {ctx.author.id} used /player verify")
        except (ipy.errors.HTTPException, ipy.errors.Forbidden):
            # Ignore permission errors if bot cannot edit nickname (e.g. Server Owner)
            pass

        # --- Interview Finishing Logic ---
        if not finish_interview:
            return
        
        # Security: Ensure this is only run in interview channels
        if int(ctx.channel.parent_id) not in [config.CLAN_TICKETS_CATEGORY, config.AFTER_CWL_CATEGORY, config.FWA_TICKETS_CATEGORY]:
            await ctx.send(f"{get_app_emoji('error')} The finishing interview function can only be used in an interview channel.")
            return

        if not joined_clans:
            return

        webhook_name = ctx.author.nick if ctx.author.nick else ctx.author.user.username

        joined_clans = list(dict.fromkeys(joined_clans)) # Deduplicate clans
        
        # Post Welcome Messages in the Clan's Chat Channel via Webhook
        for clan_tag in joined_clans:
            greeting_options = ["Welcome to ", "Thanks for joining ", "Glad to see you in ", "Glad that you chose ",
                                "Is an honor that you chose ", "Hope you enjoy your stay in "]
            welcome_message = f"{member.mention} {random.choice(greeting_options)}{clans_config[clan_tag]['name']}!"
            chat_instructions = [
                "In this channel, you can chat with your clan mates and ask questions.",
                "Feel free to chat here and ask questions.",
                "This is the chat channel for the clan, you can chat and ask questions here.",
                "If you have questions, just ask here!"
            ]

            channel = await self.bot.fetch_channel(clans_config[clan_tag]['chat'], force=True)

            if not channel:
                await ctx.send(
                    f"{get_app_emoji('error')} The chat channel of `{clans_config[clan_tag]['name']}` is set incorrectly! "
                    f"Please report this issue to **server developers**!", ephemeral=True)
                return

            # Find or create a webhook to mimic the Staff Member posting in the clan channel
            for webhook in await channel.fetch_webhooks():
                if webhook.name == "Fake User" and int(webhook.user_id) == int(self.bot.user.id):
                    break
            else:
                webhook = await channel.create_webhook(name="Fake User")

            await webhook.send(
                content=f"{welcome_message} {random.choice(chat_instructions)}",
                username=webhook_name,
                avatar_url=ctx.author.avatar.url
            )

            # Optional: Post reminders about announcement channels
            if clans_config[clan_tag]["announcement"]:
                announcement_channel = f"<#{clans_config[clan_tag]['announcement']}>"
                channel_instructions = [
                    f"Also make sure to follow {announcement_channel}!",
                    f"Don't forget to read {announcement_channel} regularly!",
                    f"Is important that you check {announcement_channel}."
                ]

                await webhook.send(
                    content=f"{random.choice(channel_instructions)}",
                    username=webhook_name,
                    avatar_url=ctx.author.avatar.url
                )

        # Post Final Closure Message in the Ticket Channel
        for interview_webhook in await ctx.channel.fetch_webhooks():
            if interview_webhook.name == "Fake User":
                break
        else:
            interview_webhook = await ctx.channel.create_webhook(name="Fake User")

        finishing_messages = [
            "Welcome to the family, your roles are set and hope you enjoy your time here. Do you have any further questions?",
            "Welcome to the alliance, the interview is finished, have any further questions?",
            "Thank you for being part of the alliance, if no further questions, the ticket will be closed!",
            "Thank you for taking your time to apply, we hope that you will feel comfortable in your new home!"
        ]

        await interview_webhook.send(
            content=f"{random.choice(finishing_messages)}",
            username=webhook_name,
            avatar_url=ctx.author.avatar.url
        )


    @ipy.message_context_menu(name="Verify Accounts")
    @has_roles("RECRUITMENT_ROLE", "SERVER_DEVELOPMENT_ROLE", "LEADER_ROLE")
    async def Verify_Accounts(self, ctx: ipy.ContextMenuContext):
        """
        Context Menu version of verification.
        Scans message for tags, links them if needed, and performs full verification.
        """
        await ctx.defer(ephemeral=True)

        player_links = json.load(open("data/member_tags.json", "r"))
        player_links_reversed = reverse_dict(player_links)

        try:
            member = await self.bot.fetch_member(ctx.target.author.id, ctx.guild_id, force=True)
        except ipy.errors.NotFound:
            await ctx.send(f"{get_app_emoji('error')} User is not in the server, cannot verify.", ephemeral=True)
            return

        clans_config: dict[str, AllianceClanData] = json.load(open("data/clans_config.json", "r"))
        member_roles = [int(role.id) for role in member.roles]
        clan_roles = set([clans_config[key]["role"] for key in clans_config.keys()])

        # Try extracting tags from message
        corrected_tags = await extract_tags(self.bot.coc, ctx.target.content, context=ctx)
        
        # Fallback to linked tags if message contains none
        if not corrected_tags:
            if not player_links.get(str(member.id)):
                await ctx.send(f"{get_app_emoji('error')} No account linked to the player, must provide player tag.", ephemeral=True)
                return
            corrected_tags = player_links[str(member.id)]

        if not corrected_tags:
            return

        valid_tags = []
        valid_roles = []
        player_townhalls = []
        
        config: sc.GuildConfig = sc.get_config(ctx.guild.id)

        for player_tag in corrected_tags:
            player = await fetch_player(self.bot.coc, player_tag, update=True)
            
            th_role = config.TH_ROLE(player.town_hall)
            if th_role:
                player_townhalls.append(th_role)

            if player_tag not in player_links_reversed:
                player_links.setdefault(str(member.id), []).append(player.tag)

            if not player.clan:
                await ctx.send(f"{get_app_emoji('error')} `{player.name} ({player.tag})` is not in any clan!",
                            ephemeral=True, delete_after=4)
                continue

            if player.clan.tag not in clans_config.keys():
                await ctx.send(f"{get_app_emoji('error')} `{player.name} ({player.tag})` is not in any alliance clans!",
                            ephemeral=True, delete_after=4)
                continue

            valid_tags.append(player.tag)
            valid_roles.append(clans_config[player.clan.tag]["role"])

        with open("data/member_tags.json", "w") as file:
            json.dump(player_links, file, indent=4)
        
        valid_roles += player_townhalls
        invalid_roles = list(set(member_roles).intersection(clan_roles) - set(valid_roles))

        if valid_tags:
            if config.FAMILY_ROLE:
                valid_roles.append(config.FAMILY_ROLE)

            player = await fetch_player(self.bot.coc, valid_tags[0], update=True)
            new_name = f"{player.name} | {player.clan}"[:32]

            await ctx.send(
                f"{get_app_emoji('success')} The player's account(s) that are part of *All For One* is/are successfully verified, "
                f"and all roles are set!",
                ephemeral=True)
        else:
            if config.VISITOR_ROLE:
                valid_roles.append(config.VISITOR_ROLE)
            if config.FAMILY_ROLE:
                invalid_roles.append(config.FAMILY_ROLE)

            player = await fetch_player(self.bot.coc, corrected_tags[0], update=True)
            new_name = f"{player.name} | Visitor"[:32]

            await ctx.send(f"{get_app_emoji('error')} The player's account(s) is/are not part of *All For One*!")

        await member.add_roles(valid_roles, reason=f"{ctx.author} {ctx.author.id} used /player verify")

        try:
            await member.remove_roles(invalid_roles, reason=f"{ctx.author} {ctx.author.id} used /player verify")
            if ctx.author.top_role.position > member.top_role.position:
                await member.edit(nickname=new_name, reason=f"{ctx.author} {ctx.author.id} used /player verify")
        except (ipy.errors.HTTPException, ipy.errors.Forbidden):
            pass


    @ipy.global_autocomplete(option_name="player_nickname")
    async def player_nickname_autocomplete(self, ctx: ipy.AutocompleteContext):
        """
        Autocomplete handler for Nickname field in verification.
        Suggests standard format "Name | Clan" based on linked accounts.
        """
        if "user" not in ctx.kwargs:
            name_choice = [{"name": "Please choose a user first", "value": "None"}]
            await ctx.send(name_choice)
            return

        member = await ctx.guild.fetch_member(ctx.kwargs["user"])

        # Default to current nickname or username
        player_name = member.nickname if member.nickname else member.username
        player_links = json.load(open("data/member_tags.json", "r"))
        clans_config: dict[str, AllianceClanData] = json.load(open("data/clans_config.json", "r"))

        if "player_tags" not in ctx.kwargs:
            if not player_links.get(str(member.id)):
                name_choice = [{"name": "Please choose a user first", "value": player_name}]
                await ctx.send(name_choice)
                return
            corrected_tags = player_links[str(member.id)]
        else:
            corrected_tags = await extract_tags(self.bot.coc, ctx.kwargs["player_tags"])

        name_choices = [{"name": player_name, "value": player_name}]
        
        # Generate suggestions based on each linked account's Clan Status
        for tag in corrected_tags:
            player = await fetch_player(self.bot.coc, tag)
            clan_tag = player.clan.tag if player.clan else None

            if clan_tag in clans_config:
                nickname = f"{player.name} | {clans_config[clan_tag]['name']}"
            else:
                nickname = f"{player.name} | Visitor"

            name_choices.append({"name": nickname, "value": nickname})

        await ctx.send(name_choices)

def setup(bot: ipy.Client):
    """
    Entry point for loading the extension.
    """
    PlayerCmds(bot)