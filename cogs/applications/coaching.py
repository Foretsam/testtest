"""
Coaching Application Module.

This extension handles the application workflow for members seeking gameplay coaching.
Unlike other applications, this module specifically coordinates between the applicant
and the coaching staff by:
1. Validating the applicant's identity within the ticket.
2. Collecting specific data regarding playstyle and availability (UTC).
3. Alerting the registered Coaching role defined in the server configuration.

Dependencies:
    - interactions (Discord interactions)
    - core (Internal utilities, models, and configuration)
"""

import interactions as ipy

# Explicit imports used to maintain code clarity and avoid namespace pollution
from core.utils import extract_integer, extract_alphabets
from core import server_setup as sc
from core.emojis_manager import get_app_emoji
# Note: 'COLOR' was used but not imported in the original file. 
# Importing it from core.models to ensure execution safety.
from core.models import COLOR 

class CoachingApplication(ipy.Extension):
    """
    Manages the interactive components and logic for the Coaching Application system.
    """

    def __init__(self, bot: ipy.Client):
        """
        Initialize the extension.

        Args:
            bot (ipy.Client): The main bot instance.
        """
        self.bot = bot

    @ipy.component_callback("coaching_start_button")
    async def coaching_apply(self, ctx: ipy.ComponentContext):
        """
        Callback for the 'Start Coaching Application' button.

        Verifies the user's identity, prompts them with a questionnaire regarding
        their clash strategies and time availability, and notifies the coaching staff.

        Args:
            ctx (ipy.ComponentContext): The context of the button interaction.
        """
        member = ctx.author

        # Identity Verification:
        # Ensure that the user clicking the button is the owner of the ticket.
        # Checks against both the User ID in the channel topic and the Username in the channel name.
        is_topic_owner = extract_integer(ctx.channel.topic) == int(member.id)
        
        # Safe extraction of username from channel name (format: ticket┃username)
        try:
            channel_user_part = ctx.channel.name.split("┃")[1]
            is_name_owner = extract_alphabets(member.username) == channel_user_part
        except IndexError:
            is_name_owner = False

        if not is_topic_owner and not is_name_owner:
            await ctx.send(
                f"{get_app_emoji('error')} Only the applicant of this channel can start the interview!",
                ephemeral=True
            )
            return

        # Defer the interaction to allow time for processing and config retrieval
        await ctx.defer(ephemeral=True)

        # Construct the Questionnaire Embed
        # Focuses on player tag, specific army composition interests, and scheduling.
        embed = ipy.Embed(
            title="**Please respond all of the following in the chat:**",
            description=(
                f"{get_app_emoji('arrow')}1. Send the tag of your Clash of Clans account.\n"
                f"{get_app_emoji('arrow')}2. Which armies do you currently play, or which ones are you interested in learning? "
                "Let us know what you’re familiar with or what you’d like to explore so we can match you with the right support.\n"
                f"{get_app_emoji('arrow')}3. During which hour range of the day are you available for the coaching? "
                "Answer must be in UTC. Please use this converter: https://dateful.com/convert/utc"
            ),
            footer=ipy.EmbedFooter(
                text="Feel free to ask for help for any confusions."
            ),
            color=COLOR
        )
        
        # Retrieve Dynamic Server Configuration
        # This ensures we ping the correct Role ID even if it changes in the database.
        config: sc.GuildConfig = sc.get_config(ctx.guild.id)
        
        # Alert the Coaching Staff via role mention
        await ctx.channel.send(f"<@&{config.COACH_ROLE}>")
        
        # Post the questionnaire
        msg = await ctx.channel.send(embeds=[embed])   

def setup(bot: ipy.Client):
    """
    Entry point for loading the extension.
    """
    CoachingApplication(bot)