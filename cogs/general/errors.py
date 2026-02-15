import interactions 
import traceback
import sys
import coc
import copy
import re
import asyncio

from core.models import ComponentTimeoutError, InvalidTagError
from core.emojis_manager import *
from core.utils import *

class Errors(ipy.Extension):
    def __init__(self, bot):
        self.bot = bot

    @ipy.listen(ipy.events.Error, disable_default_listeners=True)
    async def on_error(self, event: ipy.events.Error):
        ctx: ipy.ComponentContext | ipy.ModalContext | None = getattr(event, "ctx", None)
        error = getattr(event, "error", None)

        if ctx is None or getattr(ctx, "channel", None) is None or getattr(ctx.channel, "id", None) is None:
            return
        if isinstance(error, ComponentTimeoutError):
            if ctx.custom_id == "clan_start_button":
                await ctx.edit(error.message, embed=TIMEOUT_EMBED, components=CLAN_RESTART_BUTTON)
            elif ctx.custom_id == "fwa_start_button":
                await ctx.edit(error.message, embed=TIMEOUT_EMBED, components=FWA_RESTART_BUTTON)
            else:
                await ctx.edit(error.message, interactions.utils.misc_utils.disable_components(*error.message.components))

        elif isinstance(error, InvalidTagError):
            await ctx.send(f"{get_app_emoji('error')} The {error.tag_type} tag `{error.tag}` is invalid.", ephemeral=True)

        elif isinstance(error, coc.errors.Maintenance):
            await ctx.send(f"{get_app_emoji('error')} It seems that Clash of Clans is having an maintenance break.",
                           ephemeral=True)

        elif "Unknown interaction" in str(error):
            await ctx.send(f"{get_app_emoji('error')} Looks like something is with Discord. Please try again later as you know "
                           f"*Discord is a very stable platform...*", ephemeral=True)

        else:
            full_error = traceback.format_exception(type(error), error, error.__traceback__)
            full_error = "".join(str(i) for i in full_error)
            print(full_error, file=sys.stderr)

            if not ctx:
                return

            if isinstance(error, KeyError) and "clans_button" not in ctx.custom_id:
                await ctx.send(f"{get_app_emoji('error')} The data for the clan select is invalidated, please ask the staff "
                               f"to make a new one for you. Sorry for the inconvenience!\n\n"
                               f"*If this issue persists after remaking the clan select, please contact the developers "
                               f"using the `Report Bug` button! Thanks!*",
                               components=REPORT_BUTTON, ephemeral=True)
            else:
                await ctx.send(f"{get_app_emoji('error')} An unexpected error has occured. Please try again!\n\n"
                               f"*If you believe this is a bug, please press the `Report Bug` button! Thanks!*",
                               components=REPORT_BUTTON, ephemeral=True)

            try:
                res: ipy.ComponentContext = (await self.bot.wait_for_component(components=REPORT_BUTTON, timeout=180)).ctx
            except asyncio.TimeoutError:
                return

            await res.send(f"{get_app_emoji('success')} Thanks for reporting the bug! A message has been sent to the bot developers`, "
                           f"there will be a fix **ASAP**!",
                           ephemeral=True)

            info = f"Component: " if isinstance(ctx, ipy.ComponentContext) else f"Modal: "
            info += f"`{ctx.custom_id}`\n"

            embed = ipy.Embed(
                title=f"**{str(error)}**",
                description=f"```\n{full_error}\n```",
                fields=[
                    ipy.EmbedField(
                        name="**Additional Info**",
                        value=f"Reported by: {ctx.author.mention} `{ctx.author}`\n"
                              f"{info}"
                              f"Arguments: `{ctx.kwargs}`\n",
                        inline=False
                    )
                ],
                footer=ipy.EmbedFooter(
                    text="All For One mailing system",
                ),
                color=COLOR
            )

            bug_respond_button = copy.deepcopy(BUG_RESPOND_BUTTON)
            bug_respond_button.custom_id = f"{BUG_RESPOND_BUTTON.custom_id}|{ctx.author.id}"

            for bot_owner in self.bot.owners:
                await bot_owner.send(embed=embed, components=bug_respond_button)


    @ipy.listen(ipy.events.AutocompleteError, disable_default_listeners=True)
    async def on_autocomplete_error(self, event: ipy.events.AutocompleteError):
        ctx: ipy.AutocompleteContext = event.ctx
        error = event.error

        if isinstance(error, coc.errors.Maintenance):
            await ctx.send([{"name": "Clash of Clans maintenance break", "value": "None"}])

        elif "Unknown interaction" in str(error):
            await ctx.send([{"name": "Something wrong with Discord...", "value": "None"}])

        else:
            await ctx.send([{"name": "Unexpected error, DM master.afo please", "value": "None"}])


    @ipy.listen(ipy.events.CommandError, disable_default_listeners=True)
    async def on_command_error(self, event: ipy.events.CommandError):
        ctx: ipy.SlashContext | None = getattr(event, "ctx", None)
        error = getattr(event, "error", None)

        if ctx is None or getattr(ctx, "channel", None) is None or getattr(ctx.channel, "id", None) is None:
            return  
          
        if isinstance(error, ComponentTimeoutError):
            await ctx.edit(error.message, interactions.utils.misc_utils.disable_components(*error.message.components))

        elif isinstance(error, InvalidTagError):
            await ctx.send(f"{get_app_emoji('error')} The {error.tag_type} tag `{error.tag}` is invalid.", ephemeral=True)

        elif isinstance(error, coc.errors.Forbidden):
            await ctx.send(
                f"{get_app_emoji('error')} Something wrong with CoC API, restarting the bot. Please try again in a few minutes!",
                ephemeral=True)

            bot_restart()

        elif isinstance(error, coc.errors.Maintenance):
            await ctx.send(
                f"{get_app_emoji('error')} It seems that Clash of Clans is having an maintenance break.",
                ephemeral=True)

        elif isinstance(error, ipy.errors.MaxConcurrencyReached):
            await ctx.send(
                f"{get_app_emoji('error')} This command has reached its maximum concurrent usage! Please try again shortly.",
                ephemeral=True)

        elif isinstance(error, ipy.errors.CommandOnCooldown):
            await ctx.send(
                f"{get_app_emoji('error')} Command on cool down, try again in `{error.cooldown.get_cooldown_time()}` seconds!",
                ephemeral=True)

        elif isinstance(error, ipy.errors.CommandCheckFailure):
            await ctx.send(f"{get_app_emoji('error')} You do not have permission to run this command!", ephemeral=True)

        elif "Unknown interaction" in str(error):
            await ctx.send(f"{get_app_emoji('error')} Looks like something is wrong with Discord. Please try again later as you know "
                           f"*Discord is a very stable platform...*", ephemeral=True)

        elif isinstance(error, KeyError) and "clan_name" in ctx.kwargs:
            await ctx.send(f"{get_app_emoji('error')} The field `clan_name` takes in the tag of an alliance clan, and your input "
                           f"`{ctx.kwargs['clan_name']}` is invalid!", ephemeral=True)

        else:
            full_error = traceback.format_exception(type(error), error, error.__traceback__)
            full_error = "".join(str(i) for i in full_error)
            print(full_error, file=sys.stderr)

            if not ctx:
                return

            await ctx.send(f"{get_app_emoji('error')} An unexpected error has occured. Please try again!\n\n"
                           f"*If you believe this is a bug, please press the `Report Bug` button! Thanks!*",
                           components=REPORT_BUTTON, ephemeral=True)

            try:
                res: ipy.ComponentContext = (await self.bot.wait_for_component(components=REPORT_BUTTON, timeout=180)).ctx
            except asyncio.TimeoutError:
                return

            await res.send(f"{get_app_emoji('success')} Thanks for reporting the bug! A message has been sent to the bot developers, "
                           f"there will be a fix **ASAP**!",
                           ephemeral=True)

            full_command = str(ctx.command.name)
            full_command += f" {str(ctx.command.group_name)}" if ctx.command.group_name else ""
            full_command += f" {str(ctx.command.sub_cmd_name)}" if ctx.command.sub_cmd_name else ""

            for key in ctx.kwargs.keys():
                if isinstance(ctx.kwargs[key], (ipy.Member, ipy.GuildChannel, ipy.Role)):
                    ctx.kwargs[key] = ctx.kwargs[key].id

            embed = ipy.Embed(
                title=f"**{str(error)}**",
                description=f"```\n{full_error}\n```",
                fields=[
                    ipy.EmbedField(
                        name="**Additional Info**",
                        value=f"Reported by: {ctx.author.mention} `{ctx.author}`\n"
                              f"Command: `{full_command}`\n"
                              f"Arguments: `{ctx.kwargs}`\n",
                        inline=False
                    )
                ],
                footer=ipy.EmbedFooter(
                    text="All For One mailing system",
                ),
                color=COLOR
            )

            bug_respond_button = copy.deepcopy(BUG_RESPOND_BUTTON)
            bug_respond_button.custom_id = f"{BUG_RESPOND_BUTTON.custom_id}|{ctx.author.id}"

            for bot_owner in self.bot.owners:
                await bot_owner.send(embed=embed, components=bug_respond_button)


    @ipy.component_callback(re.compile(r"^bug_respond_button\|\d+$"))
    async def bug_respond_button(self, ctx: ipy.ComponentContext):
        _, user_id = ctx.custom_id.split("|")

        modal = ipy.Modal(
            ipy.ParagraphText(
                label="What is your response to the bug?",
                value="",
                max_length=300,
                custom_id=user_id
            ),
            title="Bug Response Form",
            custom_id="bug_response_modal",
        )
        await ctx.send_modal(modal)


    @ipy.modal_callback("bug_response_modal")
    async def bug_respond_modal(self, ctx: ipy.ModalContext, **kwargs):
        await ctx.defer(ephemeral=True)

        user = await self.bot.fetch_user(list(ctx.responses.keys())[0], force=True)

        title = f"**Response from {ctx.author} `{ctx.author.id}`**"
        description = f"Dear developers, here is the response from the user who reported this bug." \
                      f"The response is:\n" \
                      f"```{list(ctx.responses.values())[0]}```"

        if ctx.author in self.bot.owners:
            title = "**Response from the Development Team**"
            description = f"Thank you for reporting the bug to the All For One bot developers. " \
                          f"If you have any futher questions please use the response button!" \
                          f"Here is the official response to this issue:\n" \
                          f"```{list(ctx.responses.values())[0]}```"

        embed = ipy.Embed(
            title=title,
            description=description,
            fields=[
                ctx.message.embeds[0].fields[0]
            ],
            footer=ipy.EmbedFooter(
                text="All For One mailing system",
            ),
            color=COLOR,
        )

        ctx.message.components[0].components[0].disabled = True
        await ctx.message.edit(components=ctx.message.components)

        bug_respond_button = copy.deepcopy(BUG_RESPOND_BUTTON)
        bug_respond_button.custom_id = f"{BUG_RESPOND_BUTTON.custom_id}|{ctx.author.id}"

        try:
            await user.send(embed=embed, components=bug_respond_button)
        except ipy.errors.Forbidden:
            await ctx.send(f"{get_app_emoji('error')} Discord forbidden error, the bot do not share servers with the target user!")
        else:
            await ctx.send(f"{get_app_emoji('success')} Your response is sent to the user who reported the bug!")

def setup(bot):
    Errors(bot)