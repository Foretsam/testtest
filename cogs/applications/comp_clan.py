"""
Competitive Clan Application Module.

This extension manages the application workflow for players applying to competitive
clans within the alliance. It handles the interactive questionnaire process, assuring
candidates provide necessary details regarding their base, heroes, and timezone
suitability for competitive play.

This module also includes logic for:
1. Validating user identity and ticket ownership.
2. Allowing users to select from their linked Clash of Clans accounts.
3. Automatically filtering available clans based on account stats (TH level, etc.).
4. Generating dynamic selection menus for clan application.

Dependencies:
    - interactions (Discord interactions)
    - coc (Clash of Clans API wrapper)
    - core (Internal utilities, models, checks, and emoji management)
"""

import interactions as ipy
import asyncio
import secrets
import json
import random
import copy
import coc

# Explicit imports to maintain code clarity and traceability
from core.checks import *
from core.utils import *
from core.models import *
from core.emojis_manager import *
from core import server_setup as sc

class ClanApplication(ipy.Extension):
    """
    Manages the interactive components and logic for the Competitive Clan Application system.
    """

    def __init__(self, bot: ipy.Client):
        """
        Initialize the extension.

        Args:
            bot (ipy.Client): The main bot instance.
        """
        self.bot: ipy.Client = bot

    @ipy.component_callback("clan_start_button")
    async def apply_clan(self, ctx: ipy.ComponentContext):
        """
        Callback for the 'Start Application' button in a Competitive Ticket.

        Verifies the applicant's identity, retrieves their linked accounts,
        prompts them to select an account or provide a tag, and then
        generates a list of eligible clans based on their account statistics.

        Args:
            ctx (ipy.ComponentContext): The context of the button interaction.
        """
        member = ctx.author
        
        # Identity Verification:
        # Ensure that the user clicking the button is the owner of the ticket.
        # Checks against both the User ID in the channel topic and the Username in the channel name.
        if extract_integer(ctx.channel.topic) != int(member.id) and \
                extract_alphabets(member.username) != ctx.channel.name.split("┃")[1]:
            await ctx.send(f"{get_app_emoji('error')} Only the applicant of this channel can start the interview!",
                            ephemeral=True)
            return

        # Defer the interaction to prevent timeout while fetching data
        await ctx.defer(ephemeral=True)

        async def check(event: ipy.events.Component):
            """
            Internal check to ensure only the original author interacts with components.
            """
            if int(event.ctx.author.id) == int(ctx.author.id):
                return True
            await event.ctx.send(f"{get_app_emoji('error')} You cannot interact with other user's components.", ephemeral=True)
            return False

        async def msg_check(event: ipy.events.MessageCreate):
            """
            Internal check to verify messages come from the correct user in the correct channel.
            """
            if not event.message.channel.id or not event.message.author.id:
                return False
            if int(event.message.author.id) == int(ctx.author.id) and \
                    int(event.message.channel.id) == int(ctx.channel.id):
                return True
            return False
            
        account_tags = []
        jump_url = ctx.message.jump_url if ctx.message else ""
        
        # Load linked accounts from local storage
        player_links = json.load(open("data/member_tags.json", "r"))
        player_select = None
        d_player_select = None
        player = None
        player_options = {}
        
        # Iterate through linked tags for the user, verifying they exist in the API
        for tag in copy.deepcopy(player_links.get(str(ctx.author.id), [])):
            try:
                player = await fetch_player(self.bot.coc, tag)
            except coc.errors.NotFound:
                # Remove invalid tags from the local cache
                player_links[str(ctx.author.id)].remove(tag)
                continue
        
            townhall_emoji = ipy.PartialEmoji.from_str(get_app_emoji(f"Townhall{player.town_hall}"))
        
            # Create a selection option for each valid linked account
            player_options[player.tag] = ipy.StringSelectOption(
                label=f"{player.name} ({player.tag})",
                value=player.tag,
                description=f"{player.role} of {player.clan}" if player.clan else "Not in a clan",
                emoji=townhall_emoji
            )
        
        # Build the selection menu if linked accounts exist
        if player_options:
            player_select = ipy.StringSelectMenu(
                *player_options.values(),
                placeholder="👤 Apply with your linked accounts",
                custom_id="player_apply_select"
            )
            d_player_select = copy.deepcopy(player_select)
        
        # Display instructions for providing an account tag (manual entry or selection)
        embed = ipy.Embed(
            title=f"**Please provide the tag of your account \n"
            f"(ONLY YOUR MAIN ACCOUNT, you can send any other account tags after the interview ends).**",
            description=f"- Post the tag of your Clash of Clans account in the chat.\n"
                        f"- Example answer: `#LCCYJVRUY` (can be copied from your profile)\n"
                        f"- Go to this [message]({jump_url}) and click **\"Human Support\"** button for help.",
            footer=ipy.EmbedFooter(
                text="Feel free to ask for help for any confusions."
            ),
            color=COLOR
        )
        msg = await ctx.channel.send(embeds=[embed], components=player_select)
        
        fails = 0
        # Main loop to wait for user input (either message or component interaction)
        while True:
            wait_tasks = [
                asyncio.create_task(
                    self.bot.wait_for("on_message_create", checks=msg_check, timeout=600),
                    name="message"
                )
            ]
            if player_select:
                wait_tasks.append(
                    asyncio.create_task(
                        self.bot.wait_for_component(
                            components=player_select, check=check, messages=int(msg.id), timeout=600),
                        name="select"
                    )
                )
        
            # Wait for the first completed task (message or select)
            done, pending = await asyncio.wait(wait_tasks, return_when=asyncio.FIRST_COMPLETED)
            finished: asyncio.Task = list(done)[0]
        
            # Cancel any remaining tasks
            for task in pending:
                try:
                    task.cancel()
                except asyncio.CancelledError:
                    pass
        
            action_name = finished.get_name()
        
            try:
                action_result: ipy.events.MessageCreate | ipy.events.Component = finished.result()
            except asyncio.TimeoutError:
                raise ComponentTimeoutError(message=msg)
        
            # Handle Manual Tag Entry via Message
            if action_name == "message":
                valid_tags = await extract_tags(self.bot.coc, action_result.message.content)
                if not valid_tags:
                    if fails == 3:
                        await msg.edit(embed=FAIL_EMBED, components=CLAN_RESTART_BUTTON)
                        raise asyncio.exceptions.CancelledError
        
                    try:
                        await ctx.send(f"{get_app_emoji('error')} Please provide a valid tag in the chat.", ephemeral=True)
                    except ipy.errors.HTTPException:
                        await ctx.channel.send(f"{get_app_emoji('error')} Please provide a valid tag in the chat.",
                                                ephemeral=True)
        
                    fails += 1
                    continue
        
                player = await fetch_player(self.bot.coc, valid_tags[0])
        
                # Update UI to reflect manual entry success
                if player_select:
                    d_player_select.disabled = True
                    d_player_select.placeholder = f"✅ Player tag is provided in chat"
        
                    await msg.edit(components=d_player_select)
        
            # Handle Account Selection via Dropdown
            else:
                player = await fetch_player(self.bot.coc, action_result.ctx.values[0])
        
                d_player_select.disabled = True
                d_player_select.placeholder = f"✅ {player.name} ({player.tag}) is selected"
        
                await action_result.ctx.edit_origin(components=d_player_select)
        
            # Add selected tag to list and save if not already linked
            account_tags.append(player.tag)
            player_links = json.load(open("data/member_tags.json", "r"))
            player_links_reversed = reverse_dict(player_links)
        
            if player.tag not in player_links_reversed:
                player_links.setdefault(str(ctx.author.id), []).append(player.tag)
            break

        # Clan Generation Logic
        embed = ipy.Embed(
            title=f"**Generating Clan Selection**",
            description=f"{get_app_emoji('loading')} The clan selection will be generated in a few seconds.",
            footer=ipy.EmbedFooter(
                text="Feel free to ask for help for any confusions."
            ),
            color=COLOR
        )
        msg = await ctx.channel.send(embeds=[embed])

        # Load clan configurations and package data
        clans_config: dict[str, AllianceClanData] = json.load(open("data/clans_config.json", "r"))
        packages: dict[str, ApplicationPackage] = json.load(open("data/packages.json", "r"))
        package_token = secrets.token_hex(8)
        account_tags = list(set(account_tags))

        normal_clans = [i for i in list(clans_config.keys())]
        random.shuffle(normal_clans)
        
        clan_options = {}
        clan_actionrows = []
        acc_clan = {}
        
        # Filter available clans for each account based on requirements
        for count, account in enumerate(account_tags, start=1):
            player = await fetch_player(self.bot.coc, account)
            hero_sum = 0
            for hero in player.heroes:
                if hero.is_home_base:
                    hero_sum += hero.level

            clan_count = 0
            acc_clan[account] = None
            for key in normal_clans:
                try:
                    value = clans_config[key]
                except KeyError:
                    continue

                # Limit displayed options to 30 clans max
                if clan_count >= 30:
                    break

                # Filter based on clan settings (recruitment open, type, etc.)
                if not value["recruitment"]:
                    continue

                if value["type"] == "FWA":
                    continue

                if value["type"] == "CWL":
                    continue                  

                # Check Town Hall requirements
                if extract_integer(value['requirement']) > player.town_hall:
                    continue
                max_th_str = value.get("maximum_possibleTH")
                if max_th_str and player.town_hall > extract_integer(max_th_str):
                    continue

                # Run specific custom checks (e.g., hero levels, activity stats)
                player_qualification = True
                for check, check_kwargs in value["checks"].items():
                    if "client" in get_func_params(CLAN_CHECKS[check]):
                        check_kwargs["client"] = self.bot.coc

                    check_result = await ipy.utils.maybe_coroutine(CLAN_CHECKS[check], player, **check_kwargs)

                    if not check_result:
                        player_qualification = False
                        break

                if not player_qualification:
                    continue

                clan_count += 1

                # Fetch clan details for display
                clan = await fetch_clan(self.bot.coc, key)
                clan_league = str(clan.war_league).replace("League ", "")

                # 1. Default to 'unavailable' emoji if custom one is missing
                iclan_emoji = ipy.PartialEmoji.from_str(get_app_emoji('unavailable'))
                
                # 2. Try to get the specific clan emoji from config
                if value["emoji"]:
                    # Get the formatted string (<:name:id>) from cache
                    e_str = get_app_emoji(value["emoji"])
                    
                    if "<" in e_str and ">" in e_str:
                        iclan_emoji = ipy.PartialEmoji.from_str(e_str)

                capital_level = clan.capital_districts[0].hall_level if clan.capital_districts else 0

                option_label = f"{value['name']}"
                if clan.member_count == 50:
                    option_label += " (Full)"

                # Create the selection option for this valid clan
                clan_option = ipy.StringSelectOption(
                    label=option_label,
                    value=f"{key}",
                    description=f"{clan_league} | Level {clan.level} | CH{capital_level} | {value['type']} | {value['requirement']}",
                    emoji=iclan_emoji
                )

                if player.tag not in clan_options.keys():
                    clan_options[player.tag] = [clan_option]
                    continue

                clan_options[player.tag].append(clan_option)

            clan_select_id = f"clan_select|{package_token}|{count}"

            # If no clans are available for the player, disable the dropdown
            if player.tag not in clan_options.keys():
                clan_select = ipy.StringSelectMenu(
                    ipy.StringSelectOption(
                        label="No Clans Available",
                        value="No Clans Available",
                        description="No Clans Available",
                    ),
                    placeholder=f"❌ {player.name} ({player.tag}) is not eligible",
                    custom_id=clan_select_id,
                    disabled=True
                )
                # Send explanatory messages to the user
                dummy_msg = "."
                await ctx.send(dummy_msg)
                not_eligible_msg = "Sorry, at this moment you don't meet the minimum requirements to enter one of our clans. You might be either lacking Town Hall level or have rushed heroes."
                await ctx.send(not_eligible_msg)

            else:
                # Create the functional dropdown for valid clan options
                clan_select = ipy.StringSelectMenu(
                    *clan_options[player.tag],
                    placeholder=f"{NUMBER_EMOJIS[count]} Select a clan for {player.name} ({player.tag})",
                    custom_id=clan_select_id,
                )

            clan_actionrow = ipy.ActionRow(clan_select)
            clan_actionrows.append(clan_actionrow)

        # Save the application package (state) to disk
        package = {
            "account_tags": account_tags, "acc_clan": acc_clan, 
            "user": int(ctx.author.id),
            "message_id": int(msg.id), "channel_id": int(ctx.channel.id)
        }
        packages[package_token] = package

        with open("data/packages.json", "w") as file:
            json.dump(packages, file, indent=4)

        # Create Confirmation Buttons
        cancel_id = f"clan_cancel|{package_token}"

        cancel_button = ipy.Button(
            style=ipy.ButtonStyle.DANGER,
            label="Cancel",
            custom_id=str(cancel_id),
            emoji=get_app_emoji('cross')
        )

        confirm_id = f"clan_confirm|{package_token}"

        confirm_button = ipy.Button(
            style=ipy.ButtonStyle.SUCCESS,
            label="Confirm",
            custom_id=str(confirm_id),
            emoji=get_app_emoji('tick')
        )

        button_actionrow = ipy.ActionRow(cancel_button, confirm_button)
        clan_actionrows.append(button_actionrow)

        # Update the message with the final selection UI
        embed = ipy.Embed(
            title=f"**Can you select a clan you would like to apply for each of your account?**",
            description=f"- You can choose the same clan for each of your accounts.\n"
                        f"- In the clan description, `CH` stands for **\"Capital Hall\"**",
            footer=ipy.EmbedFooter(
                text="Feel free to ask for help for any confusions."
            ),
            color=COLOR
        )

        await msg.edit(content=f"{ctx.author.user.mention} Please select a clan!", embeds=[embed],
                        components=clan_actionrows)

def setup(bot):
    """
    Entry point for loading the extension.
    """
    ClanApplication(bot)