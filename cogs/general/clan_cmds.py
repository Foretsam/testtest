"""
Clan Management Commands Module.

This extension provides a suite of slash commands for managing the alliance's clan portfolio.
It includes functionality for:
1. Viewing detailed clan information (General, Settings, Linked Members).
2. Editing clan configurations (Messages, Questions, Requirements, Recruitment Status).
3. Managing clan "checks" (e.g., minimum hero levels or trophy requirements).
4. Adding or removing clans from the alliance system.

Dependencies:
    - interactions (Discord interactions)
    - coc (Clash of Clans API wrapper)
    - core (Internal utilities, models, checks, and emoji management)
"""

import interactions as ipy
import json
import re
import difflib
import coc
from coc import utils

# Explicit imports to maintain code clarity
from core.utils import *
from core.models import *
from core.emojis_manager import *
from core.checks import *

class ClanCmds(ipy.Extension):
    """
    Extension class housing all clan-related slash commands and component callbacks.
    """

    def __init__(self, bot: ipy.Client):
        self.bot = bot

    @ipy.component_callback("clan_info")
    async def clan_info_button(self, ctx: ipy.ComponentContext):
        """
        Callback for the 'Clan Info' button often found in list views.
        
        Fetches and displays a public summary of the clan, including:
        - Leader info
        - War statistics
        - Clan labels (with custom emojis if available)
        - Current league and points

        Args:
            ctx (ipy.ComponentContext): The button interaction context.
        """
        # 1. Fetch all app emojis to cache so we can check for custom label emojis
        cached_emojis = await fetch_emojis(self.bot)

        # Extract clan tag from the button label (Expected format: "Name (TAG)")
        clan_tag = ctx.component.label.split("(")[1].replace(")", "")
        clan = await fetch_clan(self.bot.coc, clan_tag)
        leader_object = utils.get(clan.members, role=coc.Role.leader)
        
        # 2. Dynamic League Emoji retrieval
        league_emoji = get_app_emoji(str(clan.war_league).replace(" ", ""))
        
        log = ":unlock: - public" if clan.public_war_log else ":lock: - private"

        # 3. Dynamic Label Logic: Match in-game labels to cached custom emojis
        clan_labels = ""
        for label in clan.labels:
            label_emoji = get_app_emoji('empty_label')
            label_key = str(label.name).replace(' ', '')
            
            # Check if we have a specific emoji for this label key
            if label_key in cached_emojis:
                label_emoji = cached_emojis[label_key]

            clan_labels += f"{label_emoji}{label.name}\n"

        if not clan_labels:
            clan_labels = f"{get_app_emoji('empty_label')} None\n" * 3

        clan_description = clan.description
        if not clan_description:
            clan_description = "There is no clan description, it seems that the leader is too lazy..."

        # Construct the summary embed
        clan_embed = ipy.Embed(
            title=f"**{clan.name}** `{clan.tag}`",
            description=f"{get_app_emoji('leader')}{leader_object.name} ({leader_object.tag})\n"
                        f":gear:{translate_clan_type(clan.type)} | TH{clan.required_townhall}+\n"
                        f":link:[In-game Link]({clan.share_link})\n"
                        f"{get_app_emoji('coc_trophy')}{clan.points} {get_app_emoji('vs_trophy')}{clan.builder_base_points}",
            fields=[
                ipy.EmbedField(
                    name=f"**Description**",
                    value=clan_description,
                    inline=False
                ),
                ipy.EmbedField(
                    name=f"**Clan Level**",
                    value=f"{get_app_emoji('clan_logo')}{clan.level}",
                    inline=True
                ),
                ipy.EmbedField(
                    name=f"**War League**",
                    value=f"{league_emoji}{str(clan.war_league).replace('League', '')}",
                    inline=True
                ),
                ipy.EmbedField(
                    name=f"**Clan Labels**",
                    value=clan_labels,
                    inline=True
                ),
                ipy.EmbedField(
                    name=f"**War Record**",
                    value=f"{get_app_emoji('war_won')} - {clan.war_wins}\n"
                          f"{get_app_emoji('war_lost')} - {clan.war_losses}\n"
                          f"{get_app_emoji('war_draw')} - {clan.war_ties}",
                    inline=True
                ),
                ipy.EmbedField(
                    name=f"**War Information**",
                    value=f"{log}\n"
                          f":tickets: - {clan.war_frequency}\n"
                          f":fire: - {clan.war_win_streak}",
                    inline=True
                ),
            ],
            footer=ipy.EmbedFooter(
                text=f"Clan Members: {clan.member_count}/50",
                icon_url=FAMILY_ICON_URL),
            thumbnail=ipy.EmbedAttachment(url=clan.badge.url),
            color=COLOR
        )

        await ctx.send(embeds=[clan_embed], ephemeral=True)

    @ipy.slash_command(name="clan", description="Clan utility")
    async def clan_base(self, ctx: ipy.SlashContext):
        """Base command for clan utilities."""
        pass

    @clan_base.subcommand(sub_cmd_name="info", sub_cmd_description="Clans' info utility")
    @ipy.slash_option(
        name="clan_name",
        description="An alliance clan",
        opt_type=ipy.OptionType.STRING,
        autocomplete=True,
        required=True
    )
    @ipy.slash_option(
        name="info_type",
        description="Information type",
        opt_type=ipy.OptionType.STRING,
        choices=[
            ipy.SlashCommandChoice(name="General Information", value="detailed"),
            ipy.SlashCommandChoice(name="Alliance Settings", value="settings"),
            ipy.SlashCommandChoice(name="Linked Members", value="members"),
        ],
        required=True
    )
    @ipy.slash_option(
        name="hidden",
        description="Hide the message?",
        opt_type=ipy.OptionType.BOOLEAN
    )
    async def clan_info(self, ctx: ipy.SlashContext, clan_name: str, info_type: str, hidden: bool = True):
        """
        Retrieves information about a specific alliance clan.
        
        Modes:
        - Settings: Shows internal configuration (roles, channels, messages).
        - Detailed: Shows public stats (War log, description, labels).
        - Members: Lists members linked to Discord users.
        """
        await ctx.defer(ephemeral=True if hidden else False)

        clan = await fetch_clan(self.bot.coc, clan_name)
        leader_object = utils.get(clan.members, role=coc.Role.leader)
        clans_config: dict[str, AllianceClanData] = json.load(open("data/clans_config.json", "r"))

        if info_type == "settings":
            # Display internal bot configuration for the clan
            value = clans_config[clan.tag]
            clan_messages = value["msg"].replace("|", "\n")
            clan_questions = value["questions"].replace("|", "\n")
            recruit_emoji = get_app_emoji('success') if value['recruitment'] else get_app_emoji('error')
            required_townhall = extract_integer(value['requirement'])

            clan_channels = f"<#{value['chat']}>"
            if value['announcement']:
                clan_channels += f"\n<#{value['announcement']}>"

            clan_embed = ipy.Embed(
                title=f"**{clan.name}** `{clan.tag}`",
                description=f"{get_app_emoji('leader')}{leader_object.name} ({leader_object.tag})\n"
                            f":gear:{translate_clan_type(clan.type)}\n"
                            f":link:[In-game Link]({clan.share_link})\n"
                            f"{get_app_emoji(f'Townhall{required_townhall}')} {value['requirement']}",
                fields=[
                    ipy.EmbedField(
                        name=f"**Recruitment Status**",
                        value=f"{recruit_emoji}{value['recruitment']}",
                        inline=False
                    ),
                    ipy.EmbedField(
                        name=f"**Clan Role**",
                        value=f"Role: <@&{value['role']}>\n"
                            f"GK Role: <@&{value['gk_role']}>",
                        inline=False
                    ),
                    ipy.EmbedField(
                        name=f"**Clan Channels**",
                        value=f"{clan_channels}",
                        inline=False
                    ),
                    ipy.EmbedField(
                        name=f"**Clan Messages**",
                        value=f"{clan_messages}",
                        inline=False
                    ),
                    ipy.EmbedField(
                        name=f"**Clan Questions**",
                        value=f"{clan_questions}",
                        inline=False
                    ),
                ],
                footer=ipy.EmbedFooter(
                    text=f"Clan Members: {clan.member_count}/50",
                    icon_url=FAMILY_ICON_URL
                ),
                thumbnail=ipy.EmbedAttachment(url=clan.badge.url),
                color=COLOR
            )

            # Append custom checks if they exist
            clan_checks = ""
            for check in value["checks"]:
                clan_checks += f"**{CLAN_CHECK_NAMES[check]}**\n" \
                            f"- Minimum Value: {value['checks'][check]['min_value']}\n\n" 

            if clan_checks:
                clan_embed.add_field(
                    name=f"**Clan Checks**",
                    value=clan_checks,
                    inline=False
                )

        elif info_type == "detailed":
            # Display public in-game statistics
            log = ":unlock: - public" if clan.public_war_log else ":lock: - private"

            clan_labels = ""
            for label in clan.labels:
                label_emoji = get_app_emoji(str(label.name).replace(' ', '')) 
                clan_labels += f"{label_emoji}{label.name}\n"

            if not clan_labels:
                clan_labels = f"{get_app_emoji('empty_label')} None\n" * 3

            clan_description = clan.description
            if not clan_description:
                clan_description = "There is no clan description, it seems that the leader is too lazy..."

            league_emoji = get_app_emoji(str(clan.war_league).replace(' ', ''))
            clan_embed = ipy.Embed(
                title=f"**{clan.name}** `{clan.tag}`",
                description=f"{get_app_emoji('leader')}{leader_object.name} ({leader_object.tag})\n"
                            f":gear:{translate_clan_type(clan.type)} | TH{clan.required_townhall}+\n"
                            f":link:[In-game Link]({clan.share_link})\n"
                            f"{get_app_emoji('coc_trophy')}{clan.points} {get_app_emoji('vs_trophy')}{clan.builder_base_points}",
                fields=[
                    ipy.EmbedField(
                        name=f"**Description**",
                        value=clan_description,
                        inline=False
                    ),
                    ipy.EmbedField(
                        name=f"**Clan Level**",
                        value=f"{get_app_emoji('clan_logo')}{clan.level}",
                        inline=True
                    ),
                    ipy.EmbedField(
                        name=f"**War League**",
                        value=f"{league_emoji}{str(clan.war_league).replace('League', '')}",
                        inline=True
                    ),
                    ipy.EmbedField(
                        name=f"**Clan Labels**",
                        value=clan_labels,
                        inline=True
                    ),
                    ipy.EmbedField(
                        name=f"**War Record**",
                        value=f"{get_app_emoji('war_won')} - {clan.war_wins}\n"
                            f"{get_app_emoji('war_lost')} - {clan.war_losses}\n"
                            f"{get_app_emoji('war_draw')} - {clan.war_ties}",
                        inline=True
                    ),
                    ipy.EmbedField(
                        name=f"**War Information**",
                        value=f"{log}\n"
                            f":tickets: - {clan.war_frequency}\n"
                            f":fire: - {clan.war_win_streak}",
                        inline=True
                    ),
                ],
                footer=ipy.EmbedFooter(
                    text=f"Clan Members: {clan.member_count}/50",
                    icon_url=FAMILY_ICON_URL),
                thumbnail=ipy.EmbedAttachment(url=clan.badge.url),
                color=COLOR
            )

        else:
            # Display list of linked members
            player_links = json.load(open("data/member_tags.json", "r"))
            player_links_reversed = reverse_dict(player_links)

            member_list = {}
            unlinked_list = []
            
            # Match clan members to discord users
            for member in clan.members:
                if member.tag not in player_links_reversed:
                    unlinked_list.append(f"{member.name} `{member.tag}`")
                    continue

                user_id = player_links_reversed[member.tag][0]
                member_list.setdefault(user_id, []).append(f"{member.name} `{member.tag}`")

            member_content = ""
            for key, value in member_list.items():
                members = "\n".join(value)
                member_content += f"<@{key}>\n{members}\n"

            clan_embed = ipy.Embed(
                title=f"**{clan.name}** `{clan.tag}`",
                description=member_content,
                footer=ipy.EmbedFooter(
                    text=f"Clan Members: {clan.member_count}/50",
                    icon_url=FAMILY_ICON_URL),
                thumbnail=ipy.EmbedAttachment(url=clan.badge.url),
                color=COLOR
            )

            if unlinked_list:
                unlinked_content = "\n".join(unlinked_list)
                clan_embed.add_field(
                    name=f"**Unlinked Members**",
                    value=unlinked_content,
                    inline=False
                )

        await ctx.send(embeds=[clan_embed])


    @clan_base.subcommand(sub_cmd_name="link", sub_cmd_description="Get clan links")
    @ipy.slash_option(
        name="clan_name",
        description="An alliance clan",
        opt_type=ipy.OptionType.STRING,
        required=True,
        autocomplete=True
    )
    async def clan_link(self, ctx: ipy.SlashContext, clan_name: str):
        """Returns the in-game share link for a clan."""
        clan = await fetch_clan(self.bot.coc, clan_name)
        await ctx.send(clan.share_link)

    @clan_base.group(name="checks", description="Add/remove/edit alliance clan checks")
    async def clan_checks_group(self, ctx: ipy.SlashContext):
        """Group for managing clan requirements/checks."""
        pass

    @clan_checks_group.subcommand(sub_cmd_name="add", sub_cmd_description="Add a clan check")
    @has_roles("SERVER_DEVELOPMENT_ROLE")
    @ipy.slash_option(
        name="clan_name",
        description="An alliance clan",
        opt_type=ipy.OptionType.STRING,
        required=True,
        autocomplete=True,
    )
    @ipy.slash_option(
        name="check_type",
        description="Check type",
        opt_type=ipy.OptionType.STRING,
        required=True,
        choices=CLAN_CHECK_CHOICES
    )
    @ipy.slash_option(
        name="min_value",
        description="Minimum value",
        opt_type=ipy.OptionType.INTEGER,
        min_value=0,
        required=True,
    )
    async def clan_checks_add(self, ctx: ipy.SlashContext, clan_name: str, check_type: str, min_value: int):
        """Adds a specific validation check (e.g., Min Hero Level) to a clan."""
        clans_config: dict[str, AllianceClanData] = json.load(open("data/clans_config.json", "r"))

        try:
            clan_tag = (await extract_tags(self.bot.coc, clan_name, extract_type="clan"))[0]
        except IndexError:
            raise InvalidTagError(tag=clan_name, tag_type="clan")

        # Limit checks to prevent complexity
        if len(clans_config[clan_tag]["checks"]) >= 2:
            await ctx.send(
                f"{get_app_emoji('error')} Each clan can only have up to 2 checks. Remove irrelevent checks using `/clan checks remove`!",
                ephemeral=True)
            return

        if check_type in clans_config[clan_tag]["checks"]:
            await ctx.send(f"{get_app_emoji('error')} This clan already have this type of check!", ephemeral=True)
            return

        clans_config[clan_tag]["checks"][check_type] = {"min_value": min_value}
        with open("data/clans_config.json", "w") as file:
            json.dump(clans_config, file, indent=4)

        await ctx.send(
            f"{get_app_emoji('success')} The clan check `{CLAN_CHECK_NAMES[check_type]}` is added to `{clans_config[clan_tag]['name']}`.",
            ephemeral=True)

    @clan_checks_group.subcommand(sub_cmd_name="remove", sub_cmd_description="Remove a clan check")
    @has_roles("SERVER_DEVELOPMENT_ROLE")
    @ipy.slash_option(
        name="clan_name",
        description="An alliance clan",
        opt_type=ipy.OptionType.STRING,
        required=True,
        autocomplete=True,
    )
    @ipy.slash_option(
        name="check_type",
        description="Check type",
        opt_type=ipy.OptionType.STRING,
        required=True,
        choices=CLAN_CHECK_CHOICES
    )
    async def clan_checks_remove(self, ctx: ipy.SlashContext, clan_name: str, check_type: str):
        """Removes a validation check from a clan."""
        clans_config: dict[str, AllianceClanData] = json.load(open("data/clans_config.json", "r"))

        try:
            clan_tag = (await extract_tags(self.bot.coc, clan_name, extract_type="clan"))[0]
        except IndexError:
            raise InvalidTagError(tag=clan_name, tag_type="clan")

        if check_type not in clans_config[clan_tag]["checks"]:
            await ctx.send(f"{get_app_emoji('error')} This clan do not have this type of check!", ephemeral=True)
            return

        del clans_config[clan_tag]["checks"][check_type]
        with open("data/clans_config.json", "w") as file:
            json.dump(clans_config, file, indent=4)

        await ctx.send(
            f"{get_app_emoji('success')} The clan check `{CLAN_CHECK_NAMES[check_type]}` is removed from `{clans_config[clan_tag]['name']}`.",
            ephemeral=True)

    @clan_checks_group.subcommand(sub_cmd_name="edit", sub_cmd_description="Edit a clan check")
    @has_roles("SERVER_DEVELOPMENT_ROLE")
    @ipy.slash_option(
        name="clan_name",
        description="An alliance clan",
        opt_type=ipy.OptionType.STRING,
        required=True,
        autocomplete=True,
    )
    @ipy.slash_option(
        name="check_type",
        description="Check type",
        opt_type=ipy.OptionType.STRING,
        required=True,
        choices=CLAN_CHECK_CHOICES
    )
    async def clan_checks_edit(self, ctx: ipy.SlashContext, clan_name: str, check_type: str):
        """Edits the minimum value of an existing clan check via Modal."""
        clans_config: dict[str, AllianceClanData] = json.load(open("data/clans_config.json", "r"))

        try:
            clan_tag = (await extract_tags(self.bot.coc, clan_name, extract_type="clan"))[0]
        except IndexError:
            raise InvalidTagError(tag=clan_name, tag_type="clan")

        if check_type not in clans_config[clan_tag]["checks"]:
            await ctx.send(
                f"{get_app_emoji('error')} This clan do not have such check. You can add this check by using `/clan checks add`",
                ephemeral=True)
            return

        modal = ipy.Modal(
            ipy.ShortText(
                label="The minimum value of the check.",
                custom_id=f"{clan_name}|0",
                value=str(clans_config[clan_tag]["checks"][check_type]["min_value"])
            ),
            title="Clan Check Edit",
            custom_id=f"clan_check_edit|{check_type}",
        )
        await ctx.send_modal(modal)


    @ipy.modal_callback(re.compile(r"^clan_check_edit\|\w+$"))
    async def clan_check_edit_modal(self, ctx: ipy.ModalContext, **kwargs):
        """Modal callback for saving edited clan checks."""
        for value in ctx.responses.values():
            if value.isnumeric() and int(value) >= 0:
                continue

            await ctx.send(f"{get_app_emoji('error')} `{value}` must be an integer and cannot be negative.")
            return

        clan_tag, _ = next(iter(ctx.responses.keys())).split("|")
        _, check_type = ctx.custom_id.split("|")
        clans_config: dict[str, AllianceClanData] = json.load(open("data/clans_config.json", "r"))

        clans_config[clan_tag]["checks"][check_type]["min_value"] = int(ctx.responses[f"{clan_tag}|0"])
        with open("data/clans_config.json", "w") as file:
            json.dump(clans_config, file, indent=4)

        await ctx.send(f"{get_app_emoji('success')} The clan check `{CLAN_CHECK_NAMES[check_type]}` is edited.",
                    ephemeral=True)


    @clan_base.group(name="edit", description="Edit alliance clan json data")
    async def clan_edit_group(self, ctx: ipy.SlashContext):
        """Group for editing general clan configuration."""
        pass


    @clan_edit_group.subcommand(sub_cmd_name="type", sub_cmd_description="Edit clan type")
    @has_roles("SERVER_DEVELOPMENT_ROLE")
    @ipy.slash_option(
        name="clan_name",
        description="An alliance clan",
        opt_type=ipy.OptionType.STRING,
        required=True,
        autocomplete=True,
    )
    @ipy.slash_option(
        name="clan_type",
        description="Clan type",
        opt_type=ipy.OptionType.STRING,
        choices=[
            ipy.SlashCommandChoice(name="Competitive", value="Competitive"),
            ipy.SlashCommandChoice(name="FWA", value="FWA"),
            ipy.SlashCommandChoice(name="CWL", value="CWL"),      
        ],
        required=True,
    )
    async def clan_edit_type(self, ctx: ipy.SlashContext, clan_name: str, clan_type: str):
        """Updates the type of the clan (e.g., Competitive vs FWA)."""
        await ctx.defer(ephemeral=True)

        try:
            clan_tag = (await extract_tags(self.bot.coc, clan_name, extract_type="clan"))[0]
        except IndexError:
            raise InvalidTagError(tag=clan_name, tag_type="clan")

        clans_config: dict[str, AllianceClanData] = json.load(open("data/clans_config.json", "r"))
        clans_config[clan_tag]["type"] = clan_type
        with open("data/clans_config.json", "w") as file:
            json.dump(clans_config, file, indent=4)

        await ctx.send(f"{get_app_emoji('success')} Clan type is successfully edited.", ephemeral=True)


    @clan_edit_group.subcommand(sub_cmd_name="messages", sub_cmd_description="Edit clan messages")
    @has_roles("SERVER_DEVELOPMENT_ROLE")
    @ipy.slash_option(
        name="clan_name",
        description="An alliance clan",
        opt_type=ipy.OptionType.STRING,
        required=True,
        autocomplete=True,
    )
    async def clan_edit_messages(self, ctx: ipy.SlashContext, clan_name: str):
        """Opens a modal to edit the 3 key messages shown to applicants."""
        try:
            clan_tag = (await extract_tags(self.bot.coc, clan_name, extract_type="clan"))[0]
        except IndexError:
            raise InvalidTagError(tag=clan_name, tag_type="clan")

        clans_config: dict[str, AllianceClanData] = json.load(open("data/clans_config.json", "r"))
        # Parse existing messages for the modal
        clan_messages = clans_config[clan_tag]["msg"].replace("- get_app_emoji('diamond') ", "").split("|")
        
        modal = ipy.Modal(
            ipy.ShortText(
                label="Type in the 1st key information.",
                max_length=50,
                custom_id=clan_name,
                value=clan_messages[0]
            ),
            ipy.ShortText(
                label="Type in the 2nd key information.",
                max_length=50,
                custom_id="textinput2",
                value=clan_messages[1]
            ),
            ipy.ShortText(
                label="Type in the 3rd key information.",
                max_length=50,
                custom_id="textinput3",
                value=clan_messages[2]
            ),
            title="Clan Message Edit",
            custom_id="clan_message_edit",
        )
        await ctx.send_modal(modal)

    @ipy.modal_callback("clan_message_edit")
    async def clan_message_edit_modal(self, ctx: ipy.ModalContext, **kwargs):
        """Modal callback for saving edited clan messages."""
        modal_data = ctx.responses
        clan_tag = list(modal_data.keys())[0]
        clans_config: dict[str, AllianceClanData] = json.load(open("data/clans_config.json", "r"))

        edited_msg = f"- {get_app_emoji('diamond')} {list(modal_data.values())[0]}|" \
                    f"- {get_app_emoji('diamond')} {list(modal_data.values())[1]}|" \
                    f"- {get_app_emoji('diamond')} {list(modal_data.values())[2]}"
        clans_config[clan_tag]["msg"] = edited_msg

        with open("data/clans_config.json", "w") as file:
            json.dump(clans_config, file, indent=4)

        await ctx.send(f"{get_app_emoji('success')} Clan message is successfully edited.", ephemeral=True)

    @clan_edit_group.subcommand(sub_cmd_name="questions", sub_cmd_description="Edit clan questions")
    @has_roles("SERVER_DEVELOPMENT_ROLE")
    @ipy.slash_option(
        name="clan_name",
        description="An alliance clan",
        opt_type=ipy.OptionType.STRING,
        required=True,
        autocomplete=True,
    )
    async def clan_edit_questions(self, ctx: ipy.SlashContext, clan_name: str):
        """Opens a modal to edit the specific questions asked during application to this clan."""
        try:
            clan_tag = (await extract_tags(self.bot.coc, clan_name, extract_type="clan"))[0]
        except IndexError:
            raise InvalidTagError(tag=clan_name, tag_type="clan")

        clans_config: dict[str, AllianceClanData] = json.load(open("data/clans_config.json", "r"))
        clan_questions = clans_config[clan_tag]["questions"].replace("get_app_emoji('arrowright') ", "").split("|")

        # Pad list to 5 items for the modal
        clan_questions += [""] * (5 - len(clan_questions))
    
        modal = ipy.Modal(
            ipy.ShortText(
                label="Type in the 1st key information.",
                max_length=150,
                custom_id="textinputa",
                value=clan_questions[0], 
                required=True
            ),
            ipy.ShortText(
                label="Type in the 2nd key information (optional).",
                max_length=150,
                custom_id="textinputb",
                value=clan_questions[1], 
                required=False
            ),
            ipy.ShortText(
                label="Type in the 3rd key information (optional).",
                max_length=150,
                custom_id="textinputc",
                value=clan_questions[2], 
                required=False
            ),
            ipy.ShortText(
                label="Type in the 4th key information (optional).",
                max_length=150,
                custom_id="textinputd",
                value=clan_questions[3], 
                required=False
            ),
            ipy.ShortText(
                label="Type in the 5th key information (optional).",
                max_length=150,
                custom_id="textinpute",
                value=clan_questions[4],  
                required=False
            ),
            title="Clan Questions Edit",
            custom_id=f"clan_questions_edit:{clan_tag}",
        )
        await ctx.send_modal(modal)
            
    @ipy.modal_callback(re.compile(r"^clan_questions_edit:.*$"))
    async def clan_questions_edit_modal(self, ctx: ipy.ModalContext, **kwargs):
        """Modal callback for saving edited clan questions."""
        modal_data = ctx.responses
        clan_tag = ctx.custom_id.split(":")[1]
        clans_config: dict[str, AllianceClanData] = json.load(open("data/clans_config.json", "r"))

        # Reconstruct string from modal inputs
        edited_questions = "|".join(
            f"{modal_data.get(f'textinput{i}', '')}"
            for i in ["a", "b", "c", "d", "e"]
        )
        clans_config[clan_tag]["questions"] = edited_questions

        with open("data/clans_config.json", "w") as file:
            json.dump(clans_config, file, indent=4)

        await ctx.send(f"{get_app_emoji('success')} Clan questions have been successfully edited.", ephemeral=True)

    @clan_edit_group.subcommand(sub_cmd_name="requirement", sub_cmd_description="Edit clan requirement")
    @has_roles("SERVER_DEVELOPMENT_ROLE")
    @ipy.slash_option(
        name="clan_name",
        description="An alliance clan",
        opt_type=ipy.OptionType.STRING,
        required=True,
        autocomplete=True,
    )
    @ipy.slash_option(
        name="clan_requirement",
        description="Clan requirement",
        opt_type=ipy.OptionType.STRING,
        choices=[
            ipy.SlashCommandChoice(name="TH17+", value="TH17+"),
            ipy.SlashCommandChoice(name="TH16+", value="TH16+"),
            ipy.SlashCommandChoice(name="TH15+", value="TH15+"),
            ipy.SlashCommandChoice(name="TH14+", value="TH14+"),
            ipy.SlashCommandChoice(name="TH13+", value="TH13+"),
            ipy.SlashCommandChoice(name="TH12+", value="TH12+"),
            ipy.SlashCommandChoice(name="TH11+", value="TH11+"),
        ],
        required=True,
    )
    async def clan_edit_requirement(self, ctx: ipy.SlashContext, clan_name: str, clan_requirement: str):
        """Updates the minimum Town Hall requirement for the clan."""
        await ctx.defer(ephemeral=True)

        try:
            clan_tag = (await extract_tags(self.bot.coc, clan_name, extract_type="clan"))[0]
        except IndexError:
            raise InvalidTagError(tag=clan_name, tag_type="clan")

        clans_config: dict[str, AllianceClanData] = json.load(open("data/clans_config.json", "r"))
        clans_config[clan_tag]["requirement"] = clan_requirement
        with open("data/clans_config.json", "w") as file:
            json.dump(clans_config, file, indent=4)

        await ctx.send(f"{get_app_emoji('success')} Clan requirement is successfully edited.", ephemeral=True)


    @clan_edit_group.subcommand(sub_cmd_name="recruitment", sub_cmd_description="Edit clan recruitment status")
    @has_roles("SERVER_DEVELOPMENT_ROLE")
    @ipy.slash_option(
        name="clan_name",
        description="Alliance clan name",
        opt_type=ipy.OptionType.STRING,
        required=True,
        autocomplete=True,
    )
    @ipy.slash_option(
        name="recruitment_status",
        description="Clan recruitment status",
        opt_type=ipy.OptionType.BOOLEAN,
        required=True,
    )
    async def clan_edit_recruitment(self, ctx: ipy.SlashContext, clan_name: str, recruitment_status: bool):
        """Toggles whether the clan is currently accepting new members."""
        await ctx.defer(ephemeral=True)

        try:
            clan_tag = (await extract_tags(self.bot.coc, clan_name, extract_type="clan"))[0]
        except IndexError:
            raise InvalidTagError(tag=clan_name, tag_type="clan")

        clans_config: dict[str, AllianceClanData] = json.load(open("data/clans_config.json", "r"))
        clans_config[clan_tag]["recruitment"] = recruitment_status
        with open("data/clans_config.json", "w") as file:
            json.dump(clans_config, file, indent=4)

        await ctx.send(f"{get_app_emoji('success')} Clan recruitment status is successfully edited.", ephemeral=True)


    @clan_base.subcommand(sub_cmd_name="add", sub_cmd_description="Add a clan to the alliance")
    @has_roles("SERVER_DEVELOPMENT_ROLE")
    @ipy.slash_option(
        name="clan_tag",
        description="Clan tag",
        opt_type=ipy.OptionType.STRING,
        required=True
    )
    @ipy.slash_option(
        name="clan_name",
        description="Clan name",
        opt_type=ipy.OptionType.STRING,
        required=True
    )
    @ipy.slash_option(
        name="clan_role",
        description="Clan role",
        opt_type=ipy.OptionType.ROLE,
        required=True
    )
    @ipy.slash_option(
        name="clan_gk_role",
        description="Clan gatekeeper role",
        opt_type=ipy.OptionType.ROLE,
        required=True
    )
    @ipy.slash_option(
        name="clan_prefix",
        description="Clan prefix",
        opt_type=ipy.OptionType.STRING,
        max_length=5,
        required=True
    )
    @ipy.slash_option(
        name="clan_message1",
        description="1st message",
        opt_type=ipy.OptionType.STRING,
        required=True,
        max_length=50
    )
    @ipy.slash_option(
        name="clan_message2",
        description="2nd message",
        opt_type=ipy.OptionType.STRING,
        required=True,
        max_length=50
    )
    @ipy.slash_option(
        name="clan_message3",
        description="3rd message",
        opt_type=ipy.OptionType.STRING,
        required=True,
        max_length=50
    )
    @ipy.slash_option(
        name="clan_questions1",
        description="1st question",
        opt_type=ipy.OptionType.STRING,
        required=True,
        max_length=150
    )
    @ipy.slash_option(
        name="clan_type",
        description="Clan type",
        opt_type=ipy.OptionType.STRING,
        required=True,
        choices=[
            ipy.SlashCommandChoice(name="Competitive", value="Competitive"),
            ipy.SlashCommandChoice(name="FWA", value="FWA"),
            ipy.SlashCommandChoice(name="CWL", value="CWL"),      
        ]
    )
    @ipy.slash_option(
        name="clan_req",
        description="Townhall requirement",
        opt_type=ipy.OptionType.INTEGER,
        required=True,
        choices=[
            ipy.SlashCommandChoice(name="17", value=17),
            ipy.SlashCommandChoice(name="16", value=16),
            ipy.SlashCommandChoice(name="15", value=15),
            ipy.SlashCommandChoice(name="14", value=14),
            ipy.SlashCommandChoice(name="13", value=13),
            ipy.SlashCommandChoice(name="12", value=12),
            ipy.SlashCommandChoice(name="11", value=11),
        ]
    )
    @ipy.slash_option(
        name="clan_leader",
        description="Clan leader",
        opt_type=ipy.OptionType.USER,
        required=True,
    )
    @ipy.slash_option(
        name="chat_channel",
        description="Clan's chat channel",
        opt_type=ipy.OptionType.CHANNEL,
        channel_types=[
            ipy.ChannelType.GUILD_TEXT,
            ipy.ChannelType.GUILD_PUBLIC_THREAD,
        ],
        required=True,
    )
    @ipy.slash_option(
        name="announcement_channel",
        description="Clan's announcement channel",
        opt_type=ipy.OptionType.CHANNEL,
        channel_types=[
            ipy.ChannelType.GUILD_TEXT,
            ipy.ChannelType.GUILD_PUBLIC_THREAD,
        ],
    )
    @ipy.slash_option(
        name="clan_emoji",
        description="Clan emoji name (Default: FreshStar)",
        opt_type=ipy.OptionType.STRING,
        autocomplete=True,
    )
    @ipy.slash_option(
        name="clan_questions2",
        description="2nd question",
        opt_type=ipy.OptionType.STRING,
        required=False,
        max_length=150
    )
    @ipy.slash_option(
        name="clan_questions3",
        description="3rd question",
        opt_type=ipy.OptionType.STRING,
        required=False,
        max_length=150
    )
    @ipy.slash_option(
        name="clan_questions4",
        description="4th question",
        opt_type=ipy.OptionType.STRING,
        required=False,
        max_length=150
    )
    @ipy.slash_option(
        name="clan_questions5",
        description="5th question",
        opt_type=ipy.OptionType.STRING,
        required=False,
        max_length=150
    )
    async def clan_add(self, ctx: ipy.SlashContext, clan_tag: str, clan_name: str, clan_role: ipy.Role, clan_gk_role: ipy.Role,
                    clan_prefix: str, clan_message1: str, clan_message2: str, clan_message3: str,
                    clan_type: str, clan_req: int, clan_leader: ipy.Member,
                    chat_channel: ipy.GuildChannel, clan_questions1: str, 
                    announcement_channel: ipy.GuildChannel = None, clan_emoji: str = "FreshStar", 
                    clan_questions2: str = None, clan_questions3: str = None, clan_questions4: str = None, clan_questions5: str = None):
        """
        Registers a new clan to the alliance system.
        This updates the configuration file and registers the clan for API updates.
        """
        await ctx.defer(ephemeral=True)

        added_clan = await fetch_clan(self.bot.coc, clan_tag)

        clans_config: dict[str, AllianceClanData] = json.load(open("data/clans_config.json", "r"))

        # Calculate max hero levels (logic present but not currently stored/used in this function scope)
        max_hero_sum = 0
        for hero_name in ["Barbarian King", "Archer Queen", "Grand Warden", "Royal Champion", "Minion Prince"]:
            hero = self.bot.coc.get_hero(hero_name)

            if min(hero.required_th_level) <= clan_req:
                max_hero_sum += hero.get_max_level_for_townhall(clan_req)

        if added_clan.tag in clans_config.keys():
            await ctx.send(f"{get_app_emoji('error')} `{clan_tag}` is already part of the alliance.", ephemeral=True)
            return

        # Format messages and questions for storage
        clan_msg = f"- {get_app_emoji('diamond')} {clan_message1}|" \
                f"- {get_app_emoji('diamond')} {clan_message2}|" \
                f"- {get_app_emoji('diamond')} {clan_message3}"

        questions = [clan_questions1, clan_questions2, clan_questions3, clan_questions4, clan_questions5]
        clan_questions_list = [f"{get_app_emoji('arrow')} {q}" for q in questions if q and q.strip()]

        if clan_questions_list:  
            clan_questions = "|".join(clan_questions_list)
        else:
            clan_questions = None  

        # Build config object
        clans_config[added_clan.tag] = {
            "leader": int(clan_leader.id),
            "emoji": clan_emoji,
            "msg": clan_msg,
            "questions": clan_questions,
            "name": clan_name,
            "prefix": clan_prefix,
            "requirement": f"TH{clan_req}+",
            "role": int(clan_role.id),
            "gk_role": int(clan_gk_role.id),
            "type": clan_type,
            "recruitment": True,
            "chat": int(chat_channel.id),
            "announcement": int(announcement_channel.id) if announcement_channel else None,
            "checks": {},
        }

        # Sort and save
        clans_config = await sort_clans_by_merit(self.bot.coc, clans_config)

        with open("data/clans_config.json", "w") as file:
            json.dump(clans_config, file, indent=4)

        # Register for real-time events
        self.bot.coc.add_clan_updates(added_clan.tag)

        await ctx.send(f"{get_app_emoji('success')} `{added_clan.name} ({added_clan.tag})` is added to the alliance.",
                    ephemeral=True)


    @clan_base.subcommand(sub_cmd_name="remove", sub_cmd_description="Remove an alliance clan")
    @has_roles("SERVER_DEVELOPMENT_ROLE")
    @ipy.slash_option(
        name="clan_name",
        description="An alliance clan",
        opt_type=ipy.OptionType.STRING,
        required=True,
        autocomplete=True,
    )
    async def clan_remove(self, ctx: ipy.SlashContext, clan_name: str):
        """Removes a clan from the alliance configuration."""
        await ctx.defer(ephemeral=True)

        clan = await fetch_clan(self.bot.coc, clan_name)

        clans_config: dict[str, AllianceClanData] = json.load(open("data/clans_config.json", "r"))

        del clans_config[clan.tag]

        with open("data/clans_config.json", "w") as file:
            json.dump(clans_config, file, indent=4)

        self.bot.coc.remove_clan_updates(clan.tag)

        await ctx.send(f"{get_app_emoji('success')} `{clan.name}` is removed from the alliance.", ephemeral=True)


    @ipy.global_autocomplete(option_name="clan_name")
    async def clan_autocomplete(self, ctx: ipy.AutocompleteContext):
        """Autocomplete handler providing a list of configured alliance clans."""
        clans_config: dict[str, AllianceClanData] = json.load(open("data/clans_config.json", "r"))
        user_input = ctx.input_text

        clan_choices = {}
        for clan in clans_config.keys():
            autocomplete_name = f"{clans_config[clan]['name']} ({clan})"
            clan_choices[extract_alphabets(clans_config[clan]["name"])] = {"name": autocomplete_name, "value": clan}

        if not user_input:
            return await ctx.send(list(clan_choices.values())[:25])

        returns = difflib.get_close_matches(
            user_input.lower(),
            clan_choices.keys(),
            n=25,
            cutoff=0.15,
        )

        results = []
        for item in returns:
            results.append(clan_choices[str(item)])

        await ctx.send(results)


    @ipy.global_autocomplete(option_name="clan_emoji")
    async def emoji_autocomplete(self, ctx: ipy.AutocompleteContext):
        """Autocomplete handler providing a list of available application emojis."""
        user_input = ctx.input_text

        # Fetch all emojis directly from the bot
        app_emojis = await self.bot.fetch_application_emojis()
        
        # Create the dictionary format required for autocomplete: {Name: {name: Name, value: Name}}
        emoji_choices = {e.name: {"name": e.name, "value": e.name} for e in app_emojis}

        if not user_input:
            return await ctx.send(list(emoji_choices.values())[:25])

        returns = difflib.get_close_matches(
            user_input.lower(),
            emoji_choices.keys(),
            n=25,
            cutoff=0.15,
        )

        results = []
        for item in returns:
            results.append(emoji_choices[item])

        await ctx.send(results)


    @ipy.modal_callback("preview_modal")
    async def preview_modal(self, ctx: ipy.ModalContext, **kwargs):
        """Generic callback for previewing modals (testing utility)."""
        await ctx.send(f"{get_app_emoji('success')} Modal preview is finished.", ephemeral=True)

def setup(bot: ipy.Client):
    """
    Entry point for loading the extension.
    """
    ClanCmds(bot)