import interactions as ipy
from core.utils import *
from core import server_setup as sc
from core.emojis_manager import*

class CoachingApplication(ipy.Extension):
    def __init__(self, bot):
        self.bot: ipy.Client = bot

    @ipy.component_callback("coaching_start_button")
    async def coaching_apply(self, ctx: ipy.ComponentContext):
        member = ctx.author

        if extract_integer(ctx.channel.topic) != int(member.id) and \
                extract_alphabets(member.username) != ctx.channel.name.split("┃")[1]:
            await ctx.send(f"{get_app_emoji('error')} Only the applicant of this channel can start the interview!",
                            ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        embed = ipy.Embed(
            title=f"**Please respond all of the following in the chat:**",
            description=f"{get_app_emoji('arrow')}1. Send the tag of your Clash of Clans account.\n"
                        f"{get_app_emoji('arrow')}2. Which armies do you currently play, or which ones are you interested in learning? Let us know what you’re familiar with or what you’d like to explore so we can match you with the right support\n"
                        f"{get_app_emoji('arrow')}3. During which hour range of the day are you available for the coaching? Answer must be in UTC, please use this to convert: https://dateful.com/convert/utc",
            footer=ipy.EmbedFooter(
                text="Feel free to ask for help for any confusions."
            ),
            color=COLOR
        )
        
        # Use Dynamic Config
        config: sc.GuildConfig = sc.get_config(ctx.guild.id)
        
        await ctx.channel.send(f"<@&{config.COACH_ROLE}>")  
        msg = await ctx.channel.send(embeds=[embed])   

def setup(bot):
    CoachingApplication(bot)