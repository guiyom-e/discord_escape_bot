import random
from typing import Optional

import discord
from discord import TextChannel, VoiceChannel, Member, VoiceState

from default_collections import ChannelCollection, CharacterCollection
from functions.text_analysis import check_answer
from game_models.abstract_minigame import AbstractMiniGame
from helpers import long_send
from helpers.json_helpers import TranslationDict
from helpers.sound_helpers import SoundTools
from logger import logger


class Messages(TranslationDict):
    # Default values (overridden if a translation is loaded)
    MASTER = "Matches:\n{matches}"
    WELCOME = "Game explanation"
    WELCOME_AUDIO = "files/sample.wav"
    CHARACTER_NAME = "Bobby"
    OK_MESSAGES = ["Ok!", "Good!"]
    SIGN = "Emoji linked to this piece of furniture: {emoji}."
    NO_MESSAGES = ["No!", "I don't believe it!"]
    ASK_TO_REPEAT = "Mention the channel to repeat (with the '#')"
    NEW_ROOM_MESSAGES = ["You can ask for a new room."]
    ONE_ROOM_AT_A_TIME = "One room after another!"
    VICTORY = "Every room explored! You can use the correct emoji in the right room."
    VICTORY_AUDIO = "files/sample.wav"
    HELPED_VICTORY = "You can use this emoji in the correct room: {emoji}"
    CORRECT_ROOM = "MAIN_ROOM"
    LISTENING_TO_ANSWER = "Listening to answer for {channel_mention}"
    NO_ANSWER = "No answer for {channel_mention}"

    # WARN: MATCHES keys must be names of ChannelCollection !
    MATCHES = {"WELCOME": {"answers": ["piece of furniture"], "file": "files/sample.wav", "emoji": "📘"},
               }


MESSAGES = Messages(path="configuration/minigames/offices_game")


class OfficesGame(AbstractMiniGame):
    """Cooperation game with 2 offices: a voice channel and a text channel."""
    _default_messages = MESSAGES

    def __init__(self, **kwargs):
        self._minimum_rooms_to_explore: Optional[int] = kwargs.pop("minimum_rooms_to_explore", None)  # None for maximum
        self._text_channel_d = ChannelCollection.get(kwargs.pop("text_channel_description", "ROOM3"))
        self._voice_channel_d = ChannelCollection.get(kwargs.pop("voice_channel_description", "ROOM4_VOICE"))
        self._matching_key = kwargs.pop("matching_key", "name")  # change not recommended: key must be unique !

        super().__init__(**kwargs)
        self._simple_mode = None  # No simple mode
        self._text_channel: Optional[TextChannel] = None
        self._voice_channel: Optional[VoiceChannel] = None
        self._matches_done = {}
        self._correct_room = None
        self.current_room = None
        # noinspection PyTypeChecker
        self._sound_tools: SoundTools = None
        self._character_description = CharacterCollection.get(kwargs.pop("character_description", "CHARACTER3"))

    async def _init(self):
        self._text_channel = self._text_channel_d.object_reference
        self._voice_channel = self._voice_channel_d.object_reference
        self._matches = {getattr(ChannelCollection[channel_enum_name], self._matching_key): value
                         for channel_enum_name, value in self._messages["MATCHES"].items()}
        self._correct_room = getattr(ChannelCollection[self._messages["CORRECT_ROOM"]], self._matching_key)
        self._matches_done.clear()
        self.current_room = None
        self._sound_tools = SoundTools.get(self.guild)
        self._webhook = await self._character_description.get_instance(self._text_channel)
        format_matches = "\n".join([f"{k} (emoji {v['emoji']}): {v['answers']}"
                                    for k, v in self._matches.items()])
        await long_send(self._master_channel_description.object_reference,
                        self._messages["MASTER"].format(matches=format_matches), quotes=False)
        self._webhook.send(self._messages["WELCOME"])
        await self._sound_tools.play(self._voice_channel, self._messages["WELCOME_AUDIO"], force=True)
        return True

    async def _on_victory(self, *args, **kwargs):
        self._webhook.send(self._messages["VICTORY"])
        await self._sound_tools.play(self._voice_channel, self._messages["VICTORY_AUDIO"], force=True)

    async def _on_helped_victory(self):
        emoji = self._messages["MATCHES"].get(self._messages["CORRECT_ROOM"], {}).get('emoji', '_?_')
        self._webhook.send(self._messages["HELPED_VICTORY"].format(emoji=emoji))
        await self._on_victory()

    async def _check_victory(self):
        minimum_rooms_to_explore = min(self._minimum_rooms_to_explore or len(self._matches), len(self._matches))
        if len(self._matches_done) >= minimum_rooms_to_explore and self._matches_done.get(self._correct_room, False):
            # if the minimum number of rooms have been explored and the correct room explored: victory
            return await self.on_victory()

    async def _analyze_message(self, message: discord.Message):
        if not self._active:
            return
        if message.channel != self._text_channel:
            return
        if message.author.bot:
            return

        if not message.channel_mentions:
            return
        if len(message.channel_mentions) > 1:
            self._webhook.send(self._messages["ONE_ROOM_AT_A_TIME"])
            return

        # search an answer:
        for room_key, match_values in self._matches.items():
            if check_answer(message.content, possible_answers=match_values["answers"]):
                # TODO: add forbidden answers ?
                self._webhook.send(random.choice(self._messages["OK_MESSAGES"]))
                self._webhook.send(self._messages["SIGN"].format(emoji=match_values["emoji"]))
                self._matches_done[room_key] = True
                self.current_room = None
                return await self._check_victory()

        # If a room has been asked to Tintin and a bad answer (len(msg)>1) is given
        if self.current_room and len(message.content.strip().split()) > 1:
            self._webhook.send(random.choice(self._messages["NO_MESSAGES"]))
            self.current_room = None
            self._webhook.send(self._messages["ASK_TO_REPEAT"])
            return

        # Else: no research at the moment: create a new research.
        search_channel = message.channel_mentions[0]
        channel_key = getattr(search_channel, self._matching_key)
        matches_value = self._matches.get(channel_key, None)
        if not matches_value:
            logger.debug(f"No message associated to channel {search_channel.name} (with attr key '{channel_key}')")
            self._webhook.send(self._messages["NO_ANSWER"].format(channel_mention=search_channel.mention))
            return
        self.current_room = channel_key
        # Play even if something is already playing
        self._webhook.send(self._messages["LISTENING_TO_ANSWER"].format(channel_mention=search_channel.mention))
        await self._sound_tools.play(self._voice_channel, matches_value["file"], force=True)

    async def on_voice_state_update(self, member: Member, before: VoiceState, after: VoiceState):
        if not self.active:
            return
        if after.channel == self._voice_channel and before.channel != after.channel:
            # New user
            # Play even if something is already playing
            await self._sound_tools.play(self._voice_channel, self._messages["WELCOME_AUDIO"], force=True)
