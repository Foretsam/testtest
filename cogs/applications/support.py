import interactions as ipy

from core.utils import *
from core.models import *
from core.emojis_manager import *
from core import server_setup as sc

class SupportApplication(ipy.Extension):
    def __init__(self, bot):
        self.bot: ipy.Client = bot

    @ipy.component_callback("support_start_button")
    async def support_apply(self, ctx: ipy.ComponentContext):
        member = ctx.author

        if extract_integer(ctx.channel.topic) != int(member.id) and \
                extract_alphabets(member.username) != ctx.channel.name.split("┃")[1]:
            await ctx.send(f"{get_app_emoji('error')} Only the applicant of this channel can interact!",
                           ephemeral=True)
            return

        await ctx.defer(ephemeral=True)    

def setup(bot):
    SupportApplication(bot)