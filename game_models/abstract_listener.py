import asyncio
import datetime
import inspect
from typing import Union, List, Awaitable, Optional, Tuple

import discord
from discord import (Member, Message, User, Guild, Reaction, VoiceState, RawReactionActionEvent, NotFound, Forbidden,
                     HTTPException, Emoji, PartialEmoji)

from constants import BOT
from helpers import TranslationDict
from logger import logger
from models.types import AbstractGuildListener


async def reconstitute_reaction_and_user(payload: RawReactionActionEvent) -> Tuple[Optional[Reaction], Optional[User]]:
    try:
        guild: Guild = BOT.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        channel = guild.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
    except (NotFound, Forbidden, HTTPException, AttributeError) as err:
        logger.debug(f"Impossible to fetch message linked to raw add reaction: {err}")
        return None, None
    for _reaction in message.reactions:
        if isinstance(_reaction.emoji, (Emoji, PartialEmoji)):
            _emoji = payload.emoji
        elif isinstance(_reaction.emoji, str):
            _emoji = payload.emoji.name
        else:
            return None, member  # bad emoji type
        if _reaction.emoji == _emoji:
            reaction = _reaction
            return reaction, member
    return None, member


class AbstractListener(AbstractGuildListener):
    """Base class of listener that can listen to bot events."""
    _default_messages = TranslationDict()

    def __init__(self, **kwargs):
        super().__init__()
        self._name: str = kwargs.pop("name", self.__class__.__name__)
        self._description: str = kwargs.pop("description", "")
        self._messages: TranslationDict = kwargs.pop("messages", self._default_messages)
        self._auto_start: bool = kwargs.pop("auto_start", False)
        self._show_in_listener_manager = kwargs.pop("show_in_listener_manager", True)
        if kwargs:
            logger.warning(f"Invalid arguments for {self.__class__.__name__} listener: {kwargs}")
        self._active: bool = False
        self._listener_manager: Optional['AbstractListenerManager'] = None
        self.__lock_init: asyncio.Lock = asyncio.Lock()

    @property
    def auto_start(self):
        return self._auto_start

    @property
    def active(self):
        return self._active

    @property
    def name(self):
        return self._name

    @property
    def description(self):
        return self._description

    @property
    def show_in_listener_manager(self):
        return self._show_in_listener_manager

    def __repr__(self):
        return f"**{self.__class__.__name__}**\n{self._description}"

    def set_listener_manager(self, manager: 'AbstractListenerManager'):
        self._listener_manager = manager

    def _init(self) -> Union[Awaitable[bool], bool]:  # to be overridden
        return True

    async def start(self) -> bool:
        if self.__lock_init.locked():
            logger.info(f"The mini-game {self.__class__.__name__} is already starting!")
            return False
        async with self.__lock_init:
            if self._active:  # mini-game already started
                logger.debug(f"{self.__class__.__name__} already started!")
                return False
            _res = self._init()
            if inspect.isawaitable(_res):
                _res = await _res
            if not _res:
                return False
            self._active = True
            if self._listener_manager:
                await self._listener_manager.start_listener(self)
            logger.info(f"{self.__class__.__name__} started!")
            return True

    def _close(self) -> Union[Awaitable[bool], bool]:  # to be overridden
        return True

    async def stop(self) -> bool:
        _res = self._close()
        if inspect.isawaitable(_res):
            _res = await _res
        if not _res:
            return False
        self._active = False
        if self._listener_manager:
            await self._listener_manager.close_listener(self)
        logger.info(f"{self.__class__.__name__} stopped!")
        return True

    def reload(self, versions=None, clear=True):
        self._messages.load(versions=versions, clear=clear)

    async def on_ready(self):
        if self._auto_start:
            await self.start()

    async def on_message(self, message: Message):
        pass

    async def on_connect(self):
        pass

    async def on_disconnect(self):
        pass

    async def on_typing(self, channel: discord.abc.Messageable, user: Union[User, Member], when: datetime.datetime):
        pass

    async def on_message_edit(self, before: Message, after: Message):
        pass

    async def on_raw_reaction_add(self, payload: RawReactionActionEvent):
        pass

    async def on_raw_reaction_remove(self, payload: RawReactionActionEvent):
        pass

    async def on_reaction_add(self, reaction: Reaction, user: Union[Member, User]):
        pass

    async def on_reaction_remove(self, reaction: Reaction, user: Union[Member, User]):
        pass

    async def on_reaction_clear(self, message: Message, reactions: List[Reaction]):
        pass

    async def on_member_join(self, member: Member):
        pass

    async def on_member_remove(self, member: Member):
        pass

    async def on_member_update(self, before: Member, after: Member):
        pass

    async def on_member_ban(self, guild: Guild, user: Union[User, Member]):
        pass

    async def on_member_unban(self, guild: Guild, user: Union[User, Member]):
        pass

    async def on_voice_state_update(self, member: Member, before: VoiceState, after: VoiceState):
        pass
