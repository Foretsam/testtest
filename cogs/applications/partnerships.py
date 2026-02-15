import interactions as ipy

from core.utils import *
from core.models import *
from core.emojis_manager import *
from core import server_setup as sc

class PartnershipApplication(ipy.Extension):
    def __init__(self, bot):
        self.bot: ipy.Client = bot

    @ipy.component_callback("partner_start_button")
    async def partner_apply(self, ctx: ipy.ComponentContext):
        member = ctx.author

        if extract_integer(ctx.channel.topic) != int(member.id) and \
                extract_alphabets(member.username) != ctx.channel.name.split("┃")[1]:
            await ctx.send(f"{get_app_emoji('error')} Only the applicant of this channel can start the interview!",
                           ephemeral=True)
            return

        await ctx.defer(ephemeral=True)
          
        embed = ipy.Embed(
            title=f"**Answer these questions in this ticket:**",
            description=f"{get_app_emoji('arrow')}1. What kind of partnership are you looking for?.\n"
                        f"{get_app_emoji('arrow')}2. Is the partnership for a clan, for an individual or for a server?\n"
                        f"{get_app_emoji('arrow')}3. How do we benefit from this partnership?\n"
                        f"{get_app_emoji('arrow')}4. How would you benefit from this partnership?",
            footer=ipy.EmbedFooter(
                text="Feel free to ask for help for any confusions."
            ),
            color=COLOR
        )
        msg = await ctx.channel.send(embeds=[embed])

def setup(bot):
    PartnershipApplication(bot)