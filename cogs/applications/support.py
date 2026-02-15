"""
Support Ticket Interaction Module.

This extension manages the interactive elements specific to 'Support' type tickets.
Unlike application tickets (Clan, Staff, FWA) which trigger complex questionnaires,
the support workflow is currently designed to be more direct, primarily verifying
the user's identity before alerting staff or allowing further interaction.

Dependencies:
    - interactions (Discord interactions)
    - core (Internal utilities and emoji management)
"""

import interactions as ipy

# Explicit imports to maintain code clarity
from core.utils import extract_integer, extract_alphabets
from core.models import * 
from core.emojis_manager import get_app_emoji

class SupportApplication(ipy.Extension):
    """
    Manages the interactive components logic for Support Tickets.
    """

    def __init__(self, bot: ipy.Client):
        """
        Initialize the extension.

        Args:
            bot (ipy.Client): The main bot instance.
        """
        self.bot = bot

    @ipy.component_callback("support_start_button")
    async def support_apply(self, ctx: ipy.ComponentContext):
        """
        Callback for the 'Start/Interact' button in a Support Ticket.

        Currently, this function performs a strict security check to ensure
        only the ticket creator can interact with the button, and then
        defers the interaction to prevent timeout.

        Args:
            ctx (ipy.ComponentContext): The context of the button interaction.
        """
        member = ctx.author

        # Identity Verification:
        # Ensure that the user clicking the button is the owner of the ticket.
        # This prevents other users (or staff) from accidentally triggering applicant-only workflows.
        # Check 1: Match User ID against the channel topic.
        # Check 2: Match Username against the channel name (fallback).
        if extract_integer(ctx.channel.topic) != int(member.id) and \
                extract_alphabets(member.username) != ctx.channel.name.split("┃")[1]:
            await ctx.send(f"{get_app_emoji('error')} Only the applicant of this channel can interact!",
                           ephemeral=True)
            return

        # Defer the interaction.
        # Since support tickets often involve manual typing or staff intervention,
        # this simply acknowledges the button press without triggering a modal/embed immediately.
        # Future expansion: Add specific support category selection here if needed.
        await ctx.defer(ephemeral=True)    

def setup(bot: ipy.Client):
    """
    Entry point for loading the extension.
    """
    SupportApplication(bot)