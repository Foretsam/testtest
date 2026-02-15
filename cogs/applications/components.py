import interactions as ipy
import re
import json
import secrets
import copy
import asyncio
from datetime import datetime
from collections import Counter
import coc

from core.checks import *
from core.utils import *
from core.models import *
from core.emojis_manager import *
from core import server_setup as sc
from cogs.general.tickets import *


class ApplicationComponents(ipy.Extension):
    def __init__(self, bot):
        self.bot: ipy.Client = bot

    @ipy.slash_command(name="clan", description="Clan utility")
    async def clan_base(self, ctx: ipy.SlashContext):
        pass

    @ipy.component_callback("support_button")
    async def support_button(self, ctx: ipy.ComponentContext):
        if extract_integer(ctx.channel.topic) != int(ctx.author.id) and \
                extract_alphabets(ctx.author.username) != ctx.channel.name.split("┃")[1]:
            await ctx.send(f"{get_app_emoji('error')} Only the applicant of this channel can request support!",
                           ephemeral=True)
            return

        await ctx.send(f"{get_app_emoji('success')} Human support will arrive soon, in the meanwhile please wait patiently, "
                       f"and please write down how we can help you.",
                       ephemeral=True)
        
        config: sc.GuildConfig = sc.get_config(ctx.guild.id)

        if ctx.channel.parent_id in [
            config.CLAN_TICKETS_CATEGORY,
            config.AFTER_CWL_CATEGORY,
            config.FWA_TICKETS_CATEGORY
        ]:
            await ctx.channel.send(
                f"<@&{config.LEADER_ROLE}> **{ctx.author.user.username}** needs support!"
            )
        elif ctx.channel.parent_id == config.CHAMPIONS_TRIALS_CATEGORY:
            await ctx.channel.send(
                f"<@&{config.MODERATOR_ROLE}> **{ctx.author.user.username}** needs support!"
            )
        elif ctx.channel.parent_id in [
            config.SUPPORT_TICKETS_CATEGORY,
            config.PARTNER_TICKETS_CATEGORY,
            config.STAFF_TRIALS_CATEGORY
        ]:
            await ctx.channel.send(
                f"<@&{config.MODERATOR_ROLE}> **{ctx.author.user.username}** needs support!"
            )

    @ipy.component_callback(re.compile(r"^clan_select\|\w+\|\d+$"))
    async def clan_selection(self, ctx: ipy.ComponentContext):
        await ctx.defer(ephemeral=True)

        message = ctx.message
        packages: dict[str, ApplicationPackage] = json.load(open("data/packages.json", "r"))
        clans_config: dict[str, AllianceClanData] = json.load(open("data/clans_config.json", "r"))

        _, package_token, fillernumber = ctx.custom_id.split("|")

        package = packages[package_token]
        acc_clan = package["acc_clan"]
        user = await self.bot.fetch_member(package["user"], ctx.guild.id, force=True)

        if int(user.id) != int(ctx.author.id):
            await ctx.send(f"{get_app_emoji('error')} You **cannot** interact with other user's components.", ephemeral=True)
            return

        clan_tag = ctx.values[0]
        account_tag = re.search(r"\(#(\w+)\)", ctx.component.placeholder).group(1).replace(")", "")

        clan = await fetch_clan(self.bot.coc, clan_tag)
        player = await fetch_player(self.bot.coc, account_tag)

        acc_clan[player.tag] = clan_tag

        with open("data/packages.json", "w") as file:
            json.dump(packages, file, indent=4)

        ctx.component.placeholder = f"✅ {player.name} ({player.tag}) → {clan.name}"
        ctx.component.disabled = True

        await message.edit(components=message.components)

        clan_msg = "\n".join([msg for msg in clans_config[clan_tag]['msg'].split("|")])
        msg_content = f"__**Key Clan Information**__ `{clan.name}`\n\n{clan_msg}\n\n"
    
        if clan.member_count == 50 and clans_config[clan_tag]['type'] != "FWA":
            msg_content += f"{get_app_emoji('warning')} *`{clan.name}` is currently full. You may still join the clan, but it will take time " \
                        f"as the clan leader will need to make space first!*"
        else:
            msg_content += f"📝 *In-game requests before confirming your clan selection will **not** be accepted!*"

        clan_link_button = ipy.Button(
            style=ipy.ButtonStyle.URL,
            url=clan.share_link,
            label="Clan Link",
            emoji=ipy.PartialEmoji(name="🔗")
        )

        await ctx.send(msg_content, components=clan_link_button, ephemeral=True, delete_after=8)

        if any(not clan_value for clan_value in acc_clan.values()):
            return

        perm_ctx = PermanentContext(ctx.message, ctx.custom_id, ctx.channel, ctx.guild, ctx.deferred, ctx.author,
                                    ctx.kwargs)

        async def check(event: ipy.events.Component):
            if int(event.ctx.author.id) == int(ctx.author.id):
                return True
            await event.ctx.send(f"{get_app_emoji('error')} You cannot interact with other user's components.", ephemeral=True)
            return False

        try:
            await self.bot.wait_for_component(messages=ctx.message, check=check, timeout=300)
        except asyncio.TimeoutError:
            await ctx.send(
                f"{ctx.author.mention} Please confirm your selection, or the bot will **automatically confirm** for you "
                f"due inactivity in 5 more minutes. You may also cancel your current selection and reselect.",
                ephemeral=True)
        else:
            return

        try:
            await self.bot.wait_for_component(messages=ctx.message, check=check, timeout=300)
        except asyncio.TimeoutError:
            await self.clan_confirm(ctx)
    
    @ipy.component_callback(re.compile(r"^clan_confirm\|\w+$"))
    async def clan_confirm(self, ctx: ipy.ComponentContext | PermanentContext):
        await ctx.defer(ephemeral=True) if not ctx.deferred else None
        
        message = ctx.message
        package_token = ctx.custom_id.split("|")[1]
        packages: dict[str, ApplicationPackage] = json.load(open("data/packages.json", "r"))
        clans_config: dict[str, AllianceClanData] = json.load(open("data/clans_config.json", "r"))
    
        package = packages[package_token]
        acc_clan = package["acc_clan"]
        user = await self.bot.fetch_member(package["user"], ctx.guild.id, force=True)

        if int(user.id) != int(ctx.author.id):
            await ctx.send(f"{get_app_emoji('error')} You **cannot** interact with other user's components.", ephemeral=True)
            return

        if not any(acc_clan.values()):
            await ctx.send(f"{get_app_emoji('error')} Please select a clan to apply for **at least one** of your accounts!",
                        ephemeral=True)
            return
        
        await message.edit(components=ipy.utils.misc_utils.disable_components(*message.components))

        embed = ipy.Embed(
            title=f"**Application Summary**",
            description=f"**User Tag:** {user.username}\n"
                        f"**User ID:** {user.id}\n"
                        f"**Channel:** {ctx.channel.mention}\n"
                        f"**Joined at:** {user.joined_at.format(ipy.TimestampStyles.LongDate)}\n"
                        f"**Applied at:** {ipy.Timestamp.fromdatetime(datetime.utcnow()).format(ipy.TimestampStyles.LongDate)}",
            footer=ipy.EmbedFooter(text="Applied Time"),
            timestamp=ipy.Timestamp.utcnow(),
            color=COLOR
        )
    

        player_options = []
        role_mentions = []
        townhall_emoji = None
        player = None
        
        config: sc.GuildConfig = sc.get_config(ctx.guild.id)
        recruitment_role_id = config.RECRUITMENT_ROLE

        for count, (acc, clan) in enumerate(acc_clan.items(), start=1):
            if not clan:
                continue

            player = await fetch_player(self.bot.coc, acc)
            clan = await fetch_clan(self.bot.coc, clan)

            if f"<@&{clans_config[clan.tag]['role']}>" not in role_mentions:
                role_mentions.append(f"<@&{clans_config[clan.tag]['gk_role']}>")

                clan_role = await ctx.guild.fetch_role(clans_config[clan.tag]['gk_role'])
                for member in clan_role.members:
                    member_roles = [int(role.id) for role in member.roles]
                    if recruitment_role_id not in member_roles:
                        continue
                    await ctx.channel.add_permission(
                        target=member.id, type=ipy.OverwriteType.MEMBER,
                        allow=ipy.Permissions.VIEW_CHANNEL | ipy.Permissions.SEND_MESSAGES
                    )

            townhall_emoji = ipy.PartialEmoji.from_str(get_app_emoji(f"Townhall{player.town_hall}"))

            clan_emoji = get_app_emoji('unavailable')
            clan_emoji_name = clans_config[clan.tag]['emoji']
            fetched_emoji = get_app_emoji(clan_emoji_name)
            if ":" in fetched_emoji: 
                clan_emoji = fetched_emoji

            player_summary = f"{get_app_emoji(f'Townhall{player.town_hall}')}[{player.name} ({player.tag})]({player.share_link})\n" \
                            f"{get_app_emoji('reply')} {clan_emoji}[{clan.name} ({clan.tag})]({clan.share_link})\n"

            embed.add_field(
                name=f"Applicant Account #{count}",
                value=player_summary,
                inline=False
            )

            if len([value for value in acc_clan.values() if value]) == 1:
                continue

            player_option = ipy.StringSelectOption(
                label=f"{player.name} ({player.tag})",
                value=player.tag,
                description=f"Applying to {clan.name} ({clan.tag})!",
                emoji=townhall_emoji
            )
            player_options.append(player_option)
        
        formatted_tag2 = player.tag.lstrip("#") 

        player_info = ipy.Button(
            style=ipy.ButtonStyle.URL,
            url = f"https://www.clashofstats.com/players/{formatted_tag2}/army",
            label=f"View Account ({player.tag})",
            emoji=townhall_emoji,
        )

        if player_options:
            player_info = ipy.StringSelectMenu(
                *player_options,
                placeholder="👤 Select a account profile here",
            )

        components = [player_info]

        await ctx.channel.send(LINE_URL)
        await ctx.channel.send(
            f"\n".join(role_mentions),
            embeds=[embed],
            components=ipy.spread_to_rows(*components) if isinstance(player_info, ipy.StringSelectMenu) else [
                ipy.ActionRow(*components)]
        )
        await ctx.channel.send(LINE_URL)

        try:
            clan_prefix = clans_config[list(acc_clan.values())[0]]['prefix'].translate(PREFIX_DICT)
            parent_id = config.CLAN_TICKETS_CATEGORY if int(
                ctx.channel.category.id) == config.FWA_TICKETS_CATEGORY else ctx.channel.category.id
            await ctx.channel.edit(name=f"{clan_prefix}┃{user.user.username}", parent_id=parent_id)
        except (ipy.errors.DiscordError, ipy.errors.RateLimited, ipy.errors.Forbidden):
            pass

        if isinstance(ctx, ipy.ComponentContext):
            await ctx.send(
                f"{get_app_emoji('success')} **Thank you** for applying, please wait patiently for the clan leaders!",
                ephemeral=True, delete_after=4
            )

        unique_clan_tags = list(set([clan for clan in acc_clan.values() if clan]))
        
        questions_content = ""
        for tag in unique_clan_tags:
            if tag not in clans_config:
                continue

            clan_data = clans_config[tag]
            clan_name = clan_data['name']
            
            raw_questions = clan_data.get('questions', "")
            
            if not raw_questions or raw_questions == "None":
                continue

            q_list = [q.strip() for q in raw_questions.split("|") if q and q.strip() != "None"]
            
            if q_list:
                formatted_questions = "\n".join(q_list)
                questions_content += f"**Welcome to {clan_name}**\n{formatted_questions}\n\n"

        if questions_content:
            await ctx.channel.send(questions_content)

    @ipy.component_callback(re.compile(r"^clan_cancel\|\w+$"))
    async def clan_cancel(self, ctx: ipy.ComponentContext):
        packages: dict[str, ApplicationPackage] = json.load(open("data/packages.json", "r"))
        package_token = ctx.custom_id.split("|")[1]
        package = packages[package_token]
        user = await self.bot.fetch_member(package["user"], ctx.guild.id, force=True)

        if int(user.id) != int(ctx.author.id):
            await ctx.send(f"{get_app_emoji('error')} You **cannot** interact with other user's components.", ephemeral=True)
            return

        for count, action_row in enumerate(ctx.message.components):
            for component in action_row.components:
                if component.type == ipy.ComponentType.STRING_SELECT and not component.placeholder.endswith("not eligible"):
                    player_tag = package["account_tags"][count]
                    player = await fetch_player(self.bot.coc, player_tag)

                    component.disabled = False
                    component.placeholder = f"{NUMBER_EMOJIS[count + 1]} Select a clan for {player.name} ({player.tag})"

                    package["acc_clan"][player_tag] = None

        with open("data/packages.json", "w") as file:
            json.dump(packages, file, indent=4)

        await ctx.message.edit(components=ctx.message.components)
        await ctx.send(f"{get_app_emoji('success')} Your previous clan selections has been **canceled**, please reselect now!",
                    ephemeral=True)

    @clan_base.subcommand(sub_cmd_name="select", sub_cmd_description="Generate clan selection")
    @has_roles("RECRUITMENT_ROLE", "SERVER_DEVELOPMENT_ROLE", "LEADER_ROLE")
    @ipy.slash_option(name="user", description="A server member", opt_type=ipy.OptionType.USER, required=True)
    @ipy.slash_option(name="player_tag1", description="User's 1st tag", opt_type=ipy.OptionType.STRING, required=True, autocomplete=True)
    async def clan_select(self, ctx: ipy.SlashContext, user: ipy.Member, player_tag1: str = "None"):
        await ctx.defer(ephemeral=True)
        config: sc.GuildConfig = sc.get_config(ctx.guild.id)
        if int(ctx.channel.parent_id) not in [config.CLAN_TICKETS_CATEGORY, config.AFTER_CWL_CATEGORY, config.FWA_TICKETS_CATEGORY]:
            await ctx.send(f"{get_app_emoji('error')} This command can only be used in interview/application channels.")
            return

        some_tags = " ".join([player_tag1])
        account_tags = await extract_tags(self.bot.coc, some_tags, context=ctx)

        if not account_tags:
            await ctx.send(f"{get_app_emoji('error')} Not a single valid player tag is provided!")
            return

        await fetch_emojis(self.bot, update=True)

        clans_config: dict[str, AllianceClanData] = json.load(open("data/clans_config.json", "r"))
        package_token = secrets.token_hex(8)
        normal_clans = [i for i in list(clans_config.keys())]

        clan_options = {}
        clan_actionrows = []
        acc_clan = {}
        acc_images = {}
        for count, account in enumerate(account_tags, start=1):
            if not account: continue

            player = await fetch_player(self.bot.coc, account)
            clan_count = 0
            acc_clan[account] = None
            acc_images[account] = None
            for key in normal_clans:
                try: value = clans_config[key]
                except KeyError: continue
                if clan_count >= 30: break
                if not value["recruitment"]: continue
                if value["type"] == "FWA": continue

                player_qualification = True
                if extract_integer(value['requirement']) > player.town_hall: continue
                max_th_str = value.get("maximum_possibleTH")
                if max_th_str and player.town_hall > extract_integer(max_th_str): continue

                for check, check_kwargs in value["checks"].items():
                    if "client" in get_func_params(CLAN_CHECKS[check]):
                        check_kwargs["client"] = self.bot.coc
                    check_result = await ipy.utils.maybe_coroutine(CLAN_CHECKS[check], player, **check_kwargs)
                    if not check_result:
                        player_qualification = False
                        break

                if not player_qualification: continue

                clan_count += 1
                clan = await fetch_clan(self.bot.coc, key)
                clan_league = str(clan.war_league).replace("League ", "")

                iclan_emoji = ipy.PartialEmoji.from_str(get_app_emoji('unavailable'))
                if value["emoji"]:
                    emoji_str = get_app_emoji(value["emoji"])
                    if "<" in emoji_str and ">" in emoji_str:
                        iclan_emoji = ipy.PartialEmoji.from_str(emoji_str)

                capital_level = clan.capital_districts[0].hall_level if clan.capital_districts else 0
                option_label = f"{value['name']} (ER)" if player_qualification == "ER" else value['name']
                if "(ER)" not in option_label and clan.member_count == 50:
                    option_label += " (Full)"

                clan_option = ipy.StringSelectOption(
                    label=option_label,
                    value=f"{key}",
                    description=f"{clan_league} | Level {clan.level} | CH{capital_level} | {value['type']} | {value['requirement']}",
                    emoji=iclan_emoji
                )

                if player.tag not in clan_options.keys():
                    clan_options[player.tag] = [clan_option]
                    continue
                clan_options[player.tag].append(clan_option)

            clan_select_id = f"clan_select|{package_token}|{count}"

            if player.tag not in clan_options.keys():
                clan_select = ipy.StringSelectMenu(
                    ipy.StringSelectOption(label="No Clans Available", value="No Clans Available", description="No Clans Available"),
                    placeholder=f"❌ {player.name} ({player.tag}) is not eligible",
                    custom_id=clan_select_id,
                    disabled=True
                )
            else:
                clan_select = ipy.StringSelectMenu(
                    *clan_options[player.tag],
                    placeholder=f"{NUMBER_EMOJIS[count]} Select a clan for {player.name} ({player.tag})",
                    custom_id=clan_select_id,
                )

            clan_actionrow = ipy.ActionRow(clan_select)
            clan_actionrows.append(clan_actionrow)

        packages: dict[str, ApplicationPackage] = json.load(open("data/packages.json", "r"))
        cancel_id = f"clan_cancel|{package_token}"
        cancel_button = ipy.Button(style=ipy.ButtonStyle.DANGER, label="Cancel", custom_id=cancel_id, emoji=get_app_emoji('cross'))
        confirm_id = f"clan_confirm|{package_token}"
        confirm_button = ipy.Button(style=ipy.ButtonStyle.SUCCESS, label="Confirm", custom_id=confirm_id, emoji=get_app_emoji('tick'))

        button_actionrow = ipy.ActionRow(cancel_button, confirm_button)
        clan_actionrows.append(button_actionrow)

        embed = ipy.Embed(
            title=f"**Can you select a clan you would like to apply for each of your account?**",
            description=f"- You can choose the same clan for each of your accounts.\n"
                        f"- In the clan description, `CH` stands for **\"Capital Hall\"**\n"
                        f"- If the clan you want to join cannot be selected, talk to the staff.",
            footer=ipy.EmbedFooter(text="Feel free to ask for help for any confusions."),
            color=COLOR
        )
        msg = await ctx.channel.send(f"{user.user.mention} Please select a clan!", embed=embed, components=clan_actionrows)

        await ctx.send(f"{get_app_emoji('success')} Clan selection is generated!")

        package = {
            "account_tags": account_tags, "acc_clan": acc_clan, 
            "acc_images": acc_images, "user": int(user.id), 
            "message_id": int(msg.id), "channel_id": int(ctx.channel.id)
        }
        packages[package_token] = package

        with open("data/packages.json", "w") as file:
            json.dump(packages, file, indent=4)

    @ipy.global_autocomplete(option_name="player_tag1")
    async def player_tag1_autocomplete(self, ctx: ipy.AutocompleteContext):
        if "user" not in ctx.kwargs:
            tag_choice = [{"name": "Please choose a user first", "value": "None"}]
            await ctx.send(tag_choice)
            return

        player_links = json.load(open("data/member_tags.json", "r"))
        if not player_links.get(ctx.kwargs["user"]):
            tag_choice = [{"name": "No accounts linked to this player", "value": "None"}]
            await ctx.send(tag_choice)
            return

        tag_choices = []
        for tag in copy.deepcopy(player_links[ctx.kwargs["user"]]):
            try: player = await fetch_player(self.bot.coc, tag)
            except coc.errors.NotFound:
                player_links[ctx.kwargs["user"]].remove(tag)
                continue
            name = f"[TH{player.town_hall}] {player.name} ({player.tag})"
            tag_choices.append({"name": name, "value": tag})

        await ctx.send(tag_choices)
        with open("data/member_tags.json", "w") as file:
            json.dump(player_links, file, indent=4)


class EmbedCommands(ipy.Extension):
    def __init__(self, bot):
        self.bot: ipy.Client = bot

    embed_base = ipy.SlashCommand(
        name="embed", description="Embed utility", 
        scopes=None
    )

    @embed_base.subcommand(sub_cmd_name="clan", sub_cmd_description="Live clan embed")
    async def embed_clan(self, ctx: ipy.SlashContext):
        await ctx.defer(ephemeral=True)

        config: sc.GuildConfig = sc.get_config(ctx.guild.id)
        family_member_count = 0
        if config.FAMILY_ROLE:
            try:
                family_member_role = await ctx.guild.fetch_role(config.FAMILY_ROLE)
                family_member_count = len(family_member_role.members)
            except: pass
        
        # Safely get FWA channel ID, defaulting to a placeholder if not found
        fwa_id = globals().get('FWA_CHANNEL', 0)
        fwa_mention = f"<#{fwa_id}>" if fwa_id else "#fwa-channel"
        
        # Safely get Banner
        banner = globals().get('BANNER_URL')

        live_embed = ipy.Embed(
            title=f"**All For One Alliance Clans**",
            description=f"{get_app_emoji('diamond')} All For One is **honored** to provide an amazing clan "
                        f"for your personalized clash experience! We consist of 10 clans ready "
                        f"to welcome you. Are you competitive? We got the perfect clan for you. "
                        f"Maybe you just want to kick your feet up and chill? We got you as well! "
                        f"Look no further, join a clan today.\n\n"
                        f"__**Types of Clans We Offer**__\n"
                        f"- {get_app_emoji('comp_clan')} Competitive (War Focused)\n"
                        f"- {get_app_emoji('fwa_clan')} FWA (Farm War Alliance)\n"
                        f" - What is FWA? → Please check {fwa_mention}! \n\n"
                        f"*To check out the details of our clans, please press the buttons attached to this embed!*",
            images=[ipy.EmbedAttachment(url=banner)] if banner else [],
            footer=ipy.EmbedFooter(
                text=f"Family Members: {family_member_count}",
                icon_url=FAMILY_ICON_URL
            ),
            color=COLOR
        )

        comp_button = ipy.Button(style=ipy.ButtonStyle.SECONDARY, label="Competitive Clans", custom_id="comp_clans_button", emoji=ipy.PartialEmoji(name="SwordsClashing", id=1318281743001845843, animated=True))
        fwa_button = ipy.Button(style=ipy.ButtonStyle.SECONDARY, label="FWA Clans", custom_id="fwa_clans_button", emoji=ipy.PartialEmoji(name="SwordBlue", id=1318281942394994769))
        cwl_button = ipy.Button(style=ipy.ButtonStyle.SECONDARY, label="CWL Only Clans", custom_id="cwl_clans_button", emoji=ipy.PartialEmoji(name="CwlChampion1", id=1318203772320616539))        
        button_actionrow = ipy.ActionRow(comp_button, fwa_button, cwl_button)

        await ctx.channel.send(embeds=[live_embed], components=button_actionrow)
        await ctx.send(f"{get_app_emoji('success')} Live embed is successfully created!", ephemeral=True)

    @ipy.component_callback(re.compile(r"^\w+_clans_button$"))
    async def clans_buttons(self, ctx: ipy.ComponentContext):
        await ctx.defer(ephemeral=True)

        data = CLAN_TYPE_DATA[ctx.custom_id.split("_")[0]]
        alliance_clans: dict[str, AllianceClanData] = json.load(open("data/clans_config.json", "r"))
        normal_clans = list(alliance_clans.keys())

        await fetch_emojis(self.bot, update=True)

        clan_embed = None
        clan_options = []
        for key in normal_clans:
            try: value = alliance_clans[key]
            except KeyError: continue
            if value["type"].lower() != data.lower(): continue

            clan = await fetch_clan(self.bot.coc, key)
            if not clan_embed:
                league_emoji = get_app_emoji(str(clan.war_league).replace("League ", ""))
                clan_description = clan.description if clan.description else "There is no clan description, it seems that the leader is too lazy..."
                clan_townhalls = [member.town_hall for member in clan.members]
                clan_compo = dict(Counter(clan_townhalls))
                clan_compo_text = " | ".join(f"{num}{get_app_emoji(f'Townhall{th}')}" for th, num in clan_compo.items())

                clan_embed = ipy.Embed(
                    title=f"**{clan.name}** `{clan.tag}`",
                    description=f"{get_app_emoji('leader')}<@{value['leader']}>\n"
                                f"⚙️{value['requirement']}\n"
                                f"🔗[In-game Link]({clan.share_link})\n"
                                f"{get_app_emoji('trophy')}{clan.points} {get_app_emoji('vstrophy')}{clan.builder_base_points}\n\n"
                                f"{clan_description}\n",
                    fields=[
                        ipy.EmbedField(name=f"**Clan Level**", value=f"{get_app_emoji('clanshield')}{clan.level}", inline=False),
                        ipy.EmbedField(name=f"**CWL League**", value=f"{league_emoji}{clan.war_league}", inline=False),
                        ipy.EmbedField(name=f"**Clan Capital**", value=f"{get_app_emoji('capital')}{clan.capital_districts[0].hall_level} ({clan.capital_league})" if clan.capital_districts else f"{get_app_emoji('capital')} 0 (Unranked)", inline=False),
                        ipy.EmbedField(name=f"**Clan Composition**", value=clan_compo_text if clan_compo else "Failed to get the clan composition...", inline=False),
                        ipy.EmbedField(name=f"**Clan Aspirations**", value=value['msg'].replace('|', '\n'), inline=False),
                    ],
                    footer=ipy.EmbedFooter(text=f"Clan Members: {clan.member_count}/50", icon_url=FAMILY_ICON_URL),
                    thumbnail=ipy.EmbedAttachment(url=clan.badge.url),
                    color=COLOR
                )

            iclan_emoji = ipy.PartialEmoji(name="Unavailable", id=1318284335580975125)
            emoji_str = get_app_emoji(value["emoji"])
            if "<" in emoji_str and ">" in emoji_str:
                iclan_emoji = ipy.PartialEmoji.from_str(emoji_str)

            clan_league = str(clan.war_league).replace("League ", "")
            capital_level = clan.capital_districts[0].hall_level if clan.capital_districts else 0

            clan_option = ipy.StringSelectOption(
                label=value['name'],
                value=clan.tag,
                description=f"{clan_league} - Level {clan.level} - CH{capital_level} - {value['type']} - {value['requirement']}",
                emoji=iclan_emoji
            )
            clan_options.append(clan_option)

        if not clan_options:
            await ctx.send(f"Currently there are no {data} clans in the alliance...")
            return

        clan_select = ipy.StringSelectMenu(
            *clan_options,
            placeholder=f"📚 Select a {data} clan here",
            custom_id="live_clan_select"
        )

        await ctx.send("Please select a clan from the list below to view details.", embeds=[clan_embed], components=clan_select)

    @ipy.component_callback("live_clan_select")
    async def live_clan_select(self, ctx: ipy.ComponentContext):
        alliance_clans: dict[str, AllianceClanData] = json.load(open("data/clans_config.json", "r"))
        clan = await fetch_clan(self.bot.coc, ctx.values[0])

        clan_dict = alliance_clans[clan.tag]
        league_emoji = get_app_emoji(str(clan.war_league).replace("League ", ""))
        clan_description = clan.description if clan.description else "There is no clan description, it seems that the leader is too lazy..."
        clan_townhalls = [member.town_hall for member in clan.members]
        clan_compo = dict(Counter(clan_townhalls))
        clan_compo_text = " | ".join(f"{num}{get_app_emoji(f'Townhall{th}')}" for th, num in clan_compo.items())

        clan_embed = ipy.Embed(
            title=f"**{clan.name}** `{clan.tag}`",
            description=f"{get_app_emoji('leader')}<@{clan_dict['leader']}>\n"
                        f"⚙️{clan_dict['requirement']}\n"
                        f"🔗[In-game Link]({clan.share_link})\n"
                        f"{get_app_emoji('trophy')}{clan.points} {get_app_emoji('vstrophy')}{clan.builder_base_points}\n\n"
                        f"{clan_description}\n",
            fields=[
                ipy.EmbedField(name=f"**Clan Level**", value=f"{get_app_emoji('clanshield')}{clan.level}", inline=False),
                ipy.EmbedField(name=f"**CWL League**", value=f"{league_emoji}{clan.war_league}", inline=False),
                ipy.EmbedField(name=f"**Clan Capital**", value=f"{get_app_emoji('capital')}{clan.capital_districts[0].hall_level} ({clan.capital_league})" if clan.capital_districts else f"{get_app_emoji('capital')} 0 (Unranked)", inline=False),
                ipy.EmbedField(name=f"**Clan Composition**", value=clan_compo_text, inline=False),
                ipy.EmbedField(name=f"**Clan Aspirations**", value=clan_dict['msg'].replace('|', '\n'), inline=False),
            ],
            footer=ipy.EmbedFooter(text=f"Clan Members: {clan.member_count}/50", icon_url=FAMILY_ICON_URL),
            thumbnail=ipy.EmbedAttachment(url=clan.badge.url),
            color=COLOR
        )
        await ctx.edit_origin(embeds=[clan_embed], components=ctx.message.components)

    @embed_base.subcommand(sub_cmd_name="apply", sub_cmd_description="Application embed")
    @ipy.slash_option(
        name="layout_type", description="Type of the application embed", opt_type=ipy.OptionType.STRING,
        choices=[
            ipy.SlashCommandChoice(name="Clan", value="Clan"),
            ipy.SlashCommandChoice(name="FWA", value="FWA"),
            ipy.SlashCommandChoice(name="Staff", value="Staff"),
            ipy.SlashCommandChoice(name="Champions", value="Champions"),
            ipy.SlashCommandChoice(name="Coaching", value="Coaching"),  
            ipy.SlashCommandChoice(name="Support", value="Support"),   
            ipy.SlashCommandChoice(name="Partner", value="Partner"),             
        ],
        required=True
    )
    async def embed_apply(self, ctx: ipy.SlashContext, layout_type: str):
        style = ipy.ButtonStyle.SECONDARY
        arrow_emoji = get_app_emoji('arrow')
        diamond_emoji = get_app_emoji('diamond')
        
        # Safely fetch Banner URL (defaults to BANNER_URL if specific one missing)
        banner = globals().get('BANNER_URL') # Fallback default
        
        # Safely fetch channels
        clan_info_id = globals().get('CLAN_INFO_CHANNEL', 0)
        clan_info_mention = f"<#{clan_info_id}>" if clan_info_id else "#clan-info"
        fwa_id = globals().get('FWA_CHANNEL', 0)
        fwa_mention = f"<#{fwa_id}>" if fwa_id else "#fwa-info"
        
        if layout_type.lower() == "clan":
            apply_emoji = ipy.PartialEmoji(name="🔰")
            style = ipy.ButtonStyle.BLURPLE
            if 'CLAN_BANNER_URL' in globals(): banner = CLAN_BANNER_URL
            
            embed = ipy.Embed(
                title=f"**All For One Clan Application**",
                description=f"{arrow_emoji} Simply press the button **\"Apply Now\"**, then a channel will be created for an interview.\n"
                            f"{arrow_emoji} For the interview, you will have to answer a few short questions.\n"
                            f"{arrow_emoji} After the interview, the bot will provide clans that will fit you.\n"
                            f"{arrow_emoji} Lastly, we hope that you will find a new home here.\n"
                            f"{arrow_emoji} For all clan details, please check {clan_info_mention}\n",
                images=[ipy.EmbedAttachment(url=banner)] if banner else [],
                color=COLOR
            )
        elif layout_type.lower() == "staff":
            apply_emoji = ipy.PartialEmoji(name="👨‍💼")
            if 'STAFF_BANNER_URL' in globals(): banner = STAFF_BANNER_URL

            embed = ipy.Embed(
                title=f"**All For One Staff Application**",
                description=f"{arrow_emoji} Simply press the button **\"Apply Now\"**, then a channel will be created for an interview.\n"
                            f"{arrow_emoji} For the interview, you will have to answer a few short questions.\n"
                            f"{arrow_emoji} After the interview, the moderators will evaluate your responses.\n"
                            f"{arrow_emoji} Lastly, we will determine whether you are eligible or not.\n",
                images=[ipy.EmbedAttachment(url=banner)] if banner else [],
                color=COLOR
            )
        elif layout_type.lower() == "fwa":
            apply_emoji = ipy.PartialEmoji(name="💎")
            if 'FWA_BANNER_URL' in globals(): banner = FWA_BANNER_URL

            embed = ipy.Embed(
                title=f"**All For One FWA Application**",
                description=f"{diamond_emoji} If you want to join FWA in this alliance, please "
                            f"press the button **\"Apply Now\"**!\n\n"
                            f"Before applying for FWA make sure to have a good understanding of FWA by checking "
                            f"{fwa_mention} and read the **FWA Rules and Regulations**. So that you will not "
                            f"be removed from FWA for breaking the rules!",
                images=[ipy.EmbedAttachment(url=banner)] if banner else [],
                color=COLOR
            )
        elif layout_type.lower()== "champions":
            apply_emoji = ipy.PartialEmoji(name="👑")
            if 'CHAMPIONS_BANNER_URL' in globals(): banner = CHAMPIONS_BANNER_URL

            embed = ipy.Embed(
                title=f"**All For One Clan Champions Trials**",
                description=f"{arrow_emoji} Simply press the button **\"Apply Now\"**, then a channel will be created for an interview.\n"
                            f"{arrow_emoji} For the interview, you will have to answer a few short questions.\n"
                            f"{arrow_emoji} Before applying, we only accept th18 for champions.\n"
                            f"{arrow_emoji} We also don't accept casuals in champions cwl, effort will be required.\n",
                images=[ipy.EmbedAttachment(url=banner)] if banner else [],
                color=COLOR
            )
        elif layout_type.lower()== "coaching":
            apply_emoji = ipy.PartialEmoji(name="🔥")
            if 'COACHING_BANNER_URL' in globals(): banner = COACHING_BANNER_URL

            embed = ipy.Embed(
                title=f"**All For One Clan Coaching**",
                description=f"{arrow_emoji} Simply press the button **\"Apply Now\"**, then a channel will be created for an interview.\n"
                            f"{arrow_emoji} For the interview, you will have to answer a few short questions.\n"
                            f"{arrow_emoji} After the questions, a coach will get in contact in the ticket to set a time for the coaching to happen.",
                images=[ipy.EmbedAttachment(url=banner)] if banner else [],
                color=COLOR
            ) 
        elif layout_type.lower()=="support":
            apply_emoji = ipy.PartialEmoji(name="🔐")
            if 'SUPPORT_BANNER_URL' in globals(): banner = SUPPORT_BANNER_URL

            embed = ipy.Embed(
                title=f"**All For One Support**",
                description=f"{arrow_emoji} Simply press the button **\"Create Ticket\"**, then a channel will be created.\n"
                            f"{arrow_emoji} Our support channel is limited to this server matters only.\n"
                            f"{arrow_emoji} Open a ticket if: Bugs on any of the alliance bots, miss conduct of any members or staff, any doubts on the server or also simply being lost and not knowing where stuff is, if you would like for us to implement your idea, use suggestions channel instead.",
                images=[ipy.EmbedAttachment(url=banner)] if banner else [],
                color=COLOR
            )      
        elif layout_type.lower() == "partner":
            apply_emoji = ipy.PartialEmoji(name="💼")
            if 'PARTNER_BANNER_URL' in globals(): banner = PARTNER_BANNER_URL

            embed = ipy.Embed(
                title=f"**All For One Partner Application**",
                description=f"{arrow_emoji} Simply press the button **\"Apply Now\"**, then a channel will be created for an interview.\n"
                            f"{arrow_emoji} For the interview, you will have to answer a few short questions.\n"
                            f"{arrow_emoji} After the interview, the moderators will evaluate your responses.\n"
                            f"{arrow_emoji} Lastly, we will determine whether you are eligible or not.\n",
                images=[ipy.EmbedAttachment(url=banner)] if banner else [],
                color=COLOR
            )          
        
        embed.set_footer(text="Feel free to message in visitor-chat for any confusions!")
        
        label_text = "Create Ticket" if layout_type.lower() == "support" else "Apply Now"
        apply_button = ipy.Button(
            style=style, label=label_text, custom_id=f"{layout_type.lower()}_apply_button", emoji=apply_emoji
        )   

        await ctx.channel.send(embeds=[embed], components=apply_button)
        await ctx.send(f"{get_app_emoji('success')} {layout_type} application embed is created!", ephemeral=True)

    @ipy.component_callback(re.compile(r"^\w+_apply_button$"))
    async def apply_buttons(self, ctx: ipy.ComponentContext):
        await ctx.defer(ephemeral=True)
        member = ctx.author
        ticket_type = ctx.custom_id.split('_')[0]
        channel = await TicketManager.create_ticket(ctx, member, ticket_type, self.bot)
        if not channel: return

        if ticket_type.lower() == "support":
            await ctx.send(f"{get_app_emoji('success')} Channel {channel.mention} is created. Please go there to start your Ticket.", ephemeral=True)
        else:
            await ctx.send(f"{get_app_emoji('success')} Channel {channel.mention} is created. Please go there to start your interview.", ephemeral=True)

def setup(bot):
    ApplicationComponents(bot)
    EmbedCommands(bot)