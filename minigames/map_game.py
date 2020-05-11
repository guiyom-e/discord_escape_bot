import asyncio

import discord

from functions.text_analysis import check_answer, check_answer_and_return_it
from game_models.abstract_channel_mini_game import ChannelGameStatus, ChannelGameStatuses, TextChannelMiniGame
from helpers.json_helpers import TranslationDict


class Messages(TranslationDict):
    INTRO = "Intro",
    MASTER = "**[MAP]**\nIntermediate codes: {codes}",
    MAP_ANNOUNCEMENT = "Map is",
    MAP_LINK_PREFIX = "link/",
    MAP_NAME = "Map",
    MAP_CODE = 0,
    ERROR_TITLE = "Not a good code",
    ERROR_MESSAGE = "No ! {code} is incorrect!",
    INTERMEDIATE_CODES = ["A", "B"],
    INTERMEDIATE_ANSWER = "Yes, '{code}' is correct",
    FINAL_CODE = "ABCDE",
    VICTORY = "Yes! This is the code.",
    HELPED_VICTORY = "Ok, I help.",
    WORDS_TO_FIND = "intermediate codes are: A, B"


MESSAGES = Messages(path="configuration/minigames/map_game")


class MapGameChannelStatus(ChannelGameStatus):
    def __init__(self, channel):
        super().__init__(channel)
        self.success = True

    def clear(self):
        super().clear()
        self.success = False


class MapGame(TextChannelMiniGame):
    _default_messages = MESSAGES

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._simple_mode = None  # No simple mode
        self._channels = ChannelGameStatuses(MapGameChannelStatus)

    async def _init_channel(self, channel) -> bool:
        if not await super()._init_channel(channel):
            return False
        await channel.edit(sync_permissions=True)
        await self._master_channel_description.object_reference.send(
            self._messages["MASTER"].format(codes=self._messages["INTERMEDIATE_CODES"]))
        await channel.send(self._messages["INTRO"])
        await asyncio.sleep(7)
        msg = f"{self._messages['MAP_ANNOUNCEMENT']}{self._messages['MAP_LINK_PREFIX']}{self._messages['MAP_CODE']}"
        await channel.send(msg)
        return True

    async def _on_channel_helped_victory(self, channel):
        self._channels[channel].success = True
        await channel.send(self._messages["HELPED_VICTORY"])
        await channel.send(self._messages["WORDS_TO_FIND"])

    async def _on_channel_victory(self, channel):
        self._channels[channel].success = True
        await channel.send(self._messages["VICTORY"])

    async def _analyze_message(self, message: discord.Message):
        if not self._active or not self._channels[message.channel].active:
            return

        if message.author.bot:
            return

        if check_answer(message.content, [self._messages["FINAL_CODE"]]):
            await self.on_channel_victory(message.channel)
            return

        code_found = check_answer_and_return_it(message.content, self._messages["INTERMEDIATE_CODES"])
        if code_found is not None:
            await message.channel.send(self._messages["INTERMEDIATE_ANSWER"].format(code=code_found))
