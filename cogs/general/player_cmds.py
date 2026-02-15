import interactions as ipy
import json
import copy
import asyncio
import coc
import random
import emoji

from core.utils import *
from core.models import *
from core.emojis_manager import *
from core import server_setup as sc

class PlayerCmds(ipy.Extension):
    def __init__(self, bot):
        self.bot: ipy.Client = bot

    @ipy.slash_command(name="player", description="Player utility for All For One family")
    async def player_base(self, ctx: ipy.SlashContext):
        pass

    @player_base.subcommand(sub_cmd_name="whois", sub_cmd_description="Check the Clash of Clans accounts linked to a user")
    @ipy.slash_option(
        name="user",
        description="Choose a user from this server",
        opt_type=ipy.OptionType.USER,
        required=True
    )
    @ipy.slash_option(
        name="hidden",
        description="Make the message hidden?",
        opt_type=ipy.OptionType.BOOLEAN
    )
    async def player_whois(self, ctx: ipy.SlashContext, user: ipy.Member, hidden: bool = True):
        await ctx.defer(ephemeral=True if hidden else False)

        player_links = json.load(open("data/member_tags.json", "r"))

        if isinstance(user, str):
            await ctx.send(
                f"{get_app_emoji('error')} Cannot get this user object. The user does not share any server with the bot.",
                ephemeral=True)

            return

        if not player_links.get(str(user.id)):
            await ctx.send(f"{get_app_emoji('error')} No account is linked to this user!", ephemeral=True)

            return

        player_profiles = []
        player_options = []

        count = 0
        player_summary = ""

        for tag in copy.deepcopy(player_links[str(user.id)]):
            try:
                player = await fetch_player(self.bot.coc, tag)
            except coc.errors.NotFound:
                player_links[str(user.id)].remove(tag)
                continue

            count += 1
            
            townhall = f"{get_app_emoji(f'Townhall{player.town_hall}')}`{player.town_hall}`"

            pets = ""
            if player.town_hall >= 14:
                pet_count = 0
                for pet in player.pets:
                    pet_count += 1
                    if pet_count == 5:
                        pets += "\n"
                    
                    clean_pet_name = pet.name.replace(".", "").replace(" ", "")
                    pets += f"{get_app_emoji(clean_pet_name)}`{pet.level}`"

            war = player.war_stars
            war = f"{get_app_emoji('coc_star')}`{str(war)}`"

            heroes = ""
            hsum = 0
            
            hero_name_map = {
                "Barbarian King": "BK", 
                "Archer Queen": "AQ", 
                "Grand Warden": "GW", 
                "Royal Champion": "RC", 
                "Minion Prince": "MP"
            }

            for scan in player.heroes:
                if scan.is_home_base:
                    short_name = hero_name_map.get(scan.name, scan.name.replace(" ", ""))
                    
                    heroes += f"{get_app_emoji(short_name)}`{scan.level}`"
                    hsum += scan.level

            click_emoji = get_app_emoji('click')
            link = "https://www.clashofstats.com/players/{}-{}/summary/".format(player.name, player.tag)
            link = link.replace(" ", "-").replace("#", "").replace("@", "%2540").lower()
            
            link = "".join(i for i in player.name if not emoji.is_emoji(i))

            clan = player.clan

            xplvl = f"{get_app_emoji('experience')}{player.exp_level}"

            fields = [
                ipy.EmbedField(
                    name=f"**General Information**",
                    value=f"**Townhall:**\n{townhall}\n"
                        f"**Experience:**\n{xplvl}\n"
                        f"**War Stars:**\n{war}\n",
                    inline=False)
            ]

            progress_value = ""

            if heroes:
                progress_value += f"**Heroes:**\n{heroes}\n"

            if pets:
                progress_value += f"**Pets:**\n{pets}\n"

            fields.append(
                ipy.EmbedField(
                    name=f"**Progress Information**",
                    value=progress_value,
                    inline=False
                )
            )

            townhall_emoji = ipy.PartialEmoji.from_str(get_app_emoji(f"Townhall{player.town_hall}"))

            if not player.clan:
                fields.append(
                    ipy.EmbedField(
                        name="**Season Information**",
                        value=f"**Donations:**\n{get_app_emoji('donated')}`{player.donations}` {get_app_emoji('received')}`{player.received}`\n"
                            f"**Multiplayer:**\n{get_app_emoji('attack')}`{player.attack_wins}` {get_app_emoji('defense')}`{player.defense_wins}`\n"
                            f"**Clan:**\n{get_app_emoji('clan_logo')} Not in a clan",
                        inline=False)
                )
                player_option = ipy.StringSelectOption(label=f"{player.name} ({player.tag})",
                                                    value=str(count),
                                                    description=f"Not in a clan",
                                                    emoji=townhall_emoji)

                player_summary += f"{townhall_emoji} [{player.name} ({player.tag})]({player.share_link})\n"
                if heroes:
                    player_summary += f"{heroes}\n"

                player_summary += f"Not in a clan\n\n"

            else:
                fields.append(
                    ipy.EmbedField(
                        name="**Season Information**",
                        value=f"**Donations:**\n{get_app_emoji('donated')}{player.donations} {get_app_emoji('received')}{player.received}\n"
                            f"**Attacks&Defenses:**\n{get_app_emoji('attack')}{player.attack_wins} {get_app_emoji('defense')}{player.defense_wins}\n"
                            f"**Clan:**\n{get_app_emoji('clan_logo')}[{player.clan}]({clan.share_link}) ({player.role})",
                        inline=False)
                )
                player_option = ipy.StringSelectOption(label=f"{player.name} ({player.tag})",
                                                    value=str(count),
                                                    description=f"{player.role} of {player.clan}",
                                                    emoji=townhall_emoji)

                player_summary += f"{townhall_emoji} [{player.name} ({player.tag})]({player.share_link})\n"
                if heroes:
                    player_summary += f"{heroes}\n"

                player_summary += f"{player.role} of {player.clan}\n\n"

            player_options.append(player_option)

            embed = ipy.Embed(
                title=f"**{player.name}** `{player.tag}`",
                description=f"{click_emoji} [Clash of Stats Profile]({link})\n"
                            f"{click_emoji} [In Game Profile]({player.share_link})",
                fields=fields,
                author=ipy.EmbedAuthor(
                    name=f"{user.username}",
                    icon_url=user.avatar.url
                ),
                footer=ipy.EmbedFooter(
                    text=f"Requested by {ctx.author.username}",
                    icon_url=ctx.author.avatar.url
                ),
                timestamp=ipy.Timestamp.utcnow(),
                color=COLOR
            )
            player_profiles.append(embed)

        with open("data/member_tags.json", "w") as file:
            json.dump(player_links, file, indent=4)

        footer = ipy.EmbedFooter(
            text=f"{count} account linked in total!" if count == 1 else f"{count} accounts linked in total!"
        )

        embed = ipy.Embed(
            title=f"**Player Summary**",
            description=player_summary,
            author=ipy.EmbedAuthor(
                name=f"{user.username}",
                icon_url=user.avatar.url
            ),
            footer=footer,
            color=COLOR,
        )

        player_option = ipy.StringSelectOption(
            label=f"Player Summary",
            value="0",
            description=f"A summary showing all accounts linked to this user",
            emoji=ipy.PartialEmoji(name="📖")
        )

        player_options.append(player_option)
        player_profiles.append(embed)

        player_select = ipy.StringSelectMenu(
            *player_options,
            placeholder="👤 Select account profiles here",
            custom_id="account_select"
        )

        msg = await ctx.send(embeds=[embed], components=player_select)

        async def check(event: ipy.events.Component):
            if int(event.ctx.author.id) == int(ctx.author.id):
                return True
            await event.ctx.send(f"{get_app_emoji('error')} You cannot interact with other user's components.", ephemeral=True)
            return False

        while True:
            try:
                res: ipy.ComponentContext = (await self.bot.wait_for_component(components=player_select, check=check,
                                                                        messages=int(msg.id), timeout=180)).ctx
            except asyncio.TimeoutError:
                raise ComponentTimeoutError(message=msg)

            await res.edit_origin(embeds=[player_profiles[int(res.values[0]) - 1]], components=player_select)

    @player_base.subcommand(sub_cmd_name="link", sub_cmd_description="Link Clash of Clans accounts to a user")
    @has_roles("RECRUITMENT_ROLE", "SERVER_DEVELOPMENT_ROLE", "LEADER_ROLE")
    @ipy.slash_option(
        name="user",
        description="Choose a user from this server",
        opt_type=ipy.OptionType.USER,
        required=True
    )
    @ipy.slash_option(
        name="player_tags",
        description="Separate the tags with a comma",
        opt_type=ipy.OptionType.STRING,
        required=True
    )
    async def player_link(self, ctx: ipy.SlashContext, user: ipy.Member, player_tags: str):
        await ctx.defer(ephemeral=True)

        player_links = json.load(open("data/member_tags.json", "r"))
        player_links_reversed = reverse_dict(player_links)

        valid_tags = await extract_tags(self.bot.coc, player_tags, context=ctx)

        if not valid_tags:
            return

        if isinstance(user, str):
            await ctx.send(
                f"{get_app_emoji('error')} Cannot get this user object. The user does not share any server with the bot.",
                ephemeral=True)

            return

        for tag in valid_tags:
            if tag in player_links.get(str(user.id), []):
                await ctx.send(f"{get_app_emoji('error')} `{tag}` is already linked to this user.", ephemeral=True)

                continue

            if tag in player_links_reversed:
                await ctx.send(f"{get_app_emoji('error')} `{tag}` is already linked to another user.", ephemeral=True)

                continue

            player_links.setdefault(str(user.id), []).append(tag)
            await ctx.send(f"{get_app_emoji('success')} `{tag}` is successfully linked.", ephemeral=True)

        with open("data/member_tags.json", "w") as file:
            json.dump(player_links, file, indent=4)


    @ipy.message_context_menu(name="Link Accounts")
    @has_roles("RECRUITMENT_ROLE", "SERVER_DEVELOPMENT_ROLE", "LEADER_ROLE")
    async def Link_Accounts(self, ctx: ipy.ContextMenuContext):
        await ctx.defer(ephemeral=True)

        # FIX: Use ctx.guild_id instead of MAIN_GUILD_ID
        user = await self.bot.fetch_member(ctx.target.author.id, ctx.guild_id, force=True)

        player_links = json.load(open("data/member_tags.json", "r"))
        player_links_reversed = reverse_dict(player_links)

        valid_tags = await extract_tags(self.bot.coc, ctx.target.content, context=ctx)

        if not valid_tags:
            await ctx.send(f"{get_app_emoji('error')} No valid player tags found.", ephemeral=True)

            return

        if isinstance(user, str):
            await ctx.send(
                f"{get_app_emoji('error')} Cannot get this user object. The user does not share any server with the bot.",
                ephemeral=True)

            return

        for tag in valid_tags:
            if tag in player_links.get(str(user.id), []):
                await ctx.send(f"{get_app_emoji('error')} `{tag}` is already linked to this user.", ephemeral=True)

                continue

            if tag in player_links_reversed:
                await ctx.send(f"{get_app_emoji('error')} `{tag}` is already linked to another user.", ephemeral=True)

                continue

            player_links.setdefault(str(user.id), []).append(tag)
            await ctx.send(f"{get_app_emoji('success')} `{tag}` is successfully linked.", ephemeral=True)

        with open("data/member_tags.json", "w") as file:
            json.dump(player_links, file, indent=4)


    @player_base.subcommand(sub_cmd_name="unlink", sub_cmd_description="Unlink Clash of Clans accounts to a user")
    @has_roles("RECRUITMENT_ROLE", "SERVER_DEVELOPMENT_ROLE", "LEADER_ROLE")
    @ipy.slash_option(
        name="user",
        description="Choose a user from this server",
        opt_type=ipy.OptionType.USER,
        required=True
    )
    @ipy.slash_option(
        name="player_tag",
        description="Clash of Clans player tag",
        opt_type=ipy.OptionType.STRING,
        required=True,
        autocomplete=True
    )
    @ipy.slash_option(
        name="user_id",
        description="Type the user id, which will override the user selection.",
        opt_type=ipy.OptionType.STRING,
    )
    async def player_unlink(self, ctx: ipy.SlashContext, user: ipy.Member, player_tag: str, user_id: str = None):
        await ctx.defer(ephemeral=True)

        player_links = json.load(open("data/member_tags.json", "r"))

        player = None
        try:
            player = await fetch_player(self.bot.coc, player_tag)
        except coc.errors.NotFound:
            if player_tag != "all":
                raise

        if not user_id:
            if isinstance(user, str):
                await ctx.send(f"{get_app_emoji('error')} Cannot get this user object, please try again using "
                            f"the option `user_id`.", ephemeral=True)
                return

            user_id = str(user.id)

        tags = player_links[str(user_id)] if player_tag == "all" else [player.tag]
        for tag in tags:

            if tag not in player_links.get(str(user.id), []):
                await ctx.send(f"{get_app_emoji('error')} The account `{tag}` is not linked to the user.", ephemeral=True)

                continue

            player_links[str(user_id)].remove(tag)
            await ctx.send(f"{get_app_emoji('success')} `{tag}` is successfully removed.", ephemeral=True)

        with open("data/member_tags.json", "w") as file:
            json.dump(player_links, file, indent=4)


    @player_unlink.autocomplete(option_name="player_tag")
    async def player_tag_autocomplete(self, ctx: ipy.AutocompleteContext):
        if "user" not in ctx.kwargs and "user_id" not in ctx.kwargs:
            tag_choice = [{"name": "Please choose a user first", "value": "None"}]
            await ctx.send(tag_choice)

            return

        user_id = ctx.kwargs["user_id"] if "user_id" in ctx.kwargs else ctx.kwargs["user"]

        player_links = json.load(open("data/member_tags.json", "r"))

        if not player_links.get(user_id, []):
            tag_choice = [{"name": "No accounts linked to this player", "value": "None"}]
            await ctx.send(tag_choice)

            return

        tag_choices = []
        for tag in copy.deepcopy(player_links[user_id]):
            try:
                player = await fetch_player(self.bot.coc, tag)
            except coc.errors.NotFound:
                player_links[ctx.kwargs["user"]].remove(tag)
                continue

            name = f"[TH{player.town_hall}] {player.name} ({player.tag})"
            tag_choices.append({"name": name, "value": tag})

        tag_choices.append({"name": "Unlink all accounts", "value": "all"})

        await ctx.send(tag_choices)

        with open("data/member_tags.json", "w") as file:
            json.dump(player_links, file, indent=4)


    @ipy.message_context_menu(name="Unlink Accounts")
    @has_roles("RECRUITMENT_ROLE", "SERVER_DEVELOPMENT_ROLE", "LEADER_ROLE")
    async def Unlink_Accounts(self, ctx: ipy.ContextMenuContext):
        await ctx.defer(ephemeral=True)

        # FIX: Use ctx.guild_id instead of MAIN_GUILD_ID
        user = await self.bot.fetch_member(ctx.target.author.id, ctx.guild_id, force=True)

        player_links = json.load(open("data/member_tags.json", "r"))

        tags = await extract_tags(self.bot.coc, ctx.target.content, context=ctx)

        if not tags:
            await ctx.send(f"{get_app_emoji('error')} Please provide at least one valid player tag.", ephemeral=True)

            return

        for tag in tags:
            if tag not in player_links.get(str(user.id), []):
                await ctx.send(f"{get_app_emoji('error')} `{tag}` is not linked to this user.", ephemeral=True)

                continue

            player_links[str(user.id)].remove(tag)
            await ctx.send(f"{get_app_emoji('success')} `{tag}` is successfully removed.", ephemeral=True)

        with open("data/member_tags.json", "w") as file:
            json.dump(player_links, file, indent=4)


    @player_base.subcommand(sub_cmd_name="verify", sub_cmd_description="Set roles and edit nickname of a user")
    @has_roles("RECRUITMENT_ROLE", "SERVER_DEVELOPMENT_ROLE", "LEADER_ROLE")
    @ipy.cooldown(bucket=ipy.Buckets.USER, rate=1, interval=5)
    @ipy.slash_option(
        name="user",
        description="Choose a user from this server",
        opt_type=ipy.OptionType.USER,
        required=True
    )
    @ipy.slash_option(
        name="player_tags",
        description="Separate the tags with a comma",
        opt_type=ipy.OptionType.STRING,
    )
    @ipy.slash_option(
        name="player_nickname",
        description="Choose the nickname of the player",
        opt_type=ipy.OptionType.STRING,
        autocomplete=True
    )
    @ipy.slash_option(
        name="finish_interview",
        description="Interview process finished?",
        opt_type=ipy.OptionType.BOOLEAN,
    )
    async def player_verify(self, ctx: ipy.SlashContext, user: ipy.Member, player_tags: str = None, player_nickname: str = None,
                            finish_interview: bool = False):
        await ctx.defer(ephemeral=True)

        player_links = json.load(open("data/member_tags.json", "r"))
        player_links_reversed = reverse_dict(player_links)

        try:
            member = await self.bot.fetch_member(user.id, ctx.guild_id, force=True)
        except ipy.errors.NotFound:
            await ctx.send(f"{get_app_emoji('error')} User is not in the server, cannot verify.")

            return

        if not member:
            await ctx.send(f"{get_app_emoji('error')} User is not in the server, cannot verify.")

            return

        clans_config: dict[str, AllianceClanData] = json.load(open("data/clans_config.json", "r"))
        member_roles = [int(role.id) for role in member.roles]
        clan_roles = set([clans_config[key]["role"] for key in clans_config.keys()])

        if not player_tags:
            if not player_links.get(str(member.id)):
                await ctx.send(f"{get_app_emoji('error')} No account linked to the player, must provide player tag.")

                return

            corrected_tags = player_links[str(member.id)]
        else:
            corrected_tags = await extract_tags(self.bot.coc, player_tags, context=ctx)

        if not corrected_tags:
            return

        valid_tags = []
        valid_roles = []
        joined_clans = []
        player_townhalls = []
        
        config: sc.GuildConfig = sc.get_config(ctx.guild.id)

        for player_tag in corrected_tags:
            player = await fetch_player(self.bot.coc, player_tag, update=True)
            
            th_role = config.TH_ROLE(player.town_hall)
            if th_role:
                player_townhalls.append(th_role)

            if player_tag not in player_links_reversed:
                player_links.setdefault(str(member.id), []).append(player.tag)

            if not player.clan:
                await ctx.send(f"{get_app_emoji('error')} `{player.name} ({player.tag})` is not in any clan!",
                            ephemeral=True, delete_after=4)

                continue

            if player.clan.tag not in clans_config.keys():
                await ctx.send(f"{get_app_emoji('error')} `{player.name} ({player.tag})` is not in any alliance clans!",
                            ephemeral=True, delete_after=4)

                continue

            joined_clans.append(player.clan.tag)
            valid_tags.append(player.tag)
            valid_roles.append(clans_config[player.clan.tag]["role"])

        with open("data/member_tags.json", "w") as file:
            json.dump(player_links, file, indent=4)
        
        valid_roles += player_townhalls
        
        invalid_roles = list(set(member_roles).intersection(clan_roles) - set(valid_roles))


        if valid_tags:
            player = await fetch_player(self.bot.coc, valid_tags[0], update=True)
            clan_tag = player.clan.tag

            if clans_config[clan_tag]['type'] == "FWA":
                # Dynamic FWA Member Role
                if config.FWA_MEMBER_ROLE:
                    valid_roles.append(config.FWA_MEMBER_ROLE)
            
            # Dynamic Family Role
            if config.FAMILY_ROLE:
                valid_roles.append(config.FAMILY_ROLE)

            new_name = f"{player.name} | {player.clan.name}"[:32]

            await ctx.send(
                f"{get_app_emoji('success')} The player's account(s) that are part of *All For One* is/are successfully verified, "
                f"and all roles are set!",
                ephemeral=True)
        else:
            # Dynamic Visitor Role
            if config.VISITOR_ROLE:
                valid_roles.append(config.VISITOR_ROLE)
            
            # Remove Family/FWA roles if they become visitor
            if config.FAMILY_ROLE:
                invalid_roles.append(config.FAMILY_ROLE)
            if config.FWA_MEMBER_ROLE:
                invalid_roles.append(config.FWA_MEMBER_ROLE)

            player = await fetch_player(self.bot.coc, corrected_tags[0], update=True)
            new_name = f"{player.name} | Visitor"[:32]

            await ctx.send(f"{get_app_emoji('error')} The player's account(s) is/are not part of *All For One*!", ephemeral=True)    

        new_name = player_nickname if player_nickname else new_name

        await member.add_roles(valid_roles, reason=f"{ctx.author} {ctx.author.id} used /player verify")

        try:
            await member.remove_roles(invalid_roles, reason=f"{ctx.author} {ctx.author.id} used /player verify")
            if ctx.author.top_role.position > member.top_role.position:
                await member.edit(nickname=new_name, reason=f"{ctx.author} {ctx.author.id} used /player verify")
        except (ipy.errors.HTTPException, ipy.errors.Forbidden):
            pass

        if not finish_interview:
            return
        
        # Check if channel is an interview channel using dynamic categories
        if int(ctx.channel.parent_id) not in [config.CLAN_TICKETS_CATEGORY, config.AFTER_CWL_CATEGORY, config.FWA_TICKETS_CATEGORY]:
            await ctx.send(f"{get_app_emoji('error')} The finishing interview function can only be used in an interview channel.")

            return

        if not joined_clans:
            return

        webhook_name = ctx.author.nick if ctx.author.nick else ctx.author.user.username

        joined_clans = list(dict.fromkeys(joined_clans))
        for clan_tag in joined_clans:
            greeting_options = ["Welcome to ", "Thanks for joining ", "Glad to see you in ", "Glad that you chose ",
                                "Is an honor that you chose ", "Hope you enjoy your stay in "]
            welcome_message = f"{member.mention} {random.choice(greeting_options)}{clans_config[clan_tag]['name']}!"
            chat_instructions = [
                "In this channel, you can chat with your clan mates and ask questions.",
                "Feel free to chat here and ask questions.",
                "This is the chat channel for the clan, you can chat and ask questions here.",
                "If you have questions, just ask here!"
            ]

            channel = await self.bot.fetch_channel(clans_config[clan_tag]['chat'], force=True)

            if not channel:
                await ctx.send(
                    f"{get_app_emoji('error')} The chat channel of `{clans_config[clan_tag]['name']}` is set incorrectly! "
                    f"Please report this issue to **server developers**!", ephemeral=True)

                return

            for webhook in await channel.fetch_webhooks():
                if webhook.name == "Fake User" and int(webhook.user_id) == int(self.bot.user.id):
                    break
            else:
                webhook = await channel.create_webhook(name="Fake User")

            await webhook.send(
                content=f"{welcome_message} {random.choice(chat_instructions)}",
                username=webhook_name,
                avatar_url=ctx.author.avatar.url
            )

            if clans_config[clan_tag]["announcement"]:
                announcement_channel = f"<#{clans_config[clan_tag]['announcement']}>"
                channel_instructions = [
                    f"Also make sure to follow {announcement_channel}!",
                    f"Don't forget to read {announcement_channel} regularly!",
                    f"Is important that you check {announcement_channel}."
                ]

                await webhook.send(
                    content=f"{random.choice(channel_instructions)}",
                    username=webhook_name,
                    avatar_url=ctx.author.avatar.url
                )

        for interview_webhook in await ctx.channel.fetch_webhooks():
            if interview_webhook.name == "Fake User":
                break
        else:
            interview_webhook = await ctx.channel.create_webhook(name="Fake User")

        finishing_messages = [
            "Welcome to the family, your roles are set and hope you enjoy your time here. Do you have any further questions?",
            "Welcome to the alliance, the interview is finished, have any further questions?",
            "Thank you for being part of the alliance, if no further questions, the ticket will be closed!",
            "Thank you for taking your time to apply, we hope that you will feel comfortable in your new home!"
        ]

        await interview_webhook.send(
            content=f"{random.choice(finishing_messages)}",
            username=webhook_name,
            avatar_url=ctx.author.avatar.url
        )


    @ipy.message_context_menu(name="Verify Accounts")
    @has_roles("RECRUITMENT_ROLE", "SERVER_DEVELOPMENT_ROLE", "LEADER_ROLE")
    async def Verify_Accounts(self, ctx: ipy.ContextMenuContext):
        await ctx.defer(ephemeral=True)

        player_links = json.load(open("data/member_tags.json", "r"))
        player_links_reversed = reverse_dict(player_links)

        try:
            # FIX: Use ctx.guild_id instead of MAIN_GUILD_ID
            member = await self.bot.fetch_member(ctx.target.author.id, ctx.guild_id, force=True)
        except ipy.errors.NotFound:
            await ctx.send(f"{get_app_emoji('error')} User is not in the server, cannot verify.", ephemeral=True)
            return

        clans_config: dict[str, AllianceClanData] = json.load(open("data/clans_config.json", "r"))
        member_roles = [int(role.id) for role in member.roles]
        clan_roles = set([clans_config[key]["role"] for key in clans_config.keys()])

        corrected_tags = await extract_tags(self.bot.coc, ctx.target.content, context=ctx)
        if not corrected_tags:
            if not player_links.get(str(member.id)):
                await ctx.send(f"{get_app_emoji('error')} No account linked to the player, must provide player tag.", ephemeral=True)

                return

            corrected_tags = player_links[str(member.id)]

        if not corrected_tags:
            return

        valid_tags = []
        valid_roles = []
        player_townhalls = []
        
        config: sc.GuildConfig = sc.get_config(ctx.guild.id)

        for player_tag in corrected_tags:
            player = await fetch_player(self.bot.coc, player_tag, update=True)
            
            th_role = config.TH_ROLE(player.town_hall)
            if th_role:
                player_townhalls.append(th_role)

            if player_tag not in player_links_reversed:
                player_links.setdefault(str(member.id), []).append(player.tag)

            if not player.clan:
                await ctx.send(f"{get_app_emoji('error')} `{player.name} ({player.tag})` is not in any clan!",
                            ephemeral=True, delete_after=4)

                continue

            if player.clan.tag not in clans_config.keys():
                await ctx.send(f"{get_app_emoji('error')} `{player.name} ({player.tag})` is not in any alliance clans!",
                            ephemeral=True, delete_after=4)

                continue

            valid_tags.append(player.tag)
            valid_roles.append(clans_config[player.clan.tag]["role"])

        with open("data/member_tags.json", "w") as file:
            json.dump(player_links, file, indent=4)
        
        valid_roles += player_townhalls
        
        invalid_roles = list(set(member_roles).intersection(clan_roles) - set(valid_roles))

        if valid_tags:
            if config.FAMILY_ROLE:
                valid_roles.append(config.FAMILY_ROLE)

            player = await fetch_player(self.bot.coc, valid_tags[0], update=True)
            new_name = f"{player.name} | {player.clan}"[:32]

            await ctx.send(
                f"{get_app_emoji('success')} The player's account(s) that are part of *All For One* is/are successfully verified, "
                f"and all roles are set!",
                ephemeral=True)
        else:
            if config.VISITOR_ROLE:
                valid_roles.append(config.VISITOR_ROLE)
            if config.FAMILY_ROLE:
                invalid_roles.append(config.FAMILY_ROLE)

            player = await fetch_player(self.bot.coc, corrected_tags[0], update=True)
            new_name = f"{player.name} | Visitor"[:32]

            await ctx.send(f"{get_app_emoji('error')} The player's account(s) is/are not part of *All For One*!")

        await member.add_roles(valid_roles, reason=f"{ctx.author} {ctx.author.id} used /player verify")

        try:
            await member.remove_roles(invalid_roles, reason=f"{ctx.author} {ctx.author.id} used /player verify")
            if ctx.author.top_role.position > member.top_role.position:
                await member.edit(nickname=new_name, reason=f"{ctx.author} {ctx.author.id} used /player verify")
        except (ipy.errors.HTTPException, ipy.errors.Forbidden):
            pass


    @ipy.global_autocomplete(option_name="player_nickname")
    async def player_nickname_autocomplete(self, ctx: ipy.AutocompleteContext):
        if "user" not in ctx.kwargs:
            name_choice = [{"name": "Please choose a user first", "value": "None"}]
            await ctx.send(name_choice)

            return

        member = await ctx.guild.fetch_member(ctx.kwargs["user"])

        player_name = member.nickname if member.nickname else member.username
        player_links = json.load(open("data/member_tags.json", "r"))
        clans_config: dict[str, AllianceClanData] = json.load(open("data/clans_config.json", "r"))

        if "player_tags" not in ctx.kwargs:
            if not player_links.get(str(member.id)):
                name_choice = [{"name": "Please choose a user first", "value": player_name}]
                await ctx.send(name_choice)

                return

            corrected_tags = player_links[str(member.id)]

        else:
            corrected_tags = await extract_tags(self.bot.coc, ctx.kwargs["player_tags"])

        name_choices = [{"name": player_name, "value": player_name}]
        for tag in corrected_tags:
            player = await fetch_player(self.bot.coc, tag)
            clan_tag = player.clan.tag if player.clan else None

            if clan_tag in clans_config:
                nickname = f"{player.name} | {clans_config[clan_tag]['name']}"
            else:
                nickname = f"{player.name} | Visitor"

            name_choices.append({"name": nickname, "value": nickname})

        await ctx.send(name_choices)

def setup(bot):
    PlayerCmds(bot)