import asyncio
from typing import Dict

import discord
from discord import TextChannel

from game_models.abstract_minigame import AbstractMiniGame
from helpers import format_channel, return_
from logger import logger


class ChannelGameStatus:
    def __init__(self, channel: discord.abc.GuildChannel):
        self._channel = channel
        self._data = {}  # not cleared nor reset
        self.number_of_games = 0  # not cleared
        self.active = False
        self.lock_init: asyncio.Lock = asyncio.Lock()
        self.lock_victory: asyncio.Lock = asyncio.Lock()

    # To be called in ChannelMiniGame._init_channel method, before a potential call to
    # ChannelMiniGame.reset_channel_stats (which calls the 'clear' method)
    def set_data(self, **data):
        self._data.update(data)

    @property
    def data(self):
        return self._data

    def clear(self):
        self._channel = self._channel.guild.get_channel(self._channel.id)  # refresh channels (members can change !)
        self.active = False

    def reset(self):
        self.clear()
        self.number_of_games = 0
        logger.info(f"Game reset in channel {format_channel(self._channel)} (Status type: {self.__class__.__name__})")


class ChannelGameStatuses:
    def __init__(self, default_factory=ChannelGameStatus):
        self._default_factory = default_factory
        self._data: Dict[discord.abc.GuildChannel, ChannelGameStatus] = {}

    def clear(self):
        self._data.clear()

    def __getitem__(self, item: discord.abc.GuildChannel):
        if item in self._data:
            return self._data[item]
        return self.__missing__(item)

    def __missing__(self, key: discord.abc.GuildChannel):
        self._data[key] = self._default_factory(key)
        return self._data[key]

    def __iter__(self):  # necessary, otherwise infinity loop when iterating or calling __contains__
        for channel in self._data:
            yield channel

    def __len__(self):
        return len(self._data)

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def items(self):
        return self._data.items()


class ChannelMiniGame(AbstractMiniGame):
    _max_games_per_channel = None  # A channel game is played as many times as wanted by default

    def __init__(self, **kwargs):
        self._max_plays = kwargs.pop("max_games", self._max_games_per_channel)  # None for infinite number of games
        super().__init__(**kwargs)
        self._channels: ChannelGameStatuses = ChannelGameStatuses()
        self._data = {}

    @property
    def channels(self):
        return self._channels

    @property
    def channels_list(self):
        if self._allowed_channels is None:
            return []
        return [channel_enum.value.object_reference for channel_enum in self._allowed_channels]

    def reset_channel_stats(self, channel):
        self._channels[channel].clear()

    # Start

    def _init(self) -> bool:
        if self._allowed_channels is None:
            return True  # ChannelMinigame allowed everywhere.
        for channel_enum in self._allowed_channels:
            channel = channel_enum.value.object_reference
            self.reset_channel_stats(channel)
        return True

    async def _init_channel(self, channel) -> bool:
        self.reset_channel_stats(channel)
        return True

    async def start_channel(self, channel) -> bool:
        if self._channels[channel].lock_init.locked():  # already starting the channel
            logger.info(f"The mini-game {self.__class__.__name__} is already starting in channel {channel}!")
            return False
        logger.debug(f"Starting channel {channel}, mini-game {self.__class__.__name__}")
        async with self._channels[channel].lock_init:
            if not self._active:
                logger.error("Cannot start channel if the mini-game has not started itself!")
                return False
            if not self._check_channel(channel):
                logger.warning(f"Channel {channel} is not allowed for this game!")
                return False
            if self._max_plays and self._channels[channel].number_of_games >= self._max_plays:
                logger.warning(f"Cannot init channel game {self.__class__.__name__}: number of games is over!")
                return False
            if self._channels[channel].active:
                logger.info(
                    f"Minigame {self.__class__.__name__} already started in channel {format_channel(channel)}")
                return False
            if await self._init_channel(channel):
                self._channels[channel].active = True
                logger.debug(f"Game {self.__class__.__name__} started in channel {format_channel(channel)}")
                if self._listener_manager:
                    await self._listener_manager.update_listeners()
                return True
            return False

    # Victory

    def _check_global_victory(self):
        sum_victories = sum((status.number_of_games for status in self._channels.values()))
        if sum_victories and sum_victories % len(self._channels) == 0:
            return True
        return False

    async def _on_channel_helped_victory(self, channel):  # to be overridden
        await self._on_channel_victory(channel)

    async def on_channel_helped_victory(self, channel):  # final
        if self._channels[channel].lock_victory.locked():
            logger.debug("Victory already started!")
            return
        async with self._channels[channel].lock_victory:
            if self._channels[channel].active:
                await return_(self._on_channel_helped_victory(channel))
                self._channels[channel].number_of_games += 1
            await self.stop_channel(channel)

    async def on_helped_victory(self):  # global helped victory
        for channel in self._channels:
            await self.on_channel_helped_victory(channel)
        await self.stop()

    async def _on_channel_victory(self, channel):  # to be overridden
        pass

    async def on_channel_victory(self, channel):  # final
        if self._channels[channel].lock_victory.locked():
            logger.debug("Victory already started!")
            return
        async with self._channels[channel].lock_victory:
            await return_(self._on_channel_victory(channel))
            if self._channels[channel].active:
                self._channels[channel].number_of_games += 1
            await self.stop_channel(channel)
            if self._check_global_victory():
                await self.on_victory()

    # Stop

    async def stop_channel(self, channel) -> bool:
        if channel not in self._channels:
            return False
        self._channels[channel].active = False
        if self._listener_manager:
            await self._listener_manager.update_listeners()
        return True

    async def stop(self) -> bool:
        if not await super().stop():
            return False
        for status in self._channels.values():
            status.active = False
            # NB: stop_channel method is not used to avoid multiple calls to self._listener_manager.update_listeners
        return True


class TextChannelMiniGame(ChannelMiniGame):
    async def _init_channel(self, channel) -> bool:
        if not isinstance(channel, TextChannel):
            logger.warning(f"Channel {channel} is not a text channel")
            return False
        self.reset_channel_stats(channel)
        return True
