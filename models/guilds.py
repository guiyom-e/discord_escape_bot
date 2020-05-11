from typing import Dict, Any, Union, Optional

import discord
from discord import Guild

from constants import GAME_LANGUAGE
from logger import logger
from models.abstract_models import DiscordObjectDict, SpecifiedDictCollection


class GuildDescription(DiscordObjectDict):
    """Describes a guild."""
    _updatable_keys = ["name", "icon"]
    _export_keys = ["name", "icon"]  # TODO: not complete

    def __init__(self, name, icon: Union[str, bytes] = None, **kwargs):
        """
        Parameters
        ----------
        name: :class:`str`
            The new name of the guild.
        description: :class:`str`
            The new description of the guild. This is only available to guilds that
            contain `VERIFIED` in :attr:`Guild.features`.
        icon: :class:`bytes`
            A :term:`py:bytes-like object` representing the icon. Only PNG/JPEG supported
            and GIF for guilds with ``ANIMATED_ICON`` feature.
            Could be ``None`` to denote removal of the icon.
        banner: :class:`bytes`
            A :term:`py:bytes-like object` representing the banner.
            Could be ``None`` to denote removal of the banner.
        splash: :class:`bytes`
            A :term:`py:bytes-like object` representing the invite splash.
            Only PNG/JPEG supported. Could be ``None`` to denote removing the
            splash. Only available for partnered guilds with ``INVITE_SPLASH``
            feature.
        region: :class:`VoiceRegion`
            The new region for the guild's voice communication.
        afk_channel: Optional[:class:`VoiceChannel`]
            The new channel that is the AFK channel. Could be ``None`` for no AFK channel.
        afk_timeout: :class:`int`
            The number of seconds until someone is moved to the AFK channel.
        owner: :class:`Member`
            The new owner of the guild to transfer ownership to. Note that you must
            be owner of the guild to do this.
        verification_level: :class:`VerificationLevel`
            The new verification level for the guild.
        default_notifications: :class:`NotificationLevel`
            The new default notification level for the guild.
        explicit_content_filter: :class:`ContentFilter`
            The new explicit content filter for the guild.
        vanity_code: :class:`str`
            The new vanity code for the guild.
        system_channel: Optional[:class:`TextChannel`]
            The new channel that is used for the system channel. Could be ``None`` for no system channel.
        system_channel_flags: :class:`SystemChannelFlags`
            The new system channel settings to use with the new system channel.
        reason: Optional[:class:`str`]
            The reason for editing this guild. Shows up on the audit log.
        """
        super().__init__(**kwargs)
        self.name = name
        if isinstance(icon, (bytes, bytearray)) or icon is None:
            self.icon: Optional[bytearray] = icon
        else:
            self.icon: bytearray = bytearray.fromhex(str(icon))

    @classmethod
    def from_dict(cls, dico: Dict[str, Any]):
        return cls(**dico)


class AbstractGuildCollection(SpecifiedDictCollection):
    _base_class = GuildDescription


class GuildWrapper:
    """Guild wrapper: reacts as a Guild object, but with more methods available."""

    def __init__(self, bot: discord.Client, guild: Guild = None):
        self._bot = bot
        self._guild = guild
        self._game_manager: 'ListenerManager' = None
        self._nb_teams = 3  # 3 by default
        self._versions = []

    @property
    def versions(self):
        return self._versions

    @versions.setter
    def versions(self, value):
        versions = value or GAME_LANGUAGE
        self._versions = [versions] if isinstance(versions, str) else versions or []

    @property
    def nb_teams(self):
        return self._nb_teams

    @nb_teams.setter
    def nb_teams(self, value):
        if value not in (1, 2, 3):
            logger.warning(f"Cannot set nb_teams to {value}")
            return
        self._nb_teams = value

    @property
    def guild(self):
        return self._guild

    async def show_control_panel(self):
        return await self._game_manager.show_control_panel(self._guild)

    @property
    def listeners(self):
        if not self.listener_manager:
            return []
        return self._game_manager.all_listeners

    async def clear_listeners(self):
        await self._game_manager.clear_listeners()

    async def add_listeners(self, mini_games):
        await self._game_manager.add_listeners(mini_games)

    @property
    def active_listeners(self):
        if not self.listener_manager:
            return set()
        return self._game_manager.active_listeners

    @property
    def listener_manager(self):
        return self._game_manager

    @listener_manager.setter
    def listener_manager(self, value):
        self._game_manager = value

    @property
    def is_undefined(self):
        return self._guild is None

    def __eq__(self, other):
        if isinstance(other, int):
            return self._guild.id == other
        if isinstance(other, Guild):
            return self._guild == other
        if isinstance(other, self.__class__):
            return self is other
        return False

    def __repr__(self):
        return f"GuildWrapper of {self._guild.__repr__()}"

    def __getattr__(self, item: str):
        return getattr(self._guild, item)
