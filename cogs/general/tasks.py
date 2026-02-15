"""
Background Tasks & Automation Module.

This extension manages scheduled asynchronous tasks that run independently of user interaction.
It acts as the bot's internal clock and maintenance crew.

Key Responsibilities:
1.  **Data Hygiene (Garbage Collection):** Periodically scans local JSON databases (`packages.json`, `ticket_data.json`)
    and removes entries linked to deleted or inaccessible channels to prevent data bloat.
2.  **Event Scheduling:** Automates time-sensitive workflows such as:
    - Notifying users when Clan War Leagues (CWL) end (on the 10th of the month).
    - Automatically starting and ending staff trials based on configured durations.
3.  **Cache Management:** Refreshes and clears the internal player data cache to ensure
    up-to-date information while managing memory usage.

Dependencies:
    - interactions (Task scheduling triggers)
    - coc (Clash of Clans API for player updates)
    - core (Utilities and models)
"""

import interactions as ipy
import json
import copy
import os
import coc
from datetime import datetime, timezone, timedelta

# Explicit imports to maintain code clarity
from core.utils import *
from core.models import *
from core.emojis_manager import *
import core.server_setup as sc

class Tasks(ipy.Extension):
    """
    Extension class containing all background tasks and their scheduling logic.
    """

    def __init__(self, bot: ipy.Client):
        self.bot = bot

    @ipy.listen(ipy.events.Startup)
    async def on_startup(self):
        """
        Event listener triggered when the bot is fully ready.
        
        Initializes and starts all background tasks. This ensures tasks rely on
        a connected bot instance and don't start prematurely.
        """
        self.cleanup_data_files.start()
        self.cwl_end.start()
        self.auto_trials.start()
        self.update_player_cache.start()
        self.clear_player_cache.start()
        print("Tasks started from cogs/general/tasks.py")

    @ipy.Task.create(ipy.IntervalTrigger(hours=24))
    async def cleanup_data_files(self):
        """
        Daily Garbage Collection Task.
        
        Runs every 24 hours to ensure database integrity. It orchestrates the cleanup
        of multiple JSON files, removing records that point to non-existent Discord entities.
        """
        print("🧹 Starting daily data cleanup...")
        await self.clean_packages_json()
        await self.clean_ticket_data_json()
        print("✅ Daily data cleanup complete.")

    async def clean_packages_json(self):
        """
        Helper method to clean 'packages.json'.
        
        Iterates through all application packages. If the associated channel cannot
        be fetched (404 NotFound or 403 Forbidden), the package is deemed stale and deleted.
        """
        if not os.path.exists("data/packages.json"):
            return

        try:
            with open("data/packages.json", "r") as f:
                packages = json.load(f)
            
            tokens_to_delete = []
            
            # Identify stale entries
            for token, data in packages.items():
                channel_id = data.get("channel_id")
                
                if not channel_id:
                    continue

                try:
                    # force=True bypasses cache to verify actual existence on Discord
                    await self.bot.fetch_channel(channel_id, force=True)
                
                except (ipy.errors.NotFound, ipy.errors.Forbidden):
                    # Channel is gone or bot lost access; mark for deletion
                    tokens_to_delete.append(token)
                except Exception as e:
                    print(f"⚠ Error checking channel {channel_id}: {e}")
                    continue

            # Perform deletion
            if tokens_to_delete:
                for token in tokens_to_delete:
                    del packages[token]
                
                with open("data/packages.json", "w") as f:
                    json.dump(packages, f, indent=4)
                print(f"🗑️ Removed {len(tokens_to_delete)} stale entries from packages.json")

        except json.JSONDecodeError:
            print("⚠ packages.json is corrupted.")

    async def clean_ticket_data_json(self):
        """
        Helper method to clean 'ticket_data.json'.
        
        Similar logic to packages cleanup, ensuring ticket metadata is removed
        if the ticket channel no longer exists.
        """
        if not os.path.exists("data/ticket_data.json"):
            return

        try:
            with open("data/ticket_data.json", "r") as f:
                ticket_data = json.load(f)

            keys_to_delete = []

            for key in ticket_data.keys():
                try:
                    # Key format assumed to contain channel_id as the first element
                    channel_id_str = key.split("|")[0]
                    channel_id = int(channel_id_str)
                    
                    await self.bot.fetch_channel(channel_id, force=True)
                except (ipy.errors.NotFound, ipy.errors.Forbidden, ValueError):
                    keys_to_delete.append(key)
                except Exception:
                    continue

            if keys_to_delete:
                for key in keys_to_delete:
                    del ticket_data[key]

                with open("data/ticket_data.json", "w") as f:
                    json.dump(ticket_data, f, indent=4)
                print(f"🗑️ Removed {len(keys_to_delete)} stale entries from ticket_data.json")

        except json.JSONDecodeError:
            print("⚠ ticket_data.json is corrupted.")

    @ipy.Task.create(ipy.TimeTrigger(hour=8))
    async def cwl_end(self):
        """
        Clan War Leagues (CWL) End Notification.
        
        Runs daily at 8:00 AM. Checks if today is the 10th of the month (standard CWL end date).
        If so, scans specific 'After CWL' ticket categories and pings the ticket owners
        to resume their application process.
        """
        now = datetime.now(timezone.utc)
        
        # CWL typically ends on the 10th-11th depending on timezone/start time
        if now.day != 10:
            return
        
        # Iterate over all guilds the bot is connected to
        for guild in self.bot.guilds:
            config: sc.GuildConfig = sc.get_config(guild.id)

            if not config.AFTER_CWL_CATEGORY:
                continue

            try:
                category = await self.bot.fetch_channel(config.AFTER_CWL_CATEGORY)
                if not category:
                    continue
            except ipy.errors.HTTPException:
                continue

            # Process each ticket in the "Hold" category
            for channel in category.channels:
                try:
                    # Optimization: Skip if the channel was already active today
                    msg = await channel.fetch_message(channel.last_message_id)
                    last_msg_date = datetime.fromtimestamp(msg.created_at.timestamp(), tz=timezone.utc)
                    if last_msg_date.day == now.day:
                        continue

                    # Identify the ticket owner to ping them
                    member = None
                    for overwrite in channel.permission_overwrites:
                        if overwrite.type == ipy.OverwriteType.MEMBER:
                            try:
                                fetched_member = await channel.guild.fetch_member(overwrite.id)
                                # Validation via Topic ID or Channel Name
                                if int(fetched_member.id) == extract_integer(channel.topic):
                                    member = fetched_member
                                    break
                                if extract_alphabets(fetched_member.username) == channel.name.split("┃")[1]:
                                    member = fetched_member
                                    break
                            except:
                                continue
                    
                    if not member:
                        continue

                    # Notify the user
                    await channel.send(
                        f"{member.mention}\n\n"
                        f"{get_app_emoji('Giveaway')} "
                        f"**CWL has ended!** Please resume with the ticket application, thanks!"
                    )
                except Exception as e:
                    print(f"Error processing channel {channel.id} in guild {guild.id}: {e}")
                    continue

    @ipy.Task.create(ipy.IntervalTrigger(minutes=1))
    async def auto_trials(self):
        """
        Automated Staff Trial Management.
        
        Runs every minute to check `trial_events.json`.
        - If a 'start' event time is reached: Calculates end time, moves channel, and pins start message.
        - If an 'end' event time is reached: Posts the voting panel and removes the event.
        """
        try:
            with open("data/trial_events.json", "r") as f:
                trial_events = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return

        if not trial_events:
            return

        now = datetime.now(timezone.utc)

        # Iterate over a deepcopy to allow modification of the dictionary during iteration
        for key, value in copy.deepcopy(trial_events).items():
            # Parse stored date list [YYYY, MM, DD, HH, MM] into datetime object
            target_date = datetime(
                value["date"][0], value["date"][1], value["date"][2],
                value["date"][3], value["date"][4], tzinfo=timezone.utc
            )

            # Wait until the target time is reached
            if target_date > now:
                continue

            channel_id, member_id = key.split("|")
            try:
                channel = await self.bot.fetch_channel(channel_id, force=True)
                user = await self.bot.fetch_user(member_id, force=True)
            except ipy.errors.HTTPException:
                # Cleanup if channel/user is gone
                del trial_events[key]
                continue

            if not user or not channel:
                del trial_events[key]
                continue

            # Handle Trial End
            if value["action"] == "end":
                vote_button = ipy.Button(
                    style=ipy.ButtonStyle.SECONDARY,
                    label="Start Voting",
                    custom_id=f"vote_start_button|{value['type'].replace(' ', '0')}",
                    emoji="🗳️"
                )

                embed = ipy.Embed(
                    title="**Trial Has Ended**",
                    description=f"{user.mention}'s **{value['type'].lower()}** trial has come to an end. "
                                f"The management team will evaluate the activity of the applicant and conduct "
                                f"voting to decide the result of the trial.",
                    footer=ipy.EmbedFooter(text="End Time"),
                    timestamp=ipy.Timestamp.utcnow(),
                    color=COLOR
                )

                del trial_events[key]

                await channel.send(f"{user.mention} We will inform you about your trial result soon!", embed=embed,
                                   components=vote_button)

            # Handle Trial Start (Transition from Pending to Active)
            if value["action"] == "start":
                # Calculate future end date based on configured duration ("days")
                end_date = datetime.now(timezone.utc) + timedelta(days=value["days"])
                end = f"<t:{int(end_date.timestamp())}:D>"

                # Update event to now track the END of the trial
                trial_events[key] = {
                    "date": [end_date.year, end_date.month, end_date.day, end_date.hour, end_date.minute],
                    "action": "end",
                    "type": value["type"]
                }
                guild_id = channel.guild.id
                config: sc.GuildConfig = sc.get_config(guild_id)
                
                parent_id = config.STAFF_TRIALS_CATEGORY

                embed = ipy.Embed(
                    title="**Trial Has Started**",
                    description=f"{user.mention}'s trial for {value['type'].lower()} has started! It will end on {end}, "
                                f"every staff in the management team wish the best luck for the applicant!",
                    footer=ipy.EmbedFooter(text="Start Time"),
                    timestamp=ipy.Timestamp.utcnow(),
                    color=COLOR
                )
                await (await channel.send(user.mention, embed=embed)).pin()

                # Move channel to the Active Trials category
                if parent_id:
                    await channel.edit(parent_id=parent_id, topic=f"Applicant ID: {user.id}\nEnds on {end}")

        with open("data/trial_events.json", "w") as file:
            json.dump(trial_events, file, indent=4)

    @ipy.Task.create(ipy.IntervalTrigger(hours=3))
    async def update_player_cache(self):
        """
        Scheduled Cache Refresh.
        
        Updates the data of cached players every 3 hours. This ensures that
        frequently accessed player profiles have relatively fresh data without
        spamming the API on every request.
        """
        # We iterate over a copy of keys to avoid runtime modification errors
        for key in copy.deepcopy(list(player_cache.keys())):
            try:
                await fetch_player(self.bot.coc, key, update=True)
            except InvalidTagError:
                del player_cache[key]
            except coc.errors.Maintenance:
                # Skip updates if API is in maintenance
                pass

    @ipy.Task.create(ipy.IntervalTrigger(days=2))
    async def clear_player_cache(self):
        """
        Cache Reset Task.
        
        Completely clears the player cache every 48 hours to free up memory
        and remove data for players who are no longer being queried.
        """
        player_cache.clear()

def setup(bot: ipy.Client):
    """
    Entry point for loading the extension.
    """
    Tasks(bot)