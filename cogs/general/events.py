"""
Global Event Listeners Module.

This extension handles Discord gateway events to ensure data consistency and 
automate maintenance tasks. It is responsible for:
1.  **Permission Synchronization:** Updates channel overwrites when specific categories are modified.
2.  **Connection Recovery:** Attempts to restart the bot service upon disconnection.
3.  **Data Cleanup:** Removes stale entries from local JSON databases (packages, tickets, events)
    when the corresponding messages or channels are deleted.
4.  **User Departure Handling:** Automatically closes open tickets if the ticket owner leaves the server.

Dependencies:
    - interactions (Discord interactions)
    - core (Internal utilities, configuration, and models)
"""

import interactions as ipy
import sys
import json
import coc
import os

# Explicit imports for internal utilities
from core.utils import fetch_overwrites, bot_restart
from core.models import ApplicationPackage
import core.server_setup as sc

class Events(ipy.Extension):
    """
    Extension class containing event listeners for Discord gateway events.
    """

    def __init__(self, bot: ipy.Client):
        self.bot = bot

    @ipy.listen(ipy.events.ChannelUpdate)
    async def on_channel_update(self, event: ipy.events.ChannelUpdate):
        """
        Listener for channel update events.
        
        Checks if the updated channel is one of the monitored Ticket Categories.
        If so, it triggers a fetch of permission overwrites to ensure the bot's 
        internal cache or database stays synchronized with Discord's state.

        Args:
            event (ipy.events.ChannelUpdate): The channel update event payload.
        """
        channel = event.after
        guild_id = channel.guild.id

        config: sc.GuildConfig = sc.get_config(guild_id)

        # Define the categories that require permission monitoring
        watched_categories = [
            config.CLAN_TICKETS_CATEGORY, 
            config.STAFF_APPLY_CATEGORY, 
            config.FWA_TICKETS_CATEGORY 
        ]
        
        # Filter out None values in case specific categories aren't configured
        watched_categories = [cat for cat in watched_categories if cat]

        # If the updated channel IS one of the watched categories, sync overwrites
        if int(event.after.id) in watched_categories:
            await fetch_overwrites(self.bot, int(event.after.id), update=True)

    @ipy.listen(ipy.events.Disconnect)
    async def on_connection_error(self, event: ipy.events.Disconnect):
        """
        Listener for the Disconnect event.
        
        Attempts to automatically restart the bot process if the connection to 
        the Discord Gateway is lost, ensuring high availability.
        """
        print(f"{self.bot.user.username} disconnected from Discord API, restarting bot!")
        try:
            bot_restart()
        except OSError:
            print(f"{self.bot.user.username} failed to restart...")
            pass

    @ipy.listen(ipy.events.MessageDelete)
    async def on_message_delete(self, event: ipy.events.MessageDelete):
        """
        Listener for message deletion.
        
        Checks if the deleted message was associated with an active 'Application Package'
        (e.g., an interactive menu for clan application). If so, removes the 
        orphaned data from `packages.json` to prevent memory leaks or logic errors.

        Args:
            event (ipy.events.MessageDelete): The message delete event payload.
        """
        try:
            packages: dict[str, ApplicationPackage] = json.load(open("data/packages.json", "r"))
        except (FileNotFoundError, json.JSONDecodeError):
            return

        # Find keys where the stored message_id matches the deleted message
        keys = [key for key, value in packages.items() if value.get("message_id") == int(event.message.id)]
        
        if keys:
            # Delete the first matching package found
            del packages[keys[0]]

            with open("data/packages.json", "w") as file:
                json.dump(packages, file, indent=4)

    @ipy.listen(ipy.events.ChannelDelete)
    async def on_channel_delete(self, event: ipy.events.ChannelDelete):
        """
        Listener for channel deletion.
        
        Performs comprehensive cleanup across multiple JSON databases:
        1. **packages.json**: Removes application data linked to the deleted channel.
        2. **open_tickets.json**: Unlinks the channel from the user's active ticket list.
        3. **ticket_events.json**: Cancels any scheduled events (e.g., auto-close timers) for the channel.

        Args:
            event (ipy.events.ChannelDelete): The channel delete event payload.
        """
        # 1. Cleanup Application Packages
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

        # 2. Cleanup Open Tickets Registry
        try:
            open_tickets = json.load(open("data/open_tickets.json", "r"))
        except (FileNotFoundError, json.JSONDecodeError):
            open_tickets = {}

        # Iterate through users to find if they owned this ticket
        for member_id in open_tickets:
            if int(event.channel.id) in open_tickets[member_id]:
                open_tickets[member_id].remove(int(event.channel.id))

                # If user has no more tickets, remove them from the registry entirely
                if not open_tickets[member_id]:
                    del open_tickets[member_id]

                with open("data/open_tickets.json", "w") as file:
                    json.dump(open_tickets, file, indent=4)
                break

        # 3. Cleanup Scheduled Ticket Events
        try:
            ticket_events = json.load(open("data/ticket_events.json", "r"))
        except (FileNotFoundError, json.JSONDecodeError):
            ticket_events = {}

        # Key format: "channel_id|member_id"
        for key, data in ticket_events.items():
            channel_id, member_id = key.split("|")
            if channel_id == str(event.channel.id):
                del ticket_events[key]

                with open("data/ticket_events.json", "w") as file:
                    json.dump(ticket_events, file, indent=4)
                break

    @ipy.listen(ipy.events.MemberRemove)
    async def on_guild_member_remove(self, event: ipy.events.MemberRemove):
        """
        Listener for member departure.
        
        Automatically deletes any open tickets belonging to the member who left.
        This prevents stale tickets from clogging the server.

        Args:
            event (ipy.events.MemberRemove): The member remove event payload.
        """
        try:
            open_tickets = json.load(open("data/open_tickets.json", "r"))
        except (FileNotFoundError, json.JSONDecodeError):
            return

        member_id_str = str(event.member.id)
        
        # Check if the departing member had any open tickets
        if member_id_str in open_tickets.keys():
            # Create a copy of the list to iterate safely while modifying/deleting
            for channel_id in list(open_tickets[member_id_str]):
                try:
                    # Force fetch the channel to ensure we have the guild context
                    channel = await self.bot.fetch_channel(channel_id, force=True)
                except (ipy.errors.NotFound, ipy.errors.Forbidden):
                    # Channel already deleted or inaccessible; skip
                    continue

                if not channel:
                    continue

                # Verification: Ensure the ticket belongs to the guild the user just left
                if channel.guild.id != event.guild.id:
                    continue

                # Delete the ticket.
                # Note: This will trigger 'on_channel_delete', which handles the JSON cleanup.
                await channel.delete(reason="Member has left the server.")

def setup(bot: ipy.Client):
    """
    Entry point for loading the extension.
    """
    Events(bot)