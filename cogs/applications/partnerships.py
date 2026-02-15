"""
Partnership Application Module.

This extension manages the application workflow for potential partners seeking collaboration
with the alliance. It handles the interactive questionnaire process, gathering essential
details about the nature of the partnership (clan, server, or individual) and the mutual
benefits involved.

Dependencies:
    - interactions (Discord interactions)
    - core (Internal utilities, models, and emoji management)
"""

import interactions as ipy

# Explicit imports to maintain code clarity
from core.utils import extract_integer, extract_alphabets
from core.models import COLOR
from core.emojis_manager import get_app_emoji
from core import server_setup as sc

class PartnershipApplication(ipy.Extension):
    """
    Manages the interactive components and logic for the Partnership Application system.
    """

    def __init__(self, bot: ipy.Client):
        """
        Initialize the extension.

        Args:
            bot (ipy.Client): The main bot instance.
        """
        self.bot = bot

    @ipy.component_callback("partner_start_button")
    async def partner_apply(self, ctx: ipy.ComponentContext):
        """
        Callback for the 'Start Application' button in a Partnership Ticket.

        Verifies the applicant's identity and posts the specific questionnaire required
        for evaluating potential partnerships.

        Args:
            ctx (ipy.ComponentContext): The context of the button interaction.
        """
        member = ctx.author

        # Identity Verification:
        # We must ensure that the person clicking the button is the actual applicant.
        # Check 1: Does the User ID extracted from the channel topic match?
        is_topic_owner = extract_integer(ctx.channel.topic) == int(member.id)
        
        # Check 2: Does the username in the channel name (ticket┃username) match?
        # This serves as a fallback if the topic is missing or malformed.
        try:
            channel_username = ctx.channel.name.split("┃")[1]
            is_name_owner = extract_alphabets(member.username) == channel_username
        except IndexError:
            # Handle edge case where channel name format is incorrect
            is_name_owner = False

        if not is_topic_owner and not is_name_owner:
            await ctx.send(
                f"{get_app_emoji('error')} Only the applicant of this channel can start the interview!",
                ephemeral=True
            )
            return

        # Defer the interaction to prevent timeout errors while processing
        await ctx.defer(ephemeral=True)
          
        # Construct the Interview Questionnaire Embed
        # Questions focus on the scope of the partnership and the value proposition (ROI).
        embed = ipy.Embed(
            title="**Answer these questions in this ticket:**",
            description=(
                f"{get_app_emoji('arrow')}1. What kind of partnership are you looking for?\n"
                f"{get_app_emoji('arrow')}2. Is the partnership for a clan, for an individual, or for a server?\n"
                f"{get_app_emoji('arrow')}3. How do we benefit from this partnership?\n"
                f"{get_app_emoji('arrow')}4. How would you benefit from this partnership?"
            ),
            footer=ipy.EmbedFooter(
                text="Feel free to ask for help for any confusions."
            ),
            color=COLOR
        )
        
        # Post the questionnaire to the ticket channel
        msg = await ctx.channel.send(embeds=[embed])

def setup(bot: ipy.Client):
    """
    Entry point for loading the extension.
    """
    PartnershipApplication(bot)