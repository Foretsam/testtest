"""
Champions CWL Application Module.

This extension manages the specific application flow for "Champions CWL" (Clan War Leagues).
It handles the interaction when a user initiates the application process within a ticket,
prompting them with specific questions regarding their Clash of Clans performance.

Dependencies:
    - interactions (Discord interactions)
    - core (Internal utilities, models, and emoji management)
"""

import interactions as ipy

# Explicit imports are preferred over wildcard (*) imports for clarity and debugging
from core.emojis_manager import get_app_emoji
from core.utils import extract_integer, extract_alphabets
from core.models import COLOR
from core import server_setup as sc

class ChampionsApplication(ipy.Extension):
    """
    Handles the interactive components for the Champions CWL application process.
    """

    def __init__(self, bot: ipy.Client):
        """
        Initialize the extension.

        Args:
            bot (ipy.Client): The main bot instance.
        """
        self.bot = bot

    @ipy.component_callback("champions_start_button")
    async def champions_apply(self, ctx: ipy.ComponentContext):
        """
        Callback for the 'Start Application' button in a Champions CWL ticket.

        Validates that the user clicking the button is the ticket owner, then
        posts the questionnaire embed to the channel.

        Args:
            ctx (ipy.ComponentContext): The context of the button interaction.
        """
        member = ctx.author

        # Security & Identity Check:
        # Verify that the user clicking the button is actually the applicant (ticket owner).
        # The check passes if EITHER:
        # 1. The ID in the channel topic matches the user's ID.
        # 2. The username in the channel name matches the user's name (formatted).
        # This dual-check provides a fallback if the topic is empty or the name format varies.
        
        user_id_match = extract_integer(ctx.channel.topic) == int(member.id)
        
        # Note: Assumes channel format includes a separator "┃" (e.g., "ticket┃username")
        try:
            channel_username = ctx.channel.name.split("┃")[1]
            username_match = extract_alphabets(member.username) == channel_username
        except IndexError:
            # Handle cases where channel name doesn't follow the split format
            username_match = False

        # If both checks fail, deny the interaction.
        if not user_id_match and not username_match:
            await ctx.send(
                f"{get_app_emoji('error')} Only the applicant of this channel can start the interview!",
                ephemeral=True
            )
            return

        # Defer interaction to prevent timeout while constructing the response
        await ctx.defer(ephemeral=True)
          
        # Construct the Interview Questionnaire Embed
        embed = ipy.Embed(
            title="**Answer these questions in this ticket:**",
            description=(
                f"{get_app_emoji('arrow')}1. Send the tag of your Clash of Clans account. \n"
                f"{get_app_emoji('arrow')}2. What armies are you using currently? \n"
                f"{get_app_emoji('arrow')}3. Please send a screenshot of your current base layout (traps included).\n"
                f"{get_app_emoji('arrow')}4. What CWL level did you play last month? And how many stars did you get? "
                "(Example: Master 2 - 18 Stars) \n"
                f"{get_app_emoji('arrow')}Before continuing, be aware that Champions CWL requires "
                "strict commitment. Do not apply if you are a casual player."
            ),
            footer=ipy.EmbedFooter(
                text="Feel free to ask for help for any confusions."
            ),
            color=COLOR
        )
        
        # Post the questions to the channel for the user to answer
        msg = await ctx.channel.send(embeds=[embed])

def setup(bot: ipy.Client):
    """
    Entry point for loading the extension.
    """
    ChampionsApplication(bot)