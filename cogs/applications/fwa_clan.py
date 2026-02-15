"""
FWA (Farm War Alliance) Application Module.

This extension manages the application workflow specifically for FWA clans.
Unlike competitive clans, FWA applications require strict validation of the player's
base layout to ensure it meets the alliance's farming specifications.

Key Features:
1. Multi-account support (User can apply with up to 2 accounts at once).
2. Mandatory image upload/link handling for FWA base proof.
3. Automated eligibility checks against the minimum Town Hall requirements of FWA clans.
4. Alerts the FWA Representative role upon successful submission.

Dependencies:
    - interactions (Discord interactions)
    - validators (URL validation for image links)
    - core (Internal utilities, models, configuration)
"""

import interactions as ipy
from datetime import datetime
import asyncio
import validators
import secrets
import json
import copy
import coc

# Explicit imports for cleaner namespace management
from core.models import *
from core.utils import *
# Note: core.models was imported twice in the original; kept one.
from core import server_setup as sc

class FwaApplication(ipy.Extension):
    """
    Manages the interactive components and logic for the FWA Clan Application system.
    """

    def __init__(self, bot: ipy.Client):
        """
        Initialize the extension.

        Args:
            bot (ipy.Client): The main bot instance.
        """
        self.bot = bot

    @ipy.component_callback("fwa_start_button")
    async def apply_fwa(self, ctx: ipy.ComponentContext):
        """
        Callback for the 'Start FWA Application' button.

        Initiates a multi-step interview process:
        1. Verify applicant identity.
        2. Ask for the number of accounts (1 or 2).
        3. For each account:
           a. Get Player Tag (via chat or linked account selection).
           b. Get FWA Base Screenshot (via attachment or URL).
        4. Validate eligibility (Min Town Hall).
        5. Submit summary to FWA Representatives.

        Args:
            ctx (ipy.ComponentContext): The context of the button interaction.
        """
        member = ctx.author

        # Identity Verification:
        # Ensure that the user clicking the button is the owner of the ticket.
        if extract_integer(ctx.channel.topic) != int(member.id) and \
                extract_alphabets(member.username) != ctx.channel.name.split("┃")[1]:
            await ctx.send(f"{get_app_emoji('error')} Only the applicant of this channel can start the interview!",
                           ephemeral=True)
            return

        # Defer interaction to prevent timeout
        await ctx.defer(ephemeral=True)
      
        # --- Internal Helper Functions ---
        async def check(event: ipy.events.Component):
            """Ensure only the applicant interacts with the components."""
            if int(event.ctx.author.id) == int(ctx.author.id):
                return True
            await event.ctx.send(f"{get_app_emoji('error')} You cannot interact with other user's components.", ephemeral=True)
            return False

        async def msg_check(event: ipy.events.MessageCreate):
            """Ensure messages come from the applicant in the correct channel."""
            if not event.message.channel.id or not event.message.author.id:
                return False
            if int(event.message.author.id) == int(ctx.author.id) and \
                    int(event.message.channel.id) == int(ctx.channel.id):
                return True
            return False

        # --- Step 1: Account Quantity Selection ---
        acc_images = {}
        account_tags = []
        jump_url = ctx.message.jump_url if ctx.message else ""

        embed = ipy.Embed(
            title=f"**With how many account do you want to apply?**",
            description=f"- Choose the number of accounts you will be applying with using the select menu.\n"
                        f"- Go to this [message]({jump_url}) and click **\"Human Support\"** button for help.",
            footer=ipy.EmbedFooter(
                text="Feel free to ask for help for any confusions."
            ),
            color=COLOR
        )

        account_options = [
            ipy.StringSelectOption(label="1", value="1"),
            ipy.StringSelectOption(label="2", value="2"),
        ]
        account_select = ipy.StringSelectMenu(
            *account_options,
            placeholder="#️⃣ Select number of accounts here",
            custom_id="account_select"
        )

        msg = await ctx.channel.send(embeds=[embed], components=account_select)

        # Wait for user to select the number of accounts
        while True:
            try:
                res: ipy.ComponentContext = (await self.bot.wait_for_component(
                    components=account_select, check=check, messages=int(msg.id), timeout=180)).ctx
            except asyncio.TimeoutError:
                raise ComponentTimeoutError(message=msg)
            break

        # Lock the selection UI
        account_select = ipy.StringSelectMenu(
            *account_options,
            placeholder=f"✅ {res.values[0]} account(s) is/are selected",
            disabled=True,
            custom_id="account_select"
        )
        await res.edit_origin(components=[account_select])

        # --- Pre-fetch Linked Accounts for Convenience ---
        player_links = json.load(open("data/member_tags.json", "r"))
        player_select = None
        d_player_select = None
        player = None
        player_options = {}
        
        # Check if user has linked accounts and validate them against API
        for tag in copy.deepcopy(player_links.get(str(ctx.author.id), [])):
            try:
                player = await fetch_player(self.bot.coc, tag)
            except coc.errors.NotFound:
                player_links[str(ctx.author.id)].remove(tag)
                continue

            townhall_emoji = ipy.PartialEmoji.from_str(get_app_emoji(f"Townhall{player.town_hall}"))

            player_options[player.tag] = ipy.StringSelectOption(
                label=f"{player.name} ({player.tag})",
                value=player.tag,
                description=f"{player.role} of {player.clan}" if player.clan else "Not in a clan",
                emoji=townhall_emoji
            )

        if player_options:
            player_select = ipy.StringSelectMenu(
                *player_options.values(),
                placeholder="👤 Apply with your linked accounts",
                custom_id="player_apply_select"
            )
            d_player_select = copy.deepcopy(player_select)

        # --- Step 2: Iterate through each account (1 or 2 times) ---
        for i in range(1, int(res.values[0]) + 1):
            
            # --- 2a. Request Player Tag ---
            embed = ipy.Embed(
                title=f"**Can you kindly provide the tag of your {NUMBER_DICT[i]} account?**",
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

                done, pending = await asyncio.wait(wait_tasks, return_when=asyncio.FIRST_COMPLETED)
                finished: asyncio.Task = list(done)[0]

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

                if action_name == "message":
                    # Handle manual tag entry via chat
                    valid_tags = await extract_tags(self.bot.coc, action_result.message.content)
                    if not valid_tags:
                        if fails == 3:
                            await msg.edit(embed=FAIL_EMBED, components=FWA_RESTART_BUTTON)
                            raise asyncio.exceptions.CancelledError

                        try:
                            await ctx.send(f"{get_app_emoji('error')} Please provide a valid tag in the chat.", ephemeral=True)
                        except ipy.errors.HTTPException:
                            await ctx.channel.send(f"{get_app_emoji('error')} Please provide a valid tag in the chat.",
                                                   ephemeral=True)
                        fails += 1
                        continue

                    player = await fetch_player(self.bot.coc, valid_tags[0])

                    if player_select:
                        d_player_select.disabled = True
                        d_player_select.placeholder = f"✅ Player tag is provided in chat"
                        await msg.edit(components=d_player_select)

                else:
                    # Handle tag selection via dropdown
                    player = await fetch_player(self.bot.coc, action_result.ctx.values[0])
                    d_player_select.disabled = True
                    d_player_select.placeholder = f"✅ {player.name} ({player.tag}) is selected"
                    await action_result.ctx.edit_origin(components=d_player_select)

                # Store the valid tag and link it if new
                account_tags.append(player.tag)
                player_links = json.load(open("data/member_tags.json", "r"))
                player_links_reversed = reverse_dict(player_links)

                if player.tag not in player_links_reversed:
                    player_links.setdefault(str(ctx.author.id), []).append(player.tag)
                break

            # --- 2b. Request FWA Base Screenshot ---
            embed = ipy.Embed(
                title=f"**Can you kindly send a screenshot of the FWA base of your {NUMBER_DICT[i]} account?**",
                description=f"- Please upload the screenshot as an attachment or send it as image URL.\n"
                            f"- This section is **compulsory**, and the base must be FWA base currently activated in your war base!\n"
                            f"- Go to this [message]({jump_url}) and click **\"Human Support\"** button for help.",
                footer=ipy.EmbedFooter(
                    text="Feel free to ask for help for any confusions."
                ),
                color=COLOR
            )

            # Button to help users find FWA base layouts
            base_button = ipy.Button(
                style=ipy.ButtonStyle.LINK,
                label="Get FWA Base",
                url="https://discord.com/channels/1167707509813940245/1336857708996988938",
                emoji=ipy.PartialEmoji(name="🔨")
            )

            msg = await ctx.channel.send(embeds=[embed], components=base_button)

            fails = 0
            while True:
                try:
                    res: ipy.events.MessageCreate = await self.bot.wait_for(
                        'on_message_create', checks=msg_check, timeout=600
                    )
                except asyncio.TimeoutError:
                    raise ComponentTimeoutError(message=msg)

                # Check for direct file attachment
                if res.message.attachments:
                    acc_images[player.tag] = res.message.attachments[0].url
                    break

                # Check for image URL in text
                if not validators.url(res.message.content) or not await is_url_image(res.message.content):
                    if fails == 3:
                        await msg.edit(embed=FAIL_EMBED, components=FWA_RESTART_BUTTON)
                        raise asyncio.exceptions.CancelledError
                    try:
                        await ctx.send(f"{get_app_emoji('error')} Your response must contain an attachment or a image link.",
                                       ephemeral=True)
                    except ipy.errors.HTTPException:
                        await ctx.channel.send(
                            f"{get_app_emoji('error')} Your response must contain an attachment or a image link.",
                            ephemeral=True)
                    fails += 1
                    continue

                acc_images[player.tag] = res.message.content
                break

        # --- Step 3: Finalize and Save Data ---
        with open("data/member_tags.json", "w") as file:
            json.dump(player_links, file, indent=4)

        packages = json.load(open("data/packages.json", "r"))
        package_token = secrets.token_hex(8)
        package = {"acc_images": acc_images}
        packages[package_token] = package

        with open("data/packages.json", "w") as file:
            json.dump(packages, file, indent=4)

        # --- Step 4: Eligibility Check and Summary Generation ---
        embed = ipy.Embed(
            title=f"**Application Summary**",
            description=f"**User Tag:** {ctx.author.username}\n"
                        f"**User ID:** {ctx.author.id}\n"
                        f"**Channel:** {ctx.channel.mention}\n"
                        f"**Joined at:** {ctx.author.joined_at.format(ipy.TimestampStyles.LongDate)}\n"
                        f"**Applied at:** {ipy.Timestamp.fromdatetime(datetime.utcnow()).format(ipy.TimestampStyles.LongDate)}",
            footer=ipy.EmbedFooter(
                text="Applied Time"
            ),
            timestamp=ipy.Timestamp.utcnow(),
            color=COLOR
        )

        # Determine Minimum FWA Town Hall Requirement from config
        clans_config: dict[str, AllianceClanData] = json.load(open("data/clans_config.json", "r"))
        fwa_reqs = []
        for value in clans_config.values():
            if value["type"] != "FWA":
                continue
            fwa_reqs.append(extract_integer(value["requirement"]))
        
        min_fwa_req = min(fwa_reqs) if fwa_reqs else 13 # Default fallback

        account_tags = list(set(account_tags))
        player_options = []
        player_summary = ""
        
        # Filter eligible accounts and build summary
        for account_tag in account_tags:
            player = await fetch_player(self.bot.coc, account_tag)

            if player.town_hall < min_fwa_req:
                continue

            townhall_emoji = ipy.PartialEmoji.from_str(get_app_emoji(f"Townhall{player.town_hall}"))
            formatted_tag = player.tag[1:]
            player_url = f"https://cc.fwafarm.com/cc_n/member.php?tag=%23{formatted_tag}"
            
            th_icon = get_app_emoji(f"Townhall{player.town_hall}")
            player_summary += f"{th_icon}[{player.name} ({player.tag})]({player.share_link}) ({player_url}) \n"
            if len(account_tags) == 1:
                continue

            player_option = ipy.StringSelectOption(
                label=f"{player.name} ({player.tag})",
                description=f"{player.role} of {player.clan}" if player.clan else "Not in a clan",
                value=player.tag,
                emoji=townhall_emoji
            )
            player_options.append(player_option)

        # If eligible accounts exist, add them to the summary
        if player_summary:
            embed.add_field(
                name=f"Applicant Accounts",
                value=player_summary,
                inline=False
            )
        else:
            # If no accounts meet the TH requirement, deny the application immediately
            embed = ipy.Embed(
                title=f"**Application Denied**",
                description=f"{get_app_emoji('error')} We are sorry that you are **not eligible** for FWA clans. The "
                            f"minimum townhall to join a FWA clan is `TH{min_fwa_req}`.\n",
                footer=ipy.EmbedFooter(
                    text="Applied Time"
                ),
                timestamp=ipy.Timestamp.utcnow(),
                color=COLOR
            )
            await ctx.channel.send(embed=embed)
            return

        # Use dynamic config for FWA Rep role notification
        config: sc.GuildConfig = sc.get_config(ctx.guild.id)
        
        await ctx.channel.send(LINE_URL)
        await ctx.channel.send(f"<@&{config.FWA_REP_ROLE}>", embeds=[embed])
        await ctx.channel.send(LINE_URL)

        try:
            await ctx.send(f"{get_app_emoji('success')} **Thank you** for applying, please wait patiently for the clan leaders!",
                           ephemeral=True)
        except ipy.errors.HTTPException:
            pass

def setup(bot: ipy.Client):
    """
    Entry point for loading the extension.
    """
    FwaApplication(bot)