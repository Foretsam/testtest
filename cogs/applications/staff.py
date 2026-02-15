"""
Staff Application & Management Module.

This extension manages the recruitment and trial process for server staff.
It provides two main classes:
1. StaffApplication: Handles the user-facing side of applying (Modals, Form submission).
2. StaffCommands: Provides administrative commands to manage staff positions,
   start/end trials, and edit application questions dynamically.

Key Features:
- Dynamic form generation based on `data/trial_config.json`.
- Interactive modals for applicants to submit responses.
- Automated trial management (start dates, end dates, notifications).
- Role-based access control for administrative commands.

Dependencies:
    - interactions (Discord interactions)
    - core (Internal utilities, server setup, emojis)
"""

import interactions as ipy
import difflib
import json
import re
from datetime import datetime, timedelta, timezone

from core.utils import *
from core import server_setup as sc
from core.emojis_manager import get_app_emoji

# ==========================================
# CHECKS & UTILS
# ==========================================

def has_staff_roles(*role_keys):
    """
    Custom check to validate if a user has one of the allowed roles 
    defined in the server configuration.
    
    This abstracts role ID fetching, allowing the bot to work across different
    server configurations without hardcoding IDs.

    Args:
        *role_keys: Strings representing the attribute names in GuildConfig (e.g., "MODERATOR_ROLE").
    
    Usage: @has_staff_roles("MODERATOR_ROLE", "ADMINISTRATION_ROLE")
    """
    async def check(ctx: ipy.SlashContext):
        if not ctx.guild_id: 
            return False
            
        config = sc.get_config(ctx.guild_id)
        allowed_ids = []
        
        for key in role_keys:
            # Fetch the role ID from the config object using the attribute name
            role_id = getattr(config, key, None)
            if role_id:
                allowed_ids.append(int(role_id))
        
        if not allowed_ids:
            # If no roles are configured, fail safe (deny access)
            return False
            
        return any(int(role.id) in allowed_ids for role in ctx.author.roles)
    
    return ipy.check(check)

# ==========================================
# EXTENSIONS
# ==========================================

class StaffApplication(ipy.Extension):
    """
    Handles the user-facing application process for staff positions.
    """

    def __init__(self, bot: ipy.Client):
        self.bot = bot

    @ipy.component_callback("staff_start_menu")
    async def apply_staff(self, ctx: ipy.ComponentContext):
        """
        Callback for the Staff Position Selection Menu.

        Triggered when a user selects a position to apply for. It validates the user,
        checks if applications for that position are open, and presents a Modal form.

        Args:
            ctx (ipy.ComponentContext): The context of the menu interaction.
        """
        # Identity Verification:
        # Validate that the user interacting is the ticket owner.
        topic_id = extract_integer(ctx.channel.topic) if ctx.channel.topic else 0
        channel_user_name = ctx.channel.name.split("┃")[1] if "┃" in ctx.channel.name else ""
        
        if topic_id != int(ctx.author.id) and extract_alphabets(ctx.author.username) != channel_user_name:
            await ctx.send(f"{get_app_emoji('error')} Only the applicant of this channel can start the interview!",
                           ephemeral=True)
            return

        if not ctx.values:
            return

        staff_name = ctx.values[0]
        # Encode space to '0' for custom_id compatibility (spaces are often problematic)
        modified_name = staff_name.replace(" ", "0")
        
        try:
            trial_config = json.load(open("data/trial_config.json", "r"))
        except FileNotFoundError:
            await ctx.send(f"{get_app_emoji('error')} Configuration file not found.", ephemeral=True)
            return

        # Check if the position is currently accepting applications
        if not trial_config.get(staff_name) or trial_config[staff_name]["application"] == "False":
            await ctx.send(f"{get_app_emoji('error')} Sorry the application of `{staff_name}` is currently closed.",
                           ephemeral=True)
            return

        # Construct the Modal
        modal = ipy.Modal(title=f"{staff_name} Form", custom_id=f"{modified_name}_staff_modal")

        # Dynamically add input fields based on the config for this staff position
        for count, question in enumerate(trial_config[staff_name]["questions"]):
            # Note: Discord Modals have a limit of 5 components.
            modal.add_components(
                ipy.InputText(
                    label=question["question"],
                    max_length=300 if question["type"] == "Paragraph" else 100,
                    custom_id=f"textinput{count}",
                    placeholder=question["placeholder"],
                    style=ipy.TextStyles.PARAGRAPH if question["type"] == "Paragraph" else ipy.TextStyles.SHORT
                )
            )

        await ctx.send_modal(modal)

    @ipy.modal_callback(re.compile(r"^\w+_staff_modal$"))
    async def staff_modal(self, ctx: ipy.ModalContext, **responses):
        """
        Callback for the Staff Application Modal submission.

        Processes the form data, posts a summary embed to the ticket,
        and provides administrative buttons (Start/Delay/Deny Trial) to staff.

        Args:
            ctx (ipy.ModalContext): The context of the modal submission.
        """
        try:
            trial_config = json.load(open("data/trial_config.json", "r"))
        except FileNotFoundError:
            return

        # Decode staff name from custom_id
        staff_name = ctx.custom_id.split("_")[0].replace("0", " ")
        staff_emoji = "<:StaffIcon:1318289342736629902>" # TODO: Move to core.emojis_manager

        embed = ipy.Embed(
            title=f"{staff_emoji} **{staff_name} Application Response**",
            description="Below shows the responses written by the applicant, existing "
                        "staff will have a look as soon as possible and take actions accordingly. "
                        "For further discussion, communicate in the channel please.",
            author=ipy.EmbedAuthor(
                name=f"{ctx.author.username}",
                icon_url=ctx.author.avatar.url
            ),
            footer=ipy.EmbedFooter(
                text=f"Applied Time"
            ),
            timestamp=ipy.Timestamp.utcnow(),
            color=COLOR
        )

        # Map responses back to questions
        modal_responses = list(responses.values())
        for count, modal_response in enumerate(modal_responses):
            question_text = trial_config[staff_name]['questions'][count]['question']
            embed.add_field(
                name=f"**{question_text}**",
                value=modal_response,
                inline=False
            )

        # Administrative Action Buttons
        start_button = ipy.Button(
            style=ipy.ButtonStyle.SUCCESS,
            label="Start Trial",
            custom_id=f"start_trial|{staff_name.replace(' ', '0')}",
        )

        delay_button = ipy.Button(
            style=ipy.ButtonStyle.SECONDARY,
            label="Delay Trial",
            custom_id=f"delay_trial|{staff_name.replace(' ', '0')}",
        )

        deny_button = ipy.Button(
            style=ipy.ButtonStyle.DANGER,
            label=f"Deny Trial",
            custom_id=f"deny_trial|{staff_name.replace(' ', '0')}",
        )

        actionrows = [ipy.ActionRow(start_button, delay_button, deny_button)]
        
        # Determine whom to ping (Moderators/Admins) based on server config
        config: sc.GuildConfig = sc.get_config(ctx.guild.id)
        role_pings = []
        if config.MODERATOR_ROLE: role_pings.append(f"<@&{config.MODERATOR_ROLE}>")
        if config.ADMINISTRATION_ROLE: role_pings.append(f"<@&{config.ADMINISTRATION_ROLE}>")
        
        ping_content = " and ".join(role_pings) if role_pings else "Staff"

        # Send summary to the ticket channel
        await ctx.channel.send(LINE_URL)
        await ctx.channel.send(
            ping_content,
            embeds=[embed], components=actionrows
        )
        await ctx.channel.send(LINE_URL)

        # Update channel name with the specific staff position prefix
        raw_prefix = trial_config[staff_name]['prefix']
        staff_prefix = raw_prefix.translate(PREFIX_DICT)
        try:
            await ctx.channel.edit(name=f"{staff_prefix}┃{ctx.author.user.username}")
        except:
            # Fallback if rename fails due to permissions or length
            pass

        await ctx.send(
            f"{get_app_emoji('success')} Your answers are **successfully** submitted. "
            f"Please wait patiently for the moderators and admins to review it.",
            ephemeral=True
        )

class StaffCommands(ipy.Extension):
    """
    Administrative commands for managing the Staff system.
    """
    def __init__(self, bot: ipy.Client):
        self.bot = bot

    staff_base = ipy.SlashCommand(name="staff", description="Staff application utility")

    @staff_base.subcommand(sub_cmd_name="server", sub_cmd_description="Get staff server link")
    @has_staff_roles("RECRUITMENT_ROLE", "SERVER_DEVELOPMENT_ROLE", "ADMINISTRATION_ROLE", "LEADER_ROLE")
    async def staff_server(self, ctx: ipy.SlashContext):
        """
        Retrieves the Staff Server Invite URL from the configuration.
        Restricted to specific staff roles.
        """
        # Fetch Dynamic URL from Config
        config = sc.get_config(ctx.guild.id)
        url = config.STAFF_SERVER_URL
        
        if not url:
            await ctx.send(f"{get_app_emoji('error')} Staff Server URL has not been configured.", ephemeral=True)
        else:
            await ctx.send(url)

    staff_trial_group = staff_base.group(name="trial", description="Start or end a staff trial")
    
    @staff_trial_group.subcommand(sub_cmd_name="end", sub_cmd_description="To end a staff trial")
    @has_staff_roles("ADMINISTRATION_ROLE", "MODERATOR_ROLE", "SERVER_DEVELOPMENT_ROLE")
    @ipy.max_concurrency(bucket=ipy.Buckets.CHANNEL, concurrent=1)
    @ipy.slash_option(
        name="staff_name",
        description="Name of the staff position.",
        opt_type=ipy.OptionType.STRING,
        required=True,
        autocomplete=True,
    )
    async def staff_trial_end(self, ctx: ipy.SlashContext, staff_name: str):
        """
        Manually ends a staff trial for the user in the current channel.
        Removes the trial event from the database and prompts for a vote.
        """
        await ctx.defer(ephemeral=True)

        config: sc.GuildConfig = sc.get_config(ctx.guild.id)

        # Validation: Command must be used in the Active Trials category
        if str(ctx.channel.parent_id) != str(config.STAFF_TRIALS_CATEGORY):
            await ctx.send(f"{get_app_emoji('error')} You can only use this command when there is a on-going trial.", ephemeral=True)
            return

        # Identify the trial subject (member)
        member = None
        for overwrite in ctx.channel.permission_overwrites:
            if overwrite.type == ipy.OverwriteType.MEMBER:
                try:
                    fetched = await ctx.guild.fetch_member(overwrite.id)
                    # Check channel topic or name to verify identity
                    topic_id = extract_integer(ctx.channel.topic) if ctx.channel.topic else 0
                    if int(fetched.id) == topic_id:
                        member = fetched
                        break
                    
                    if extract_alphabets(fetched.username) == ctx.channel.name.split("┃")[1]:
                        member = fetched
                        break
                except:
                    continue
        
        if not member:
            await ctx.send(f"{get_app_emoji('error')} Unable to get the applicant of this channel.", ephemeral=True)
            return

        vote_button = ipy.Button(
            style=ipy.ButtonStyle.SECONDARY,
            label="Start Voting",
            custom_id=f"vote_start_button|{staff_name.replace(' ', '0')}",
            emoji="🗳️"
        )

        embed = ipy.Embed(
            title="**Trial Has Ended**",
            description=f"{member.mention}'s **{staff_name.lower()}** trial has come to an end. "
                        f"The management team will evaluate the activity of the applicant and conduct "
                        f"voting to decide the result of the trial.",
            footer=ipy.EmbedFooter(
                text=f"End Time",
            ),
            timestamp=ipy.Timestamp.utcnow(),
            color=COLOR
        )

        # Remove trial from active events database
        try:
            trial_events = json.load(open("data/trial_events.json", "r"))
            key = f"{ctx.channel.id}|{member.id}"
            if key in trial_events:
                del trial_events[key]
                with open("data/trial_events.json", "w") as file:
                    json.dump(trial_events, file, indent=4)
        except FileNotFoundError:
            pass

        await ctx.channel.send(f"{member.mention} We will inform you about your trial result soon!", embed=embed,
                               components=vote_button)

        await ctx.send(f"{get_app_emoji('success')} Trial has been ended!", ephemeral=True)

    @staff_trial_group.subcommand(sub_cmd_name="start", sub_cmd_description="Start a staff trial")
    @has_staff_roles("ADMINISTRATION_ROLE", "MODERATOR_ROLE", "SERVER_DEVELOPMENT_ROLE")
    @ipy.max_concurrency(bucket=ipy.Buckets.CHANNEL, concurrent=1)
    @ipy.slash_option(
        name="staff_name",
        description="Name of the staff position.",
        opt_type=ipy.OptionType.STRING,
        required=True,
        autocomplete=True,
    )
    @ipy.slash_option(
        name="days",
        description="Duration of the trial (3 - 14 days)",
        opt_type=ipy.OptionType.INTEGER,
        required=True,
        max_value=14,
        min_value=3
    )
    async def staff_trial_start(self, ctx: ipy.SlashContext, staff_name: str, days: int):
        """
        Manually starts a staff trial.
        Calculates the end date, registers the event, and moves the channel to the Trials category.
        """
        await ctx.defer(ephemeral=True)

        config: sc.GuildConfig = sc.get_config(ctx.guild.id)

        # Validation: Command must be used in the Pending category
        if str(ctx.channel.parent_id) != str(config.STAFF_APPLY_CATEGORY):
            await ctx.send(f"{get_app_emoji('error')} You can only use this command when it is in the staff pending category.", ephemeral=True)
            return

        # Calculate End Date
        end_date = datetime.now(timezone.utc) + timedelta(days=days)
        end = f"<t:{int(end_date.timestamp())}:D>"

        # Identify the trial subject
        member = None
        for overwrite in ctx.channel.permission_overwrites:
            if overwrite.type == ipy.OverwriteType.MEMBER:
                try:
                    fetched = await ctx.guild.fetch_member(overwrite.id)
                    topic_id = extract_integer(ctx.channel.topic) if ctx.channel.topic else 0
                    if int(fetched.id) == topic_id:
                        member = fetched
                        break
                    
                    if extract_alphabets(fetched.username) == ctx.channel.name.split("┃")[1]:
                        member = fetched
                        break
                except:
                    continue

        if not member:
            await ctx.send(f"{get_app_emoji('error')} Unable to get the applicant of this channel.", ephemeral=True)
            return

        # Register event in database
        try:
            trial_events = json.load(open("data/trial_events.json", "r"))
        except FileNotFoundError:
            trial_events = {}

        trial_events[f"{ctx.channel.id}|{member.id}"] = {
            "date": [end_date.year, end_date.month, end_date.day, end_date.hour, end_date.minute],
            "action": "end",
            "type": staff_name
        }
        with open("data/trial_events.json", "w") as file:
            json.dump(trial_events, file, indent=4)

        embed = ipy.Embed(
            title="**Trial Has Started**",
            description=f"{member.mention}'s trial for {staff_name.lower()} has started! It will end on {end}, "
                        f"every staff in the management team wishes luck for the applicant!",
            footer=ipy.EmbedFooter(
                text=f"Start Time",
            ),
            timestamp=ipy.Timestamp.utcnow(),
            color=COLOR
        )

        msg = await ctx.channel.send(member.mention, embed=embed)
        await msg.pin()

        # Move channel to trials category
        if config.STAFF_TRIALS_CATEGORY:
            await ctx.channel.edit(parent_id=config.STAFF_TRIALS_CATEGORY, topic=f"Applicant ID: {member.id}\nEnds on {end}")
        else:
            await ctx.send(f"{get_app_emoji('warning')} Staff Trials Category is not configured! Channel was not moved.", ephemeral=True)

        await ctx.send(f"{get_app_emoji('success')} Trial started!", ephemeral=True)

    staff_edit_group = staff_base.group(name="edit", description="Edit staff positions json data")

    @staff_edit_group.subcommand(sub_cmd_name="questions", sub_cmd_description="Edit application questions")
    @has_staff_roles("SERVER_DEVELOPMENT_ROLE")
    async def staff_edit_questions(self, ctx: ipy.SlashContext, staff_name: str, question_index: int,
                                   question_type: str = None):
        """
        Edits the text or type of a specific question for a staff position.
        """
        try:
            trial_config = json.load(open("data/trial_config.json", "r"))
        except FileNotFoundError:
            await ctx.send(f"{get_app_emoji('error')} Config file not found.", ephemeral=True)
            return

        if question_type:
            trial_config[staff_name]["questions"][question_index]["type"] = question_type

            with open("data/trial_config.json", "w") as file:
                json.dump(trial_config, file, indent=4)

        modal = ipy.Modal(
            ipy.ShortText(
                label="Type in the question",
                max_length=45,
                custom_id=f"{staff_name}|{question_index}",
                value=trial_config[staff_name]["questions"][question_index]["question"]
            ),
            ipy.ShortText(
                label="Type in the placeholder",
                max_length=100,
                custom_id=staff_name,
                value=trial_config[staff_name]["questions"][question_index]["placeholder"],
                required=False
            ),
            title=f"Question {question_index + 1} Edit",
            custom_id="staff_questions_edit",
        )
        await ctx.send_modal(modal)

    @ipy.modal_callback("staff_questions_edit")
    async def staff_questions_edit_modal(self, ctx: ipy.ModalContext, **modal_data):
        staff_name, question_index = list(modal_data.keys())[0].split("|")
        trial_config = json.load(open("data/trial_config.json", "r"))
        
        # Responses are in the values
        values = list(modal_data.values())
        trial_config[staff_name]["questions"][int(question_index)]["question"] = values[0]
        trial_config[staff_name]["questions"][int(question_index)]["placeholder"] = values[1]

        with open("data/trial_config.json", "w") as file:
            json.dump(trial_config, file, indent=4)

        await ctx.send(f"{get_app_emoji('success')} Question {int(question_index) + 1} is successfully edited.", ephemeral=True)

    @staff_edit_group.subcommand(sub_cmd_name="application", sub_cmd_description="Edit staff application status")
    @has_staff_roles("SERVER_DEVELOPMENT_ROLE")
    async def staff_edit_application(self, ctx: ipy.SlashContext, staff_name: str, application_status: bool):
        """
        Toggles the ability to apply for a specific staff position (Open/Closed).
        """
        await ctx.defer(ephemeral=True)
        if staff_name == "Other":
            await ctx.send(f"{get_app_emoji('error')} This staff position is not editable!", ephemeral=True)
            return

        try:
            trial_config = json.load(open("data/trial_config.json", "r"))
        except FileNotFoundError:
            return

        trial_config[staff_name]["application"] = str(application_status)

        with open("data/trial_config.json", "w") as file:
            json.dump(trial_config, file, indent=4)

        await ctx.send(f"{get_app_emoji('success')} Staff position application status is successfully edited.",
                       ephemeral=True)

    @staff_base.subcommand(sub_cmd_name="add", sub_cmd_description="Add a staff position")
    @has_staff_roles("SERVER_DEVELOPMENT_ROLE")
    async def staff_add(self, ctx: ipy.SlashContext, staff_name: str, question1: str, question2: str, question3: str,
                        staff_prefix: str):
        """
        Adds a completely new staff position to the configuration.
        """
        await ctx.defer(ephemeral=True)

        try:
            trial_config = json.load(open("data/trial_config.json", "r"))
        except FileNotFoundError:
            trial_config = {}

        questions = []
        for question in [question1, question2, question3]:
            questions.append({"question": question, "placeholder": "", "type": "Paragraph"})

        trial_config[staff_name] = {
            "questions": questions,
            "prefix": staff_prefix,
            "application": "True"
        }

        # Ensure "Other" remains at the end or exists (fallback logic)
        other = trial_config.pop("Other", None)
        if other is not None:
            trial_config["Other"] = other
        else:
            trial_config["Other"] = {
                "questions": [
                    {"question": "Default Question 1", "placeholder": "", "type": "Paragraph"},
                    {"question": "Default Question 2", "placeholder": "", "type": "Paragraph"},
                    {"question": "Default Question 3", "placeholder": "", "type": "Paragraph"}
                ],
                "prefix": "OTHR",
                "application": "False"
            }

        with open("data/trial_config.json", "w") as file:
            json.dump(trial_config, file, indent=4)

        await ctx.send(f"{get_app_emoji('success')} `{staff_name}` is added to the staff application.", ephemeral=True)

    @staff_base.subcommand(sub_cmd_name="remove", sub_cmd_description="Remove a staff position")
    @has_staff_roles("SERVER_DEVELOPMENT_ROLE")
    async def staff_remove(self, ctx: ipy.SlashContext, staff_name: str):
        """
        Removes a staff position from the configuration.
        """
        await ctx.defer(ephemeral=True)

        if staff_name == "Other":
            await ctx.send(f"{get_app_emoji('error')} This staff position is unremovable!", ephemeral=True)
            return

        try:
            trial_config = json.load(open("data/trial_config.json", "r"))
        except FileNotFoundError:
            return

        if staff_name in trial_config:
            del trial_config[staff_name]
            with open("data/trial_config.json", "w") as file:
                json.dump(trial_config, file, indent=4)
            await ctx.send(f"{get_app_emoji('success')} `{staff_name}` is removed from staff application.", ephemeral=True)
        else:
            await ctx.send(f"{get_app_emoji('error')} `{staff_name}` does not exist.", ephemeral=True)

    @ipy.global_autocomplete(option_name="staff_name")
    async def staff_autocomplete(self, ctx: ipy.AutocompleteContext):
        """
        Autocomplete handler for 'staff_name' arguments.
        Fetches available staff positions from trial_config.json.
        """
        try:
            trial_config = json.load(open("data/trial_config.json", "r"))
        except FileNotFoundError:
            return

        user_input = ctx.input_text
        staff_choices = {}
        for staff in trial_config.keys():
            staff_choices[staff.lower().replace(" ", "")] = {"name": staff, "value": staff}

        if not user_input:
            await ctx.send(list(staff_choices.values())[:25])
            return

        returns = difflib.get_close_matches(
            user_input.lower(),
            staff_choices,
            n=25,
            cutoff=0.15,
        )

        results = []
        for item in returns:
            results.append(staff_choices[item])

        await ctx.send(results)

def setup(bot: ipy.Client):
    """
    Entry point for loading the extensions.
    """
    StaffApplication(bot)
    StaffCommands(bot)