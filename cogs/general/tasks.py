import interactions as ipy
import json
import copy
import coc
from datetime import datetime, timezone, timedelta

# Imports from your core modules
from core.utils import *
from core.models import *
from core.emojis_manager import *
import core.server_setup as sc

class Tasks(ipy.Extension):
    def __init__(self, bot):
        self.bot = bot

    @ipy.listen(ipy.events.Startup)
    async def on_startup(self):
        """
        Starts the tasks when the bot is ready. 
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
        Daily Garbage Collection:
        Checks packages.json and ticket_data.json for entries linked to 
        channels that no longer exist and removes them.
        """
        print("🧹 Starting daily data cleanup...")
        await self.clean_packages_json()
        await self.clean_ticket_data_json()
        print("✅ Daily data cleanup complete.")

    async def clean_packages_json(self):
        if not os.path.exists("data/packages.json"):
            return

        try:
            with open("data/packages.json", "r") as f:
                packages = json.load(f)
            
            tokens_to_delete = []
            
            for token, data in packages.items():
                channel_id = data.get("channel_id")
                
                if not channel_id:
                    continue

                try:
                    await self.bot.fetch_channel(channel_id, force=True)
                
                except (ipy.errors.NotFound, ipy.errors.Forbidden):
                    tokens_to_delete.append(token)
                except Exception as e:
                    print(f"⚠ Error checking channel {channel_id}: {e}")
                    continue

            if tokens_to_delete:
                for token in tokens_to_delete:
                    del packages[token]
                
                with open("data/packages.json", "w") as f:
                    json.dump(packages, f, indent=4)
                print(f"🗑️ Removed {len(tokens_to_delete)} stale entries from packages.json")

        except json.JSONDecodeError:
            print("⚠ packages.json is corrupted.")

    async def clean_ticket_data_json(self):
        if not os.path.exists("data/ticket_data.json"):
            return

        try:
            with open("data/ticket_data.json", "r") as f:
                ticket_data = json.load(f)

            keys_to_delete = []

            for key in ticket_data.keys():
                try:
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
        now = datetime.now(timezone.utc)
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

            for channel in category.channels:
                try:
                    msg = await channel.fetch_message(channel.last_message_id)
                    last_msg_date = datetime.fromtimestamp(msg.created_at.timestamp(), tz=timezone.utc)
                    if last_msg_date.day == now.day:
                        continue

                    member = None
                    for overwrite in channel.permission_overwrites:
                        if overwrite.type == ipy.OverwriteType.MEMBER:
                            try:
                                fetched_member = await channel.guild.fetch_member(overwrite.id)
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
        try:
            with open("data/trial_events.json", "r") as f:
                trial_events = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return

        if not trial_events:
            return

        now = datetime.now(timezone.utc)

        for key, value in copy.deepcopy(trial_events).items():
            target_date = datetime(
                value["date"][0], value["date"][1], value["date"][2],
                value["date"][3], value["date"][4], tzinfo=timezone.utc
            )

            if target_date > now:
                continue

            channel_id, member_id = key.split("|")
            try:
                channel = await self.bot.fetch_channel(channel_id, force=True)
                user = await self.bot.fetch_user(member_id, force=True)
            except ipy.errors.HTTPException:
                del trial_events[key]
                continue

            if not user or not channel:
                del trial_events[key]
                continue

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

            if value["action"] == "start":
                end_date = datetime.now(timezone.utc) + timedelta(days=value["days"])
                end = f"<t:{int(end_date.timestamp())}:D>"

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

                if parent_id:
                    await channel.edit(parent_id=parent_id, topic=f"Applicant ID: {user.id}\nEnds on {end}")

        with open("data/trial_events.json", "w") as file:
            json.dump(trial_events, file, indent=4)

    @ipy.Task.create(ipy.IntervalTrigger(hours=3))
    async def update_player_cache(self):
        # We iterate over a copy of keys to avoid runtime modification errors
        for key in copy.deepcopy(list(player_cache.keys())):
            try:
                await fetch_player(self.bot.coc, key, update=True)
            except InvalidTagError:
                del player_cache[key]
            except coc.errors.Maintenance:
                pass

    @ipy.Task.create(ipy.IntervalTrigger(days=2))
    async def clear_player_cache(self):
        player_cache.clear()

def setup(bot):
    Tasks(bot)