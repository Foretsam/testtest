import interactions as ipy
import sys
import json
import coc
import os

from core.utils import fetch_overwrites, bot_restart
from core.models import ApplicationPackage
import core.server_setup as sc

class Events(ipy.Extension):
    def __init__(self, bot):
        self.bot = bot

    @ipy.listen(ipy.events.ChannelUpdate)
    async def on_channel_update(self, event: ipy.events.ChannelUpdate):
        channel = event.after
        guild_id = channel.guild.id

        config: sc.GuildConfig = sc.get_config(guild_id)

        # Use dynamic categories
        watched_categories = [
            config.CLAN_TICKETS_CATEGORY, 
            config.STAFF_APPLY_CATEGORY, 
            config.FWA_TICKETS_CATEGORY 
        ]
        
        # Filter out None in case config is partial
        watched_categories = [cat for cat in watched_categories if cat]

        if int(event.after.id) in watched_categories:
            await fetch_overwrites(self.bot, int(event.after.id), update=True)

    @ipy.listen(ipy.events.Disconnect)
    async def on_connection_error(self):
        print(f"{self.bot.user.username} disconnected from Discord API, restarting bot!")
        try:
            bot_restart()
        except OSError:
            print(f"{self.bot.user.username} failed to restart...")
            pass

    @ipy.listen(ipy.events.MessageDelete)
    async def on_message_delete(self, event: ipy.events.MessageDelete):
        try:
            packages: dict[str, ApplicationPackage] = json.load(open("data/packages.json", "r"))
        except (FileNotFoundError, json.JSONDecodeError):
            return

        keys = [key for key, value in packages.items() if value.get("message_id") == int(event.message.id)]
        if keys:
            del packages[keys[0]]

            with open("data/packages.json", "w") as file:
                json.dump(packages, file, indent=4)

    @ipy.listen(ipy.events.ChannelDelete)
    async def on_channel_delete(self, event: ipy.events.ChannelDelete):
        try:
            packages: dict[str, ApplicationPackage] = json.load(open("data/packages.json", "r"))
        except (FileNotFoundError, json.JSONDecodeError):
            packages = {}

        keys = [key for key, value in packages.items() if value.get("channel_id") == int(event.channel.id)]
        if keys:
            for key in keys:
                del packages[key]

            with open("data/packages.json", "w") as file:
                json.dump(packages, file, indent=4)

        try:
            open_tickets = json.load(open("data/open_tickets.json", "r"))
        except (FileNotFoundError, json.JSONDecodeError):
            open_tickets = {}

        for member_id in open_tickets:
            if int(event.channel.id) in open_tickets[member_id]:
                open_tickets[member_id].remove(int(event.channel.id))

                if not open_tickets[member_id]:
                    del open_tickets[member_id]

                with open("data/open_tickets.json", "w") as file:
                    json.dump(open_tickets, file, indent=4)

                break

        try:
            ticket_events = json.load(open("data/ticket_events.json", "r"))
        except (FileNotFoundError, json.JSONDecodeError):
            ticket_events = {}

        for key, data in ticket_events.items():
            channel_id, member_id = key.split("|")
            if channel_id == str(event.channel.id):
                del ticket_events[key]

                with open("data/ticket_events.json", "w") as file:
                    json.dump(ticket_events, file, indent=4)

                break

    @ipy.listen(ipy.events.MemberRemove)
    async def on_guild_member_remove(self, event: ipy.events.MemberRemove):
        try:
            open_tickets = json.load(open("data/open_tickets.json", "r"))
        except (FileNotFoundError, json.JSONDecodeError):
            return

        member_id_str = str(event.member.id)
        if member_id_str in open_tickets.keys():
            # Use list() to create a copy so we can modify the original list if needed
            for channel_id in list(open_tickets[member_id_str]):
                try:
                    # force=True fetches from API to ensure we get the guild_id correctly
                    channel = await self.bot.fetch_channel(channel_id, force=True)
                except (ipy.errors.NotFound, ipy.errors.Forbidden):
                    # Channel might already be gone or inaccessible
                    continue

                if not channel:
                    continue

                # IMPORTANT: Only delete the ticket if it belongs to the guild the member just left
                if channel.guild.id != event.guild.id:
                    continue

                await channel.delete(reason="Member has left the server.")
                # Note: The deletion triggers on_channel_delete which updates the JSON,
                # so we don't strictly need to update JSON here, but it's safe to let the event listener handle it.

def setup(bot):
    Events(bot)