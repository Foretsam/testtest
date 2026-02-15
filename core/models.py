from typing import TypedDict, NotRequired, Any, Type, Optional

import coc
import interactions as ipy

class ClanCheckData(TypedDict):
    min_value: int
    client: NotRequired[coc.Client]

class AllianceClanData(TypedDict):
    leader: int
    emoji: str
    msg: str
    questions: str
    name: str
    prefix: str
    requirement: str
    role: int
    gk_role: int
    type: str
    recruitment: bool
    chat: int
    announcement: int
    checks: dict[str, ClanCheckData]


class ApplicationPackage(TypedDict):
    account_tags: NotRequired[list[str]]
    acc_clan: NotRequired[dict[str | Any, str | None]]
    acc_images: NotRequired[dict[str | Any, str | None]]
    user: NotRequired[int]
    continent_name: NotRequired[str | None]
    message_id: NotRequired[int]
    channel_id: NotRequired[int]


class PermanentContext:
    def __init__(self, message: ipy.Message, custom_id: str, channel: Type[ipy.BaseChannel], guild: ipy.Guild,
                 deferred: bool, author: ipy.Member, kwargs: dict[str, Any]):
        self.message = message
        self.custom_id = custom_id
        self.channel = channel
        self.guild = guild
        self.deferred = deferred
        self.author = author
        self.kwargs = kwargs


class ComponentTimeoutError(Exception):
    def __init__(self, message: ipy.Message):
        self.message = message

    def __str__(self):
        return f"Components in message (ID: {self.message.id}) has timed out!"


class InvalidTagError(coc.errors.NotFound):
    def __init__(self, tag: str, tag_type: str):
        self.tag = tag
        self.tag_type = tag_type

    def __str__(self):
        return f"The {self.tag_type} tag ({self.tag}) is invalid!"
