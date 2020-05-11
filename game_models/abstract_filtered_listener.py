import inspect
from typing import Collection, Optional, Union, List

import discord
from discord import Message, Reaction, Member, User

from default_collections import ChannelCollection, RoleCollection
from game_models.abstract_listener import AbstractListener
from helpers import user_to_member
from logger import logger
from models import ChannelDescription, RoleDescription
from models.abstract_models import SpecifiedDictCollection


class AbstractFilteredListener(AbstractListener):
    """Subclass of AbstractListener with listening filtered.

    Message filtering depends on custom roles, channels. If not defined, all are accepted

    Message filtering feature:
    --------------------------

    On game initialization (`__init__` method), it is possible to pass allowed/forbidden channels/roles/users
    If an item is not passed, all items are allowed or nothing is forbidden (depending on if item is allowed/forbidden).
    Then, filters apply on some events only:
    - on_message:
    In AbstractMiniGame subclasses, `_analyze_message` is called only if the message passes the filter.
    It is thus recommended to let `on_message` final and override `_analyze_message`

    - on_message_edit
    - on_reaction_add
    - on_reaction_remove
    - on_reaction_clear
    In AbstractMiniGame subclasses, you need to use a super call to know if the message passes the filter:

    ```
    async def on_message_edit(message):
        if not await super().on_message_edit(message):
            return
        # Your code
    ```
    """
    _default_allowed_channels: Collection[ChannelDescription] = None
    _default_forbidden_channels: Collection[ChannelDescription] = [ChannelCollection.LOG]

    _default_allowed_roles: Collection[RoleDescription] = None
    _default_forbidden_roles: Collection[RoleDescription] = None

    @staticmethod
    def _get_collection_args(kwargs, key, default, collection_class: SpecifiedDictCollection):
        args = kwargs.pop(key, False)
        if args is False:
            return default
        if args is None:
            return None
        res = []
        for _arg in args:
            if isinstance(_arg, collection_class.base_class):
                res.append(_arg)
            else:
                obj = collection_class.get(_arg, None)
                if obj:
                    res.append(obj)
        return res

    def __init__(self, **kwargs):
        self._master_channel_description = ChannelCollection.get(kwargs.pop("master_channel_description", "MEMO"))
        self._music_channel_description = ChannelCollection.get(kwargs.pop("music_channel_description", "MUSIC"))

        self._allowed_channels: Optional[Collection[ChannelDescription]] = self._get_collection_args(
            kwargs, "allowed_channels", self._default_allowed_channels, ChannelCollection)
        self._forbidden_channels: Optional[Collection[ChannelDescription]] = self._get_collection_args(
            kwargs, "forbidden_channels", self._default_forbidden_channels, ChannelCollection)
        self._allowed_roles: Optional[Collection[RoleDescription]] = self._get_collection_args(
            kwargs, "allowed_roles", self._default_allowed_roles, RoleCollection)
        self._forbidden_roles: Optional[Collection[RoleDescription]] = self._get_collection_args(
            kwargs, "forbidden_roles", self._default_forbidden_roles, RoleCollection)
        super().__init__(**kwargs)

    def _check_role_member(self, member: discord.Member) -> bool:
        if self._forbidden_roles is not None:
            for role in self._forbidden_roles:
                if role.has_the_role(member):
                    return False
        if self._allowed_roles is None:
            return True
        for role in self._allowed_roles:
            if role.has_the_role(member):
                return True
        return False

    def _check_channel(self, channel):
        if self._forbidden_channels is not None:
            for _channel in self._forbidden_channels:
                if _channel.is_in_channel(channel):
                    return False
        if self._allowed_channels is None:
            return True
        for _channel in self._allowed_channels:
            if _channel.is_in_channel(channel):
                return True
        return False

    def _filter_message(self, message: discord.Message) -> Optional[discord.Message]:
        """Returns None to discard the message, else the message to analyze"""
        if not self._check_channel(message.channel):
            return None
        if not self._check_role_member(user_to_member(message.guild, message.author)):
            return None
        return message

    async def _analyze_message(self, message):  # to be overridden
        """Analyze a message that respect the criteria defined."""
        pass

    async def on_message(self, message: Message):  # final
        message = self._filter_message(message)
        if message is None:
            # logger.debug(f"Message discarded: {message}")
            return
        logger.debug(f"Message {message.content[:100]} passed the filter in mini-game {self.__class__.__name__}")
        res = self._analyze_message(message)
        if inspect.isawaitable(res):
            res = await res
        return res

    async def on_message_edit(self, before: Message, after: Message):  # to be called with super
        message = self._filter_message(before)
        if message is None:
            # logger.debug(f"Message edit discarded: {before}")
            return False
        return True

    async def on_reaction_add(self, reaction: Reaction, user: Union[Member, User]):  # to be called with super
        message = self._filter_message(reaction.message)
        if message is None:
            # logger.debug(f"Reaction discarded: {reaction}")
            return False
        return True

    async def on_reaction_remove(self, reaction: Reaction, user: Union[Member, User]):  # to be called with super
        message = self._filter_message(reaction.message)
        if message is None:
            # logger.debug(f"Reaction removal discarded: {reaction}")
            return False
        return True

    async def on_reaction_clear(self, message: Message, reactions: List[Reaction]):  # to be called with super
        message = self._filter_message(message)
        if message is None:
            # logger.debug(f"Reactions discarded: Message {message} / Reactions {reactions}")
            return False
        return True
