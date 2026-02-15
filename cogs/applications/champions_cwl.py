import interactions as ipy

from core.emojis_manager import *
from core.utils import *
from core.models import *
from core import server_setup as sc

# Clan-Apply (not fwa) 
class ChampionsApplication(ipy.Extension):
    def __init__(self, bot):
        self.bot: ipy.Client = bot

    @ipy.component_callback("champions_start_button")
    async def champions_apply(self, ctx: ipy.ComponentContext):
        member = ctx.author

        if extract_integer(ctx.channel.topic) != int(member.id) and \
                extract_alphabets(member.username) != ctx.channel.name.split("┃")[1]:
            await ctx.send(f"{get_app_emoji('error')} Only the applicant of this channel can start the interview!",
                           ephemeral=True)
            return

        await ctx.defer(ephemeral=True)
          
        embed = ipy.Embed(
            title=f"**Answer these questions in this ticket:**",
            description=f"{get_app_emoji('arrow')}1. Send the tag of your Clash of Clans account. \n"
                        f"{get_app_emoji('arrow')}2. What armies are you using currently? \n"
                        f"{get_app_emoji('arrow')}3. Please send a ss of your current base layout (traps included).\n"
                        f"{get_app_emoji('arrow')}4. What cwl level did you play last month? And how many stars did you get? (Example: Master 2 - 18 Stars) \n"
                        f"{get_app_emoji('arrow')}Before continuing, to be in champions will requires commitment and you should not apply if you're a casual player.",
            footer=ipy.EmbedFooter(
                text="Feel free to ask for help for any confusions."
            ),
            color=COLOR
        )
        msg = await ctx.channel.send(embeds=[embed])

def setup(bot):
    ChampionsApplication(bot)