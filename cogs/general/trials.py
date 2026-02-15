import re
import json
import secrets
from core.emojis_manager import *
from datetime import datetime, timedelta, timezone

from core.utils import *
from core.models import *
from core import server_setup as sc
import interactions as ipy

class TrialAssistant(ipy.Extension):
    @ipy.component_callback(re.compile(r"^start_trial\|\w+$"))
    async def trial_start_button(self, ctx: ipy.ComponentContext):
        config: sc.GuildConfig = sc.get_config(ctx.guild.id)
        # Dynamic check
        if not any(int(role.id) in [config.MODERATOR_ROLE, config.SERVER_DEVELOPMENT_ROLE] for role in
                   ctx.author.roles):
            await ctx.send(f"{get_app_emoji('error')} You do not have the permission to interact with this component!",
                           ephemeral=True)

            return

        modal = ipy.Modal(
            ipy.ParagraphText(
                label="How many days will the trial be?",
                placeholder="Enter a number (3-14)",
                max_length=2,
                custom_id="days"
            ),
            title="Trial Duration Form",
            custom_id=f"modal_{ctx.custom_id}",
        )
        await ctx.send_modal(modal)

    @ipy.modal_callback(re.compile(r"^modal_start_trial\|\w+$"))
    async def trial_start_modal(self, ctx: ipy.ModalContext, **responses):
        await ctx.defer(ephemeral=True)

        _, trial_type = ctx.custom_id.split("|")
        trial_type = trial_type.replace("0", " ")
        days = int(responses["days"])

        if days < 3 or days > 14:
            await ctx.send(f"{get_app_emoji('error')} The number of days must be between 3 and 14.", ephemeral=True)

            return

        end_date = datetime.now(timezone.utc) + timedelta(days=days)
        end = f"<t:{int(end_date.timestamp())}:D>"

        for overwrite in ctx.channel.permission_overwrites:
            if overwrite.type == ipy.OverwriteType.MEMBER:
                member = await ctx.guild.fetch_member(overwrite.id)

                if int(member.id) == extract_integer(ctx.channel.topic):
                    break

                if extract_alphabets(member.username) == ctx.channel.name.split("┃")[1]:
                    break
        else:
            await ctx.send(f"{get_app_emoji('error')} Unable to get the applicant of this channel.", ephemeral=True)

            return

        trial_events = json.load(open("data/trial_events.json", "r"))
        trial_events[f"{ctx.channel.id}|{member.id}"] = {
            "date": [end_date.year, end_date.month, end_date.day, end_date.hour, end_date.minute],
            "action": "end",
            "type": trial_type
        }
        with open("data/trial_events.json", "w") as file:
            json.dump(trial_events, file, indent=4)

        config: sc.GuildConfig = sc.get_config(ctx.guild.id)
        parent_id = config.STAFF_TRIALS_CATEGORY 

        embed = ipy.Embed(
            title="**Trial Has Started**",
            description=f"{member.mention}'s trial for {trial_type.lower()} has started! It will end on {end}, "
                        f"every staff in the management team wish the best luck for the applicant!",
            footer=ipy.EmbedFooter(
                text=f"Start Time",
            ),
            timestamp=ipy.Timestamp.utcnow(),
            color=COLOR
        )
        await (await ctx.channel.send(member.mention, embed=embed)).pin()

        await ctx.channel.edit(parent_id=parent_id, topic=f"Applicant ID: {member.id}\nEnds on {end}")

        await ctx.message.edit(components=ipy.utils.misc_utils.disable_components(*ctx.message.components))

        await ctx.send(f"{get_app_emoji('success')} Trial started!", ephemeral=True)

    @ipy.component_callback(re.compile(r"^delay_trial\|\w+$"))
    async def trial_delay_button(self, ctx: ipy.ComponentContext):
        config: sc.GuildConfig = sc.get_config(ctx.guild.id)
        if not any(int(role.id) in [config.MODERATOR_ROLE, config.SERVER_DEVELOPMENT_ROLE] for role in
                   ctx.author.roles):
            await ctx.send(f"{get_app_emoji('error')} You do not have the permission to interact with this component!",
                           ephemeral=True)

            return

        modal = ipy.Modal(
            ipy.ParagraphText(
                label="How many days will the trial be delayed?",
                placeholder="Enter a number (1-30)",
                max_length=2,
                custom_id="days"
            ),
            ipy.ParagraphText(
                label="How many days will the trial be?",
                placeholder="Enter a number (3-14)",
                max_length=2,
                custom_id="trial_duration"
            ),
            title="Trial Delay Duration Form",
            custom_id=f"modal_{ctx.custom_id}",
        )
        await ctx.send_modal(modal)

    @ipy.modal_callback(re.compile(r"^modal_delay_trial\|\w+$"))
    async def trial_delay_modal(self, ctx: ipy.ModalContext, **responses):
        await ctx.defer(ephemeral=True)

        _, trial_type = ctx.custom_id.split("|")
        trial_type = trial_type.replace("0", " ")
        days = int(responses["days"])

        if days < 1 or days > 30:
            await ctx.send(f"{get_app_emoji('error')} The number of days must be between 1 and 30.", ephemeral=True)

            return

        start_date = datetime.now(timezone.utc) + timedelta(days=days)
        start = f"<t:{int(start_date.timestamp())}:D>"

        for overwrite in ctx.channel.permission_overwrites:
            if overwrite.type == ipy.OverwriteType.MEMBER:
                member = await ctx.guild.fetch_member(overwrite.id)

                if int(member.id) == extract_integer(ctx.channel.topic):
                    break

                if extract_alphabets(member.username) == ctx.channel.name.split("┃")[1]:
                    break
        else:
            await ctx.send(f"{get_app_emoji('error')} Unable to get the applicant of this channel.", ephemeral=True)

            return

        trial_events = json.load(open("data/trial_events.json", "r"))
        trial_events[f"{ctx.channel.id}|{member.id}"] = {
            "date": [start_date.year, start_date.month, start_date.day, start_date.hour, start_date.minute],
            "action": "start",
            "type": trial_type,
            "days": int(responses["trial_duration"])
        }
        with open("data/trial_events.json", "w") as file:
            json.dump(trial_events, file, indent=4)

        embed = ipy.Embed(
            title="**Trial Has Been Delayed**",
            description=f"{member.mention} Multiple trials are already in process, therefore, your trial have been "
                        f"delayed for {days} days! The trial will start on {start}. We are sorry for the delay "
                        f"and inconvenience!",
            footer=ipy.EmbedFooter(
                text=f"Delayed Time",
            ),
            timestamp=ipy.Timestamp.utcnow(),
            color=COLOR
        )
        config: sc.GuildConfig = sc.get_config(ctx.guild.id)
        parent_id = config.STAFF_TRIALS_CATEGORY

        await (await ctx.channel.send(member.mention, embed=embed)).pin()

        await ctx.channel.edit(parent_id=parent_id, topic=f"Applicant ID: {member.id}\nStarts on {start}")

        await ctx.message.edit(components=ipy.utils.misc_utils.disable_components(*ctx.message.components))

        await ctx.send(f"{get_app_emoji('success')} Trial has been delayed!", ephemeral=True)

    @ipy.component_callback(re.compile(r"^deny_trial\|\w+$"))
    async def trial_deny_button(self, ctx: ipy.ComponentContext):
        config: sc.GuildConfig = sc.get_config(ctx.guild.id)
        if not any(int(role.id) in [config.MODERATOR_ROLE, config.SERVER_DEVELOPMENT_ROLE] for role in
                   ctx.author.roles):
            await ctx.send(f"{get_app_emoji('error')} You do not have the permission to interact with this component!",
                           ephemeral=True)
            return

        modal = ipy.Modal(
            ipy.ParagraphText(
                label="What is the reason of denying this trial?",
                placeholder="Explain the reason clearly so the applicant does not feel unfair",
                max_length=300,
                custom_id="reason"
            ),
            title="Trial Deny Form",
            custom_id=f"modal_{ctx.custom_id}",
        )
        await ctx.send_modal(modal)

    @ipy.modal_callback(re.compile(r"^modal_deny_trial\|\w+$"))
    async def trial_deny_modal(self, ctx: ipy.ModalContext, **responses):
        await ctx.defer(ephemeral=True)

        for overwrite in ctx.channel.permission_overwrites:
            if overwrite.type == ipy.OverwriteType.MEMBER:
                member = await ctx.guild.fetch_member(overwrite.id)

                if int(member.id) == extract_integer(ctx.channel.topic):
                    break

                if extract_alphabets(member.username) == ctx.channel.name.split("┃")[1]:
                    break
        else:
            await ctx.send(f"{get_app_emoji('error')} Unable to get the applicant of this channel.", ephemeral=True)

            return

        embed = ipy.Embed(
            title="**Trial Has Been Denied**",
            description=f"{get_app_emoji('error')} {member.mention} After evaluating your responses, we are sorry to inform you that the management team "
                        f"has decided that you are not a fit to the alliance. However, feel free to reapply later once you fit our "
                        f"expectations!\n\n"
                        f"**Reason**\n```{responses['reason']}```",
            footer=ipy.EmbedFooter(
                text=f"Denied Time",
            ),
            timestamp=ipy.Timestamp.utcnow(),
            color=COLOR
        )
        await ctx.channel.send(member.mention, embed=embed)

        await ctx.message.edit(components=ipy.utils.misc_utils.disable_components(*ctx.message.components))

        await ctx.send(f"{get_app_emoji('success')} Trial has been denied!", ephemeral=True)

    @ipy.component_callback(re.compile(r"^vote_start_button\|\w+$"))
    async def voting_start(self, ctx: ipy.ComponentContext):
        await ctx.defer(ephemeral=True)
        config: sc.GuildConfig = sc.get_config(ctx.guild.id)

        if not any(int(role.id) in [config.MODERATOR_ROLE, config.SERVER_DEVELOPMENT_ROLE] for role in
                   ctx.author.roles):
            await ctx.send(f"{get_app_emoji('error')} You do not have the permission to interact with this component!",
                           ephemeral=True)

            return

        _, trial_type = ctx.custom_id.split("|")
        trial_type = trial_type.replace("0", " ")

        trial_config = json.load(open("data/trial_config.json", "r"))

        thread = await ctx.channel.create_private_thread(name="Trial Voting", invitable=False)
        mentions = f"<@&{config.SERVER_DEVELOPMENT_ROLE}>"
        if trial_type not in ["Server Developer", "Moderator"]:
            mentions += f" <@&{config.MODERATOR_ROLE}>"

        for overwrite in ctx.channel.permission_overwrites:
            if overwrite.type == ipy.OverwriteType.MEMBER:
                member = await ctx.guild.fetch_member(overwrite.id)

                if int(member.id) == extract_integer(ctx.channel.topic):
                    break

                if extract_alphabets(member.username) == ctx.channel.name.split("┃")[1]:
                    break
        else:
            await ctx.send(f"{get_app_emoji('error')} Unable to get the applicant of this channel.", ephemeral=True)

            return

        if trial_type in trial_config:
            msg_content = f"Is {member.mention} capable of taking on the tasks and the responsibilities of a " \
                          f"**{trial_type.lower()}**? Vote using the buttons below based on their performance " \
                          f"during the trial!"

        elif trial_type == "Clan Alliance":
            clans_config: dict[str, AllianceClanData] = json.load(open("data/clans_config.json", "r"))
            for value in clans_config.values():
                if value["leader"] == int(member.id):
                    clan_role = await ctx.guild.fetch_role(value["role"])
                    member_count = len(clan_role.members)

                    break
            else:
                member_count = "Unknown"

            msg_content = f"Will {member.mention}'s clan be beneficial to the alliance as a whole? Have they made effort " \
                          f"to contribute and is the leader active in tickets? In total, they managed to get `{member_count}` members " \
                          f"in the server! Vote using the buttons below based on their performance " \
                          f"during the trial!"

        else:
            msg_content = f"Is a **{trial_type.lower()}** partnership worthwhile with {member.mention}? " \
                          f"Vote using the buttons below based on their performance " \
                          f"during the trial!"

        member_name = member.nickname if member.nickname else member.username
        embed = ipy.Embed(
            title=f"**{member_name}**'s Trial Voting (0 Votes)",
            description=msg_content,
            fields=[
                ipy.EmbedField(
                    name="Upvote Percentage (%)",
                    value=progress_bar(0),
                    inline=False
                ),
                ipy.EmbedField(
                    name="Neutral Percentage (%)",
                    value=progress_bar(0),
                    inline=False
                ),
                ipy.EmbedField(
                    name="Downvote Percentage (%)",
                    value=progress_bar(0),
                    inline=False
                )
            ],
            footer=ipy.EmbedFooter(
                text="Please try to vote unbiased!",
            ),
            color=COLOR
        )

        poll_token = secrets.token_hex(8)

        upvote_button = ipy.Button(
            style=ipy.ButtonStyle.SUCCESS,
            custom_id=f"upvote|button|{poll_token}",
            emoji="️⬆️"
        )

        neutral_button = ipy.Button(
            style=ipy.ButtonStyle.SECONDARY,
            custom_id=f"neutral|button|{poll_token}",
            emoji="️➖"
        )

        downvote_button = ipy.Button(
            style=ipy.ButtonStyle.DANGER,
            custom_id=f"downvote|button|{poll_token}",
            emoji="⬇️"
        )

        details_button = ipy.Button(
            style=ipy.ButtonStyle.SECONDARY,
            label="View Votes",
            custom_id=f"voting_details|{poll_token}",
            emoji="ℹ️"
        )

        actionrow = ipy.ActionRow(upvote_button, neutral_button, downvote_button, details_button)

        msg = await thread.send(mentions, embed=embed, components=[actionrow])
        await msg.pin()

        try:
            await thread.remove_member(member)
        except (ipy.errors.HTTPException, ipy.errors.Forbidden):
            pass

        trial_votes = json.load(open("data/trial_votes.json", "r"))
        trial_votes[poll_token] = {"upvote": [], "neutral": [], "downvote": []}
        with open("data/trial_votes.json", "w") as file:
            json.dump(trial_votes, file, indent=4)

        await ctx.send(f"{get_app_emoji('success')} A poll is created for the voting of the trial.", ephemeral=True)

    @ipy.component_callback(re.compile(r"^(((down|up|)vote)|neutral)\|button\|\w+$"))
    async def voting_buttons(self, ctx: ipy.ComponentContext):
        config: sc.GuildConfig = sc.get_config(ctx.guild.id)
        member_roles = [int(role.id) for role in ctx.author.roles]
        
        # Dynamic role check
        allowed_roles = [config.ADMINISTRATION_ROLE, config.SERVER_DEVELOPMENT_ROLE, config.MODERATOR_ROLE]
        
        if not any([role_id in allowed_roles for role_id in member_roles]):
            await ctx.send(f"{get_app_emoji('error')} Only administrators and management staffs can use this button.",
                           ephemeral=True)

            return

        vote_type, _, poll_token = ctx.custom_id.split("|")
        trial_votes = json.load(open("data/trial_votes.json", "r"))
        data = trial_votes[poll_token]

        if int(ctx.author.id) in data[vote_type]:
            if vote_type == "neutral":
                await ctx.send(f"{get_app_emoji('error')} You have already voted for neutral!", ephemeral=True)
            else:
                await ctx.send(f"{get_app_emoji('error')} You have already {vote_type}d!", ephemeral=True)

            return

        total_votes = 0
        data[vote_type].append(int(ctx.author.id))
        for key in data.keys():
            if key != vote_type and int(ctx.author.id) in data[key]:
                data[key].remove(int(ctx.author.id))

            total_votes += len(data[key])

        with open("data/trial_votes.json", "w") as file:
            json.dump(trial_votes, file, indent=4)

        upvote_percentage = len(data["upvote"]) / total_votes
        neutral_percentage = len(data["neutral"]) / total_votes
        downvote_percentage = len(data["downvote"]) / total_votes

        new_title = re.sub(r'\((\d+) Votes\)', f'({total_votes} Votes)', ctx.message.embeds[0].title)

        ctx.message.embeds[0].title = new_title
        ctx.message.embeds[0].fields[0].value = progress_bar(upvote_percentage)
        ctx.message.embeds[0].fields[1].value = progress_bar(neutral_percentage)
        ctx.message.embeds[0].fields[2].value = progress_bar(downvote_percentage)

        await ctx.message.edit(embed=ctx.message.embeds[0])
        await ctx.send(f"{get_app_emoji('success')} Your vote is recorded!", ephemeral=True)

    @ipy.component_callback(re.compile(r"^voting_details\|\w+$"))
    async def voting_details(self, ctx: ipy.ComponentContext):
        config: sc.GuildConfig = sc.get_config(ctx.guild.id)
        member_roles = [int(role.id) for role in ctx.author.roles]
        
        if config.ADMINISTRATION_ROLE not in member_roles:
            await ctx.send(f"{get_app_emoji('error')} Only administrators can use this button.", ephemeral=True)

            return

        _, poll_token = ctx.custom_id.split("|")
        trial_votes = json.load(open("data/trial_votes.json", "r"))
        data = trial_votes[poll_token]

        upvoted_users = ""
        for user_id in data["upvote"]:
            upvoted_users += f"<@{user_id}>\n"

        if not upvoted_users:
            upvoted_users = "No upvotes..."

        downvoted_users = ""
        for user_id in data["downvote"]:
            downvoted_users += f"<@{user_id}>\n"

        if not downvoted_users:
            downvoted_users = "No downvotes..."

        neutral_users = ""
        for user_id in data["neutral"]:
            neutral_users += f"<@{user_id}>\n"

        if not neutral_users:
            neutral_users = "No neutrals..."

        embed = ipy.Embed(
            title=f"**Voting Details**",
            fields=[
                ipy.EmbedField(
                    name="⬆️ Upvotes",
                    value=upvoted_users,
                    inline=True
                ),
                ipy.EmbedField(
                    name="➖ Neutrals",
                    value=neutral_users,
                    inline=True
                ),
                ipy.EmbedField(
                    name="⬇️ Downvotes",
                    value=downvoted_users,
                    inline=True
                )
            ],
            footer=ipy.EmbedFooter(
                text=f"Requested by {ctx.author.user.username}",
                icon_url=ctx.author.avatar.url
            ),
            color=COLOR
        )

        await ctx.send(embed=embed, ephemeral=True)