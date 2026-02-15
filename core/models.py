"""
Data Models & Type Definitions.

This module defines the core data structures and custom exceptions used throughout the
application. It leverages Python's `typing.TypedDict` to enforce schema validation
for the JSON-based data stores (e.g., clan configurations, application packages).

Key Components:
1.  **Data Schemas:** `AllianceClanData` and `ApplicationPackage` define the expected
    structure for the bot's configuration files, ensuring type safety when loading/saving JSON.
2.  **Context Wrappers:** `PermanentContext` provides a persistent context object for
    handling long-running interactions or timeout recovery.
3.  **Custom Exceptions:** specialized error classes (`ComponentTimeoutError`, `InvalidTagError`)
    allow the error handling extension to provide specific, user-friendly feedback.

Dependencies:
    - typing (Type hinting)
    - coc (Clash of Clans API wrapper)
    - interactions (Discord interactions)
"""

from typing import TypedDict, NotRequired, Any, Type, Optional
import coc
import interactions as ipy

class ClanCheckData(TypedDict):
    """
    Schema for individual validation checks within a clan's configuration.
    
    Attributes:
        min_value (int): The numeric threshold for the check (e.g., min hero level sum).
        client (coc.Client, optional): The API client instance, injected dynamically during runtime.
    """
    min_value: int
    client: NotRequired[coc.Client]

class AllianceClanData(TypedDict):
    """
    Schema representing the configuration for a single Alliance Clan.
    Matches the structure stored in `data/clans_config.json`.
    """
    leader: int          # Discord ID of the clan leader
    emoji: str           # Name of the custom emoji used for this clan
    msg: str             # Pipe-separated string of key messages shown to applicants
    questions: str       # Pipe-separated string of specific interview questions
    name: str            # In-game name of the clan
    prefix: str          # Short prefix used for ticket channel naming
    requirement: str     # Text description of requirements (e.g., "TH14+")
    role: int            # Discord Role ID for clan members
    gk_role: int         # Discord Role ID for Gatekeepers/Recruiters
    type: str            # Clan classification ("Competitive", "FWA", "CWL")
    recruitment: bool    # Boolean flag indicating if recruitment is open
    chat: int            # Channel ID for the clan's chat
    announcement: int    # Channel ID for the clan's announcements (optional in practice, but typed as int)
    checks: dict[str, ClanCheckData] # Dictionary of enabled validation checks

class ApplicationPackage(TypedDict):
    """
    Schema representing the state of an active application session.
    Matches the structure stored in `data/packages.json`.
    
    This object persists the user's progress through the multi-step application flow.
    """
    account_tags: NotRequired[list[str]]                # List of CoC player tags involved in the application
    acc_clan: NotRequired[dict[str | Any, str | None]]  # Map of Player Tag -> Selected Clan Tag
    acc_images: NotRequired[dict[str | Any, str | None]]# Map of Player Tag -> Proof Image URL (for FWA)
    user: NotRequired[int]                              # Discord ID of the applicant
    continent_name: NotRequired[str | None]             # (Deprecated/Optional) Region info
    message_id: NotRequired[int]                        # ID of the interface message to update
    channel_id: NotRequired[int]                        # ID of the ticket channel

class PermanentContext:
    """
    A custom wrapper for interaction contexts.
    
    This class is designed to simulate or persist a context object when the original
    interaction token might have expired, or when passing context between disparate
    parts of the application (e.g., from a background task to a command handler).
    """
    def __init__(self, message: ipy.Message, custom_id: str, channel: Type[ipy.BaseChannel], guild: ipy.Guild,
                 deferred: bool, author: ipy.Member, kwargs: dict[str, Any]):
        """
        Initialize the PermanentContext.

        Args:
            message (ipy.Message): The message object associated with the interaction.
            custom_id (str): The custom ID of the component that triggered the flow.
            channel (ipy.BaseChannel): The channel where the interaction occurred.
            guild (ipy.Guild): The guild context.
            deferred (bool): Whether the interaction has been deferred.
            author (ipy.Member): The user who initiated the interaction.
            kwargs (dict): Additional arguments passed to the context.
        """
        self.message = message
        self.custom_id = custom_id
        self.channel = channel
        self.guild = guild
        self.deferred = deferred
        self.author = author
        self.kwargs = kwargs

class ComponentTimeoutError(Exception):
    """
    Custom exception raised when a user fails to interact with a component 
    (button/select menu) within the allotted time window.
    
    Caught by: `cogs.general.errors` to disable components or send a timeout message.
    """
    def __init__(self, message: ipy.Message):
        self.message = message

    def __str__(self):
        return f"Components in message (ID: {self.message.id}) has timed out!"

class InvalidTagError(coc.errors.NotFound):
    """
    Custom exception raised when a provided Clash of Clans tag is malformed 
    or does not exist in the API.
    
    Inherits from `coc.errors.NotFound` to align with the library's error hierarchy.
    """
    def __init__(self, tag: str, tag_type: str):
        """
        Args:
            tag (str): The invalid tag string.
            tag_type (str): The type of tag (e.g., "player", "clan").
        """
        self.tag = tag
        self.tag_type = tag_type

    def __str__(self):
        return f"The {self.tag_type} tag ({self.tag}) is invalid!"