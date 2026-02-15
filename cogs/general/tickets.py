"""
Ticket Management & Lifecycle Module.

This extension orchestrates the core functionality of the ticketing system.
It is divided into two main components:
1.  **TicketManager:** A static utility class responsible for the logic of creating tickets.
    It handles dynamic category resolution, permission overwrites, channel naming conventions,
    and the initialization of application-specific embeds.
2.  **TicketCommands:** The interface for users and staff to interact with tickets.
    It includes commands to create, move, and delete tickets, as well as background tasks
    to enforce inactivity timeouts and auto-deletion policies.

Dependencies:
    - interactions (Discord interactions and permissions)
    - core (Server configuration, models, and utilities)
    - datetime (Time tracking for inactivity)
"""

import asyncio
import calendar
import copy
import json
import interactions as ipy
from core import server_setup as sc
from datetime import datetime, timedelta, timezone

# Import configuration data and utilities
from core.server_setup import *
from core.utils import *
from core.models import *
from core.emojis_manager import *

# --- Dynamic Permission Check ---
def has_roles(*role_keys):
    """
    Custom decorator to check if a user has specific roles defined in the server config.
    
    Args:
        *role_keys: Strings representing attribute names in GuildConfig (e.g., "MODERATOR_ROLE").
    """
    async def check(ctx: ipy.SlashContext):
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

class TicketManager:
    """
    Static manager for handling the creation and setup of new ticket channels.
    """
    
    @staticmethod
    async def create_ticket(ctx: ipy.BaseContext, member: ipy.Member, ticket_type: str, bot: ipy.Client):
        """
        Creates a new ticket channel for a user based on the specified type.

        This method performs several key actions:
        1. Validates the ticket type against `APPLY_DATA`.
        2. Resolves the correct Discord Category ID dynamically from `server_setup`.
        3. Checks if the user already has an open ticket to prevent spam.
        4. Calculates permission overwrites (Member + Bot + Staff).
        5. Creates the text channel and initializes the specific application flow (Embeds/Buttons).

        Args:
            ctx (ipy.BaseContext): The context triggering creation (SlashCommand or Button).
            member (ipy.Member): The user for whom the ticket is being created.
            ticket_type (str): The key identifying the type (e.g., 'clan', 'staff', 'support').
            bot (ipy.Client): The bot instance.

        Returns:
            ipy.GuildText: The created channel object, or None if creation failed.
        """
        ticket_type_key = ticket_type.lower()
        if ticket_type_key not in APPLY_DATA:
            raise ValueError(f"Invalid ticket type: {ticket_type}")

        data = APPLY_DATA[ticket_type_key]
        member_name = extract_alphabets(member.username)
        
        # --- Dynamic Category Logic ---
        # Fetch the guild configuration to determine where to place this ticket.
        config: sc.GuildConfig = sc.get_config(ctx.guild.id)
        resolved_category_ids = []
        
        # APPLY_DATA maps ticket types to config attribute names (e.g., 'CLAN_TICKETS_CATEGORY')
        for category_key in data["categories"]:
            cat_id = getattr(config, category_key, None)
            if cat_id:
                resolved_category_ids.append(cat_id)
        
        if not resolved_category_ids:
            await ctx.send(f"{get_app_emoji('error')} Configuration Error: No categories defined for {ticket_type}.", ephemeral=True)
            return None

        # Check for existing open tickets by this user in the target categories
        for category_id in resolved_category_ids:
            try:
                category = await ctx.guild.fetch_channel(category_id)
            except ipy.errors.NotFound:
                continue

            if not category: 
                continue

            for guild_channel in category.channels:
                if not guild_channel.parent_id or guild_channel.type != ipy.ChannelType.GUILD_TEXT:
                    continue

                # Parse channel name format: "prefix┃username"
                channel_name = guild_channel.name
                if "┃" in guild_channel.name:
                    channel_name = guild_channel.name.split("┃")[1]

                # Check topic for User ID (more reliable) or fallback to name match
                topic_id = extract_integer(guild_channel.topic) if guild_channel.topic else None
                
                if topic_id == int(member.id) or member_name == channel_name:
                    await ctx.send(
                        f"{get_app_emoji('error')} You have already started an interview/ticket in <#{int(guild_channel.id)}>, "
                        f"you **cannot** start another one!", ephemeral=True)
                    return None

        # Create ticket in the primary resolved category
        main_category_id = resolved_category_ids[0]
        
        # Fetch base overwrites (Staff roles) and add the specific user
        channel_overwrites = await fetch_overwrites(bot, main_category_id)
        channel_overwrites.append(
            ipy.PermissionOverwrite(
                id=member.id,
                type=ipy.OverwriteType.MEMBER,
                allow=ipy.Permissions.VIEW_CHANNEL | ipy.Permissions.SEND_MESSAGES,
            )
        )

        try:
            channel = await ctx.guild.create_channel(
                name=f"{data['prefix']}┃{member_name}",
                channel_type=ipy.ChannelType.GUILD_TEXT,
                category=main_category_id,
                permission_overwrites=channel_overwrites,
                topic=f"Applicant ID: {member.id}"
            )
        except ipy.errors.HTTPException:
            # Fallback if the username contains illegal characters causing API error
            channel = await ctx.guild.create_channel(
                name=f"{data['prefix']}┃censored_name{random.randint(1000, 9999)}",
                channel_type=ipy.ChannelType.GUILD_TEXT,
                category=main_category_id,
                permission_overwrites=channel_overwrites,
                topic=f"Applicant ID: {member.id}"
            )

        # Register the new ticket in the persistence file
        try:
            open_tickets = json.load(open("data/open_tickets.json", "r"))
        except (FileNotFoundError, json.JSONDecodeError):
            open_tickets = {}

        with open("data/open_tickets.json", "w") as file:
            open_tickets.setdefault(str(member.id), []).append(int(channel.id))
            json.dump(open_tickets, file, indent=4)

        # --- Embed Construction ---
        # Generate the specific welcome embed based on ticket type
        embed = None
        component_actionrows = []

        if ticket_type_key == "champions":
             embed = ipy.Embed(
                title=f"**All For One Champions Trials**",
                description=f"{get_app_emoji('arrow')} 1. You will do a short interview that takes only **2-3 minutes.\n"
                            f"{get_app_emoji('arrow')} 2. Here is how the trial will work: You will temporarily join a clan provide by us.**\n"
                            f"{get_app_emoji('arrow')} 3. We will send you 5 friendly challenges, which you can and should scout before attacking.\n"
                            f"{get_app_emoji('arrow')} 4. Your results will be kept with us and you will be informed if you passed the trial or not within a week.\n"
                            f"{get_app_emoji('arrow')} 5. You can re-take the trial later if you fail, please go through our helpful guides in <#1355914473478684693> for better chances.\n",
                footer=ipy.EmbedFooter(text="Press \"Human Support\" if further supports are needed."),
                color=COLOR
            )
             if 'CHAMPIONS_BANNER_URL' in globals(): embed.set_image(url=CHAMPIONS_BANNER_URL)
        elif ticket_type_key == "coaching":
            embed = ipy.Embed(
                title=f"**All For One Coaching**",
                description=f"{get_app_emoji('arrow')} Please click button bellow to start, a few quick questions will be asked which will help us tailor the coaching to your needs.\n",
                footer=ipy.EmbedFooter(text="Press \"Human Support\" if further supports are needed."),
                color=COLOR
            )
            if 'COACHING_BANNER_URL' in globals(): embed.set_image(url=COACHING_BANNER_URL)
        elif ticket_type_key == "support":
            embed = ipy.Embed(
                title=f"**All For One Support**",
                description=f"{get_app_emoji('arrow')} Please state the reason of the ticket bellow, staff will come as soon as available.\n",
                footer=ipy.EmbedFooter(text="Press \"Human Support\" if further supports are needed."),
                color=COLOR
            )
            if 'SUPPORT_BANNER_URL' in globals(): embed.set_image(url=SUPPORT_BANNER_URL)
        elif ticket_type_key == "partner":
            embed = ipy.Embed(
                title=f"**All For One Partnerships**",
                description=f"{get_app_emoji('arrow')} Please click button bellow to start, a few quick questions will be asked, staff will come as soon as available.\n",
                footer=ipy.EmbedFooter(text="Press \"Human Support\" if further supports are needed."),
                color=COLOR
            )
            if 'PARTNER_BANNER_URL' in globals(): embed.set_image(url=PARTNER_BANNER_URL)
        else:
            # Default Clan/FWA application flow
            embed = ipy.Embed(
                title=f"**All For One Clan Interview**",
                description=f"{get_app_emoji('arrow')} 1. {data['msg']} to start.\n"
                            f"{get_app_emoji('arrow')} 2. You will do a short interview that takes only **2-3 minutes.**\n"
                            f"{get_app_emoji('arrow')} 3. The bot will guide you step by step.\n"
                            f"{get_app_emoji('arrow')} 4. Our staffs are also available for help.\n",
                footer=ipy.EmbedFooter(text="Press \"Human Support\" if further supports are needed."),
                color=COLOR
            )

        # Prepare Buttons (Start Application / Human Support)
        human_support_btn = ipy.Button(
            style=ipy.ButtonStyle.SECONDARY,
            label="Human Support",
            custom_id="support_button",
            emoji=get_app_emoji('error')
        )

        if ticket_type_key == "support":
            component_actionrows = [ipy.ActionRow(human_support_btn)]
        elif ticket_type_key == "staff":
            # Staff applications use a Dropdown menu for position selection
            select_options = []
            try:
                staff_positions = json.load(open("data/trial_config.json", "r")) 
                for option, staff in staff_positions.items():
                    if staff is not None and "application" in staff:
                        label = option if staff["application"] == "True" else f"{option} (Unavailable)"
                    else:
                        label = f"{option} (Unavailable)"
                    select_options.append(ipy.StringSelectOption(label=label, value=option))
                
                component_actionrows = ipy.spread_to_rows(
                    ipy.StringSelectMenu(
                        *select_options,
                        placeholder=f"{data['emoji']} Select the type of application",
                        custom_id=f"{ticket_type_key}_start_menu",
                    ),
                    human_support_btn
                )
            except Exception as e:
                print(f"Error loading staff file: {e}")
                component_actionrows = [ipy.ActionRow(human_support_btn)]
        else:
            # Standard Flow: Start Button + Support Button
            start_btn = ipy.Button(
                style=ipy.ButtonStyle.PRIMARY,
                label="Start Application",
                custom_id=f"{ticket_type_key}_start_button",
                emoji=get_app_emoji('start')
            )
            component_actionrows = [ipy.ActionRow(start_btn, human_support_btn)]

        msg_content = f"{member.user.mention} "
        if ticket_type_key == "support":
            msg_content += "You have successfully created a Support Ticket, please read the embed message!"
        else:
            msg_content += "Thanks for applying to the All For One Family, please read the embed message!"

        await channel.send(msg_content, embeds=[embed], components=component_actionrows)

        return channel

class TicketCommands(ipy.Extension):
    """
    Extension containing slash commands for ticket management (Move, Create, Delete).
    Also handles background tasks for ticket expiration.
    """
    
    def __init__(self, bot):
        self.bot: ipy.Client = bot
        self.auto_delete.start()
    
    # === REMOVED SCOPES=GUILD_IDS ===
    ticket_base = ipy.SlashCommand(name="ticket", description="Ticket utility")

    move_group = ticket_base.group(name="move", description="To move a ticket to another category")

    @move_group.subcommand(sub_cmd_name="after_cwl", sub_cmd_description="Move a clan ticket to after CWL category")
    @has_roles("RECRUITMENT_ROLE", "SERVER_DEVELOPMENT_ROLE", "LEADER_ROLE")
    @ipy.max_concurrency(bucket=ipy.Buckets.CHANNEL, concurrent=1)
    async def ticket_move_after_cwl(self, ctx: ipy.SlashContext):
        """
        Moves the current ticket to the 'After CWL' category.
        Used when an applicant is accepted but will join after the current League season.
        """
        config: sc.GuildConfig = sc.get_config(ctx.guild.id)

        if int(ctx.channel.parent_id) not in [config.CLAN_TICKETS_CATEGORY, config.FWA_TICKETS_CATEGORY]:
            await ctx.send(
                f"{get_app_emoji('error')} Can only move a clan ticket channel that is not already in after CWL category.",
                ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        await ctx.channel.edit(parent_id=config.AFTER_CWL_CATEGORY)
        msg = await ctx.channel.send("*Applicants will join after CWL ends. **Do not** delete this ticket!*")
        await msg.pin()

        await ctx.send(f"{get_app_emoji('success')} Ticket is successfully moved to `After CWL` category!")

    @move_group.subcommand(sub_cmd_name="finish_champions_trial", sub_cmd_description="Move a ticket to the finished champions trials category.")
    @has_roles("SERVER_DEVELOPMENT_ROLE", "CHAMPIONS_TESTER_ROLE")
    @ipy.max_concurrency(bucket=ipy.Buckets.CHANNEL, concurrent=1)
    async def finish_champions_trial(self, ctx: ipy.SlashContext):
        """
        Moves a Champions Trial ticket to the 'Finished' category.
        Indicates the trial phase is over and results are pending or decided.
        """
        config: sc.GuildConfig = sc.get_config(ctx.guild.id)
        if int(ctx.channel.parent_id) not in [config.CHAMPIONS_TRIALS_CATEGORY]:
            await ctx.send(
                f"{get_app_emoji('error')} Can only move a clan ticket channel that is not already in finished champions trials category.",
                ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        await ctx.channel.edit(parent_id=config.CHAMPIONS_TRIALS_FINISHED_CATEGORY)
        msg = await ctx.channel.send("*Applicant finished his champions trial.*")
        await msg.pin()

        await ctx.send(f"{get_app_emoji('success')} Ticket is successfully moved to `finished champions trials` category!")

    @ticket_base.subcommand(sub_cmd_name="create", sub_cmd_description="Create a ticket")
    @has_roles("RECRUITMENT_ROLE", "SERVER_DEVELOPMENT_ROLE", "LEADER_ROLE")
    @ipy.cooldown(bucket=ipy.Buckets.USER, rate=1, interval=5)
    @ipy.slash_option(
        name="member",
        description="A member from this server",
        opt_type=ipy.OptionType.USER,
        required=True,
    )
    @ipy.slash_option(
        name="ticket_type",
        description="Type of ticket to create",
        opt_type=ipy.OptionType.STRING,
        required=True,
        choices=[
            ipy.SlashCommandChoice(name="Clan", value="Clan"),
            ipy.SlashCommandChoice(name="FWA", value="FWA"),
            ipy.SlashCommandChoice(name="Staff", value="Staff"),
            ipy.SlashCommandChoice(name="Champions", value="Champions"),
            ipy.SlashCommandChoice(name="Support", value="Support"), 
            ipy.SlashCommandChoice(name="Coaching", value="Coaching"),  
            ipy.SlashCommandChoice(name="Partner", value="Partner"),       
        ]
    )
    @ipy.slash_option(
        name="hidden",
        description="Make the message hidden?",
        opt_type=ipy.OptionType.BOOLEAN,
    )
    async def ticket_create(self, ctx: ipy.SlashContext, member: ipy.Member, ticket_type: str, hidden: bool = False):
        """
        Manually creates a ticket for a user.
        Useful for staff when a user cannot open a ticket themselves.
        """
        if isinstance(member, str):
            await ctx.send(f"{get_app_emoji('error')} user is not in the server and cannot create a ticket.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        if member.bot:
            await ctx.send(f"{get_app_emoji('error')} You cannot open a ticket for a bot user.", ephemeral=True)
            return

        channel = await TicketManager.create_ticket(ctx, member, ticket_type, self.bot)

        if not channel:
            return

        if ticket_type.lower() == "support":
            await ctx.send(
                f"{get_app_emoji('success')} Channel {channel.mention} is created. Please go there to start your Ticket.",
                ephemeral=True)
        else:
            await ctx.send(
                f"{get_app_emoji('success')} Channel {channel.mention} is created. Please go there to start your interview.",
                ephemeral=True)

        if not hidden:
            embed = ipy.Embed(
                title=f"**{ticket_type} Application Ticket**",
                description=f"`{ctx.author}` has opened a {ticket_type} ticket for you! You can start your application "
                            f"there! If you think this was a mistake, please kindly ask a recruiter to close the ticket for "
                            f"you, thanks!",
                footer=ipy.EmbedFooter(
                    text=f"Created at",
                ),
                timestamp=ipy.Timestamp.utcnow(),
                color=COLOR
            )

            channel_url = f"https://discord.com/channels/{channel.guild.id}/{channel.id}"
            channel_button = ipy.Button(
                style=ipy.ButtonStyle.URL,
                label="Go to Ticket",
                emoji=ipy.PartialEmoji(name="🔗"),
                url=channel_url
            )
            try:
                await ctx.channel.send(f"{member.mention}", embed=embed, components=channel_button)
            except Exception:
                pass


    @ipy.Task.create(ipy.IntervalTrigger(minutes=1))
    async def auto_delete(self):
            """
            Background Task: Enforces deletion timers.
            
            Checks `data/ticket_data.json` every minute. If a ticket's deletion time
            has passed, it deletes the channel and notifies the user via DM.
            """
            try:
                with open("data/ticket_data.json", "r") as file:
                    ticket_data = json.load(file)
            except (FileNotFoundError, json.JSONDecodeError):
                return
    
            if not ticket_data:
                return
    
            now = datetime.now(timezone.utc)
            data_changed = False 
    
            # Iterate through a copy to safely modify the original dictionary
            for key, value in copy.deepcopy(ticket_data).items():
                try:
                    delete_date = datetime(
                        value["date"][0], value["date"][1], value["date"][2],
                        value["date"][3], value["date"][4], tzinfo=timezone.utc
                    )
    
                    if delete_date > now:
                        continue
    
                    channel_id, member_id = key.split("|")
                    
                    try:
                        channel = await self.bot.fetch_channel(channel_id)
                    except (ipy.NotFound, ipy.HTTPException):
                        # Channel already gone, cleanup data
                        if key in ticket_data:
                            del ticket_data[key]
                            data_changed = True
                        continue
    
                    if channel:
                        try:
                            author = await self.bot.fetch_user(value['author'])
                            await channel.delete(reason=f"Inactive for set hours.\nUser: {author} {author.id}")
                        except (ipy.NotFound, ipy.Forbidden):
                            pass
    
                    # Notify user about deletion
                    try:
                        user = await self.bot.fetch_user(member_id)
                        apply_link_button = ipy.Button(
                            label="Reapply",
                            emoji=ipy.PartialEmoji(name="🔗"),
                            style=ipy.ButtonStyle.URL,
                            url="https://discord.com/channels/1167707509813940245/1167708046701633586"
                        )
                        await user.send(
                            f"<:Error:1318281185016680498> You have opened a ticket in All For One server, but "
                            f"due to **inactivity**, it has been deleted. If you wish to continue the "
                            f"application please reapply by clicking on the link below.", 
                            components=apply_link_button
                        )
                    except Exception:
                        pass
    
                    if key in ticket_data:
                        del ticket_data[key]
                        data_changed = True
    
                except Exception as e:
                    print(f"[AutoDelete Error] Failed processing key {key}: {e}")
                    continue
    
            if data_changed:
                with open("data/ticket_data.json", "w") as file:
                    json.dump(ticket_data, file, indent=4)   
  
    @ticket_base.subcommand(sub_cmd_name="delete", sub_cmd_description="Delete a ticket")
    @has_roles("SERVER_DEVELOPMENT_ROLE", "RECRUITMENT_ROLE")
    @ipy.max_concurrency(bucket=ipy.Buckets.CHANNEL, concurrent=1)
    @ipy.slash_option(
        name="hours_inactive",
        description="Hours to wait before deleting the ticket (3h - 24h)",
        opt_type=ipy.OptionType.INTEGER,
        required=False,
        max_value=24,
        min_value=3
    )
    async def ticket_delete(self, ctx: ipy.SlashContext, hours_inactive: int = 0):
        """
        Deletes a ticket.
        
        Options:
        - Immediate: Deletes after a confirmation prompt.
        - Scheduled (`hours_inactive`): Sets a timer. If no message is sent in the channel
          for X hours, the ticket is auto-deleted.
        """
        await ctx.defer(ephemeral=True)
        config: sc.GuildConfig = sc.get_config(ctx.guild.id)
        
        # Dynamically build deletable categories
        valid_categories = [
            config.CLAN_TICKETS_CATEGORY, config.STAFF_APPLY_CATEGORY,
            config.AFTER_CWL_CATEGORY, config.FWA_TICKETS_CATEGORY,
            config.STAFF_TRIALS_CATEGORY, config.CHAMPIONS_TRIALS_CATEGORY, config.CHAMPIONS_TRIALS_FINISHED_CATEGORY,
            config.COACHING_SESSIONS_CATEGORY, config.SUPPORT_TICKETS_CATEGORY, config.PARTNER_TICKETS_CATEGORY
        ]
        
        if int(ctx.channel.parent_id) not in valid_categories:
            await ctx.send(f"{get_app_emoji('error')} Only interview/application channels can be deleted.", ephemeral=True)
            return

        if hours_inactive:
            delete_date = datetime.now(timezone.utc) + timedelta(hours=hours_inactive)
            delete_date_unix = f"<t:{calendar.timegm(delete_date.timetuple())}:R>"

            # Identify the ticket owner to store in the schedule
            for overwrite in ctx.channel.permission_overwrites:
                if overwrite.type == ipy.OverwriteType.MEMBER:
                    member = await ctx.guild.fetch_member(overwrite.id)

                    if int(member.id) == extract_integer(ctx.channel.topic):
                        break

                    if extract_alphabets(member.username) == ctx.channel.name.split("┃")[1]:
                        break
            else:
                await ctx.send(
                    f"{get_app_emoji('error')} Unable to get the applicant of this ticket. However, `/ticket delete` without "
                    f"using **inactive_hours** would still work!", ephemeral=True)
                return

            cancel_button = ipy.Button(
                style=ipy.ButtonStyle.DANGER,
                label="Cancel",
                custom_id="delete_cancel_button",
                emoji=get_app_emoji('cross')
            )

            embed = ipy.Embed(
                title="**Ticket Deletion Warning**",
                description=f"This ticket will be **deleted** {delete_date_unix} due to inactivity. "
                            f"Send any message in the channel to cancel the deletion! Any recruitment "
                            f"staff can also cancel this action manually!",
                footer=ipy.EmbedFooter(
                    text=f"Command ran by: {ctx.author} | {ctx.author.id}",
                ),
                color=COLOR
            )

            msg = await ctx.channel.send(f"{member.mention} ", embed=embed, components=cancel_button)

            await ctx.send(f"{get_app_emoji('success')} Deletion timer is set.", ephemeral=True)

            date_data = [delete_date.year, delete_date.month, delete_date.day, delete_date.hour, delete_date.minute]
            ticket_data = json.load(open("data/ticket_data.json", "r"))
            ticket_data[f"{ctx.channel.id}|{member.id}"] = {"message": int(msg.id), "date": date_data,
                                                            "author": int(ctx.author.id)}

            with open("data/ticket_data.json", "w") as file:
                json.dump(ticket_data, file, indent=4)
            return

        # Immediate Deletion Flow
        cancel_button = ipy.Button(
            style=ipy.ButtonStyle.DANGER,
            label="Cancel",
            custom_id="cancel",
            emoji=get_app_emoji('cross')
        )
        confirm_button = ipy.Button(
            style=ipy.ButtonStyle.SUCCESS,
            label="Confirm",
            custom_id="confirm",
            emoji=get_app_emoji('tick')
        )
        button_actionrow = ipy.ActionRow(cancel_button, confirm_button)

        msg = await ctx.send("Are you sure that you would like to **delete** the ticket?\n\n"
                             "*Note: you cannot undo this action.*",
                             components=button_actionrow, ephemeral=True)

        try:
            res: ipy.ComponentContext = (
                await self.bot.wait_for_component(components=button_actionrow, messages=int(msg.id), timeout=180)).ctx
        except asyncio.TimeoutError:
            raise ComponentTimeoutError(message=msg)

        if res.custom_id == "confirm":
            await res.edit_origin(components=ipy.utils.misc_utils.disable_components(button_actionrow))

            await ctx.send(f"get_app_emoji('loading') The ticket will be deleted in 5 seconds.", ephemeral=True)
            await asyncio.sleep(5)

            await ctx.channel.delete(reason=f"Manual deletion.\nUser: {ctx.author} ({ctx.author.id})")

        if res.custom_id == "cancel":
            await res.edit_origin(components=ipy.utils.misc_utils.disable_components(button_actionrow))

            await ctx.send(f"{get_app_emoji('success')} The action has been canceled.", ephemeral=True)

    @ipy.component_callback("delete_cancel_button")
    async def delete_cancel_button(self, ctx: ipy.ComponentContext):
        """
        Callback to cancel a pending scheduled deletion.
        Checks if the user has appropriate staff permissions.
        """
        config = sc.get_config(ctx.guild.id)
        author_roles = [int(role.id) for role in ctx.author.roles]
        
        # Use dynamic roles
        allowed_roles = [config.RECRUITMENT_ROLE, config.SERVER_DEVELOPMENT_ROLE, config.LEADER_ROLE]
        
        if not any(role_id in author_roles for role_id in allowed_roles):
            await ctx.send(f"{get_app_emoji('error')} You do not have permission to cancel this action!", ephemeral=True)
            return

        ticket_data = json.load(open("data/ticket_data.json", "r"))

        for key, data in copy.deepcopy(ticket_data).items():
            if int(ctx.message.id) == data["message"]:
                del ticket_data[key]

        with open("data/ticket_data.json", "w") as file:
            json.dump(ticket_data, file, indent=4)

        await ctx.message.delete()
        await ctx.channel.send(
            f"{get_app_emoji('success')} Ticket successfully **resumed**...\n\n*Ticket deletion canceled by `{ctx.author}`*")

    @ipy.listen(ipy.events.MessageCreate)
    async def on_message_create(self, event: ipy.events.MessageCreate):
        """
        Global listener for message creation.
        
        1. Resets inactivity timers: If a message is sent in a channel pending deletion, 
           the timer is cancelled and the ticket resumes.
        2. Gatekeeper Logic: Grants view permissions to specific Clan Gatekeepers (Recruiters)
           if their role is mentioned in the ticket.
        """
        msg = event.message
        if not msg.guild: return
        
        ticket_data: dict = json.load(open("data/ticket_data.json", "r"))

        # Check if this channel has a pending deletion timer associated with this user
        if ticket_data.get(f"{msg.channel.id}|{msg.author.id}"):
            message = await msg.channel.fetch_message(ticket_data[f"{msg.channel.id}|{msg.author.id}"]["message"])
            try:
                await message.delete()
            except AttributeError:
                pass

            await msg.channel.send(f"{get_app_emoji('success')} Ticket successfully **resumed**...")

            del ticket_data[f"{msg.channel.id}|{msg.author.id}"]

            with open("data/ticket_data.json", "w") as file:
                json.dump(ticket_data, file, indent=4)

        # Gatekeeper Permission Logic
        mentioned_roles: set = {int(role.id) async for role in msg.mention_roles}
        config: sc.GuildConfig = sc.get_config(msg.guild.id)
        
        valid_categories = [config.CLAN_TICKETS_CATEGORY, config.AFTER_CWL_CATEGORY, config.FWA_TICKETS_CATEGORY]
        
        if mentioned_roles and int(msg.channel.parent_id) in valid_categories and not msg.author.bot:
            clans_config: dict[str, AllianceClanData] = json.load(open("data/clans_config.json", "r"))
            clan_roles: set = {value["gk_role"] for value in clans_config.values()}
            
            # If a Gatekeeper role is mentioned, grant its members access to the ticket
            for role_id in mentioned_roles.intersection(clan_roles):
                clan_role = await msg.guild.fetch_role(role_id)
                for member in clan_role.members:
                    member_roles = [int(role.id) for role in member.roles]
                    if config.RECRUITMENT_ROLE not in member_roles:
                        continue

                    await msg.channel.add_permission(
                        target=member.id, type=ipy.OverwriteType.MEMBER,
                        allow=ipy.Permissions.SEND_MESSAGES | ipy.Permissions.VIEW_CHANNEL
                    )

    @ipy.listen(ipy.events.Startup)
    async def on_start(self):
        print("➤ Ticket commands loaded")
