import asyncio
import random
from typing import Optional

import discord
from discord import TextChannel, File, VoiceChannel, Member, VoiceState

from default_collections import ChannelCollection
from game_models.abstract_minigame import AbstractMiniGame
from helpers import SoundTools
from helpers.json_helpers import TranslationDict


class Messages(TranslationDict):
    # Default values (overridden if a translation is loaded)
    VALID_EMOJIS = {"📕": "Yes!", "🧲": "Magnet, yes!", "🔑": "Key, yes!"}
    VALIDATION = "Yes!\n\nA key has been found: {key_emoji}. Use it!"
    KEY_EMOJI = "🗝"
    AUDIO_FILES = ["files/sample.wav"]
    VICTORY = "The restricted room is open!"
    VICTORY_FILE = "files/placeholder.png"
    VICTORY_2 = "We found what we were looking for!"
    VICTORY_FILE_2 = "files/placeholder.png"
    MASTER = "Three emojis to be validated: {emojis}.\nThen, use the emoji {key_emoji} to open the restricted room."


MESSAGES = Messages(path="configuration/minigames/end_game")


class EndGame(AbstractMiniGame):
    _default_messages = MESSAGES

    def __init__(self, **kwargs):
        self._text_channel_d = ChannelCollection.get(kwargs.pop("text_channel_description", "MAIN_ROOM"))
        self._voice_channel_d = ChannelCollection.get(kwargs.pop("voice_channel_description", "RESTRICTED_ROOM"))

        super().__init__(**kwargs)
        self._simple_mode = None  # No simple mode
        self._text_channel: Optional[TextChannel] = None
        self._voice_channel: Optional[VoiceChannel] = None
        self._emojis_done = set()
        self._first_victory = False

    async def _init(self) -> bool:
        self._text_channel = self._text_channel_d.object_reference
        self._voice_channel = self._voice_channel_d.object_reference
        self._emojis_done.clear()
        self._first_victory = False
        await self._master_channel_description.object_reference.send(
            self._messages["MASTER"].format(emojis=self._messages["VALID_EMOJIS"],
                                            key_emoji=self._messages["KEY_EMOJI"]))
        return True

    async def _on_victory(self, *args, **kwargs):
        if len(CongratulationsGame.instances(self.guild)):
            await CongratulationsGame.instances(self.guild)[0].start()
        await self._text_channel.send(self._messages["VICTORY"], file=File(self._messages["VICTORY_FILE"]))
        await self._voice_channel.edit(sync_permissions=True)
        await asyncio.sleep(10)
        await self._text_channel.send(self._messages["VICTORY_2"], file=File(self._messages["VICTORY_FILE_2"]))

    async def _check_first_victory(self):
        if len(self._emojis_done) == len(self._messages["VALID_EMOJIS"]):
            self._first_victory = True
            await asyncio.sleep(2)
            await self._text_channel.send(self._messages["VALIDATION"].format(key_emoji=self._messages["KEY_EMOJI"]))

    async def _analyze_message(self, message: discord.Message):
        if not self._active:
            return
        if message.channel != self._text_channel:
            return

        if message.content in self._messages["VALID_EMOJIS"]:
            self._emojis_done.add(message.content)
            await self._text_channel.send(self._messages["VALID_EMOJIS"][message.content])
            return await self._check_first_victory()

        if self._first_victory and self._messages["KEY_EMOJI"] in message.content:
            return await self.on_victory()


class CongratulationsGame(AbstractMiniGame):
    _default_messages = MESSAGES

    def __init__(self, **kwargs):
        self._voice_channel_d = ChannelCollection.get(kwargs.pop("voice_channel_description", "RESTRICTED_ROOM"))
        super().__init__(**kwargs)
        self._simple_mode = None  # No simple mode
        self._sound_tools: SoundTools = None
        self._voice_channel: Optional[VoiceChannel] = None

    async def _init(self) -> bool:
        self._sound_tools = SoundTools.get(self.guild)
        self._voice_channel = self._voice_channel_d.object_reference
        await self._voice_channel.edit(sync_permissions=True)
        return True

    async def on_voice_state_update(self, member: Member, before: VoiceState, after: VoiceState):
        # Say Congratulations to newcomers in the restricted room !
        if after.channel == self._voice_channel and before.channel != after.channel:
            # Play only if something is not already playing
            await self._sound_tools.play(self._voice_channel, random.choice(self._messages["AUDIO_FILES"]), force=False)

    # TODO: add an end ?
