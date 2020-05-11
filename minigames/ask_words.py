import asyncio
import random

import discord
from discord import Forbidden, HTTPException, Member, VoiceState, File, NotFound

from default_collections import Emojis, ChannelCollection, RoleCollection, CharacterCollection
from functions.text_analysis import check_answer, check_answer_and_return_it, TextAnalysisOptions
from game_models.abstract_channel_mini_game import ChannelGameStatus, ChannelGameStatuses, TextChannelMiniGame
from helpers.json_helpers import TranslationDict
from logger import logger


class Messages(TranslationDict):
    START = "I invite you to listen the singer!"
    RULES = "If you don't like it, say it with the correct words!"
    STAY_IN_AUDIO = "Stay in {salle_marine_mention} to be able to talk !"
    BAD_ANSWERS = ["You cannot say that ! Cancellation of previous answers !"]
    GOOD_ANSWERS = ["Yes, I understand that you are bored"]
    VICTORY = "Ok I understand, I'll kick the singer"
    MANDATORY_ANSWERS = ["a"]
    CORRECT_ANSWERS = ["b"]
    OPTIONAL_ANSWERS = ["c"]
    FORBIDDEN_ANSWERS = ["d"]
    MASTER = "lists:\n\nMANDATORY:\n{mandatory}\n\nCORRECT ({correct_proportion}% in the list):\n{correct}" \
             "\n\nOPTIONAL (1 optional = {bonus_proportion}% correct):\n{optional]" \
             "\n\nFORBIDDEN (1 forbidden = reset:\n{forbidden}",
    MASTER_ACTIONS = "⚠️ Use an external bot (Octave) with the singer role, make it join {back_channel} let it play!"
    WAITING_FOR_SINGER = "Waiting for the singer"
    SINGER_ARRIVED = "Here is {singer_name}!"
    MEMBERS_IMPOSSIBLE_TO_MOVE = "Member {member} cannot be moved! " \
                                 "Is it connected to a voice channel ? !\nOriginal error: {err}"
    CHARACTER_MESSAGES = ["Please, stop the music !", "Use my words to stop it!"]
    CHARACTER_MESSAGES_2 = ["I already heard {nb_correct} answers."]
    CHARACTER_MESSAGE_FILE = "files/placeholder.jpg"


MESSAGES = Messages(path="configuration/minigames/ask_words")


class AskWordsChannelStatus(ChannelGameStatus):
    def __init__(self, channel):
        super().__init__(channel)
        self.members = {}
        self.mandatory_answers = set()
        self.correct_answers = set()
        self.optional_answers = set()
        self.waiting = False
        self.count_messages = 0
        self.initial_message_sent = False  # not reset by clear
        self.webhook = None  # not reset by clear

    def clear(self):
        super().clear()
        self.members.clear()
        self.members.update({member: 0 for member in self._channel.members if not member.bot})
        self.mandatory_answers.clear()
        self.correct_answers.clear()
        self.optional_answers.clear()
        self.waiting = False
        self.count_messages = 0


class AskWordsGame(TextChannelMiniGame):
    _default_messages = MESSAGES

    def __init__(self, **kwargs):
        self._correct_answers_proportion = kwargs.pop("correct_answers_proportions", 0.2)
        # all optional answers = optional_answers_bonus_proportion of correct answers
        self._optional_answers_bonus_proportion = kwargs.pop("optional_answers_bonus_proportion", 0.5)
        self._voice_channel_description = ChannelCollection.get(kwargs.pop("voice_channel_description", "ROOM2_VOICE"))
        self._back_channel_description = ChannelCollection.get(kwargs.pop("back_channel_description", "AUDIO_BACK"))
        self._singer_role_description = RoleCollection.get(kwargs.pop("singer_role_description", "SINGER"))
        self._character_description = CharacterCollection.get(kwargs.pop("character_description", "CHARACTER2"))
        self._ignored_roles_descriptions = [RoleCollection.get(role_name) for role_name in
                                            kwargs.pop("ignored_roles_descriptions", ["DEV", "MASTER"])]
        super().__init__(**kwargs)
        self._simple_mode = None  # No simple mode
        self._channels = ChannelGameStatuses(AskWordsChannelStatus)
        self._nb_mandatory = len(self._messages["MANDATORY_ANSWERS"])
        self._nb_correct = len(self._messages["CORRECT_ANSWERS"])
        self._nb_optional = len(self._messages["OPTIONAL_ANSWERS"])
        if self._nb_optional:
            self._factor_optional = self._optional_answers_bonus_proportion * self._nb_correct / self._nb_optional
        else:
            self._factor_optional = 0

    async def _send_actions_for_master(self):
        msg = self._messages["MASTER_ACTIONS"].format(back_channel=self._back_channel_description.object_reference.name)
        await self._master_channel_description.object_reference.send(msg)

    async def _init(self) -> bool:
        await self._send_actions_for_master()
        return True

    async def _move_roles(self, origin_text_channel) -> bool:
        # You must have the move_members permission to use this.
        members = self._singer_role_description.object_reference.members
        for member in members:
            try:
                await member.edit(mute=False, voice_channel=self._voice_channel_description.object_reference)
            except (Forbidden, HTTPException) as err:
                msg = self._messages["MEMBERS_IMPOSSIBLE_TO_MOVE"].format(member=member.mention, err=err)
                logger.warning(msg)
                await self._master_channel_description.object_reference.send(msg)
                await self._send_actions_for_master()
                await origin_text_channel.send(self._messages["WAITING_FOR_SINGER"])
                self._channels[origin_text_channel].waiting = True
                return False
        self._channels[origin_text_channel].waiting = False
        await self._send_rules(origin_text_channel)
        return True

    async def _send_rules(self, channel):
        await asyncio.sleep(8)
        await channel.send(self._messages["RULES"])

    async def _mute_and_move_roles(self, mute=True):
        members = self._singer_role_description.object_reference.members
        for member in members:
            try:
                await member.edit(mute=mute)
            except (Forbidden, HTTPException) as err:
                logger.warning(f"Impossible to mute {member}! Ignoring it. Error: {err}")
        await asyncio.sleep(5)
        for member in members:
            channel = self._back_channel_description.object_reference
            try:
                await member.move_to(channel)
            except (Forbidden, HTTPException) as err:
                logger.warning(f"Impossible to move {member} to {channel}! Ignoring it. Error: {err}")

    async def _init_channel(self, channel) -> bool:
        if not await super()._init_channel(channel):
            return False
        msg = self._messages["MASTER"].format(mandatory=self._messages["MANDATORY_ANSWERS"],
                                              correct=self._messages["CORRECT_ANSWERS"],
                                              optional=self._messages["OPTIONAL_ANSWERS"],
                                              forbidden=self._messages["FORBIDDEN_ANSWERS"],
                                              correct_proportion=self._correct_answers_proportion * 100,
                                              bonus_proportion=self._optional_answers_bonus_proportion * 100
                                              )
        await self._master_channel_description.object_reference.send(msg)
        await channel.send(self._messages["START"])
        await self._move_roles(channel)
        logger.debug(f"{self.__class__.__name__} started for channel {channel}")
        return True

    def reset_counter(self, channel):
        self.reset_channel_stats(channel)
        self._channels[channel].active = True

    def _count_nb_correct(self, channel):
        return int(len(self._channels[channel].correct_answers)
                   + len(self._channels[channel].optional_answers) * self._factor_optional)

    def _nb_correct_to_reach(self):
        return int(self._correct_answers_proportion * self._nb_correct)

    def _check_victory(self, channel):
        nb_correct = self._count_nb_correct(channel)
        if (len(self._channels[channel].mandatory_answers) >= self._nb_mandatory
                and (nb_correct >= self._nb_correct_to_reach())):
            return True
        return False

    async def _on_channel_victory(self, channel):
        await channel.send(self._messages["VICTORY"])
        await self._mute_and_move_roles()

    async def _check_and_handle_victory(self, channel):
        if self._check_victory(channel):
            await self.on_channel_victory(channel)

    async def _analyze_message(self, message: discord.Message):
        if not self._active or not self._channels[message.channel].active:
            if message.content == Emojis.anchor:
                return await self.start_channel(message.channel)
            return

        if message.author.bot:
            return

        if not self._channels[message.channel].active:  # game already ended
            logger.debug("Game already ended")
            return

        if ((not message.author.voice
             or message.author.voice.channel != self._voice_channel_description.object_reference)
                and not any(role_descr.has_the_role(message.author)
                            for role_descr in self._ignored_roles_descriptions)):
            msg = self._messages["STAY_IN_AUDIO"].format(
                salle_marine_mention=self._voice_channel_description.object_reference.mention)
            await message.channel.send(msg)
            return

        channel = message.channel

        # Send a webhook message from character
        if self._channels[channel].count_messages % 10 == 2:
            if not self._channels[channel].webhook:
                self._channels[channel].webhook = await self._character_description.get_instance(channel)
            try:
                self._channels[channel].webhook.send(random.choice(self._messages["CHARACTER_MESSAGES"]))
                if self._count_nb_correct(channel):
                    self._channels[channel].webhook.send(random.choice(
                        self._messages["CHARACTER_MESSAGES_2"]).format(nb_correct=self._count_nb_correct(channel)))
            except NotFound as err:
                logger.exception(err)
                self._channels[channel].webhook = None
            if self._channels[channel].count_messages == 10:
                self._channels[channel].webhook.send(file=File(self._messages["CHARACTER_MESSAGE_FILE"]))
        self._channels[channel].count_messages += 1

        # Check forbidden answers (exact word check)
        if check_answer(message.content, self._messages["FORBIDDEN_ANSWERS"],
                        options=[TextAnalysisOptions.STRICT_EQUAL]):
            await message.add_reaction(Emojis.interrobang)
            await channel.send(random.choice(self._messages["BAD_ANSWERS"]))
            self.reset_counter(channel)
            await message.add_reaction(Emojis.face_with_symbols_over_mouth)
            await asyncio.sleep(5)
            await message.add_reaction(Emojis.name_badge)
            await message.delete(delay=2)
            return

        # Check correct messages
        messages_to_check = (self._messages["MANDATORY_ANSWERS"],
                             self._messages["CORRECT_ANSWERS"],
                             self._messages["OPTIONAL_ANSWERS"])
        answers_to_update = (self._channels[channel].mandatory_answers,
                             self._channels[channel].correct_answers,
                             self._channels[channel].optional_answers)
        answers_to_send = (self._messages["GOOD_ANSWERS"], self._messages["GOOD_ANSWERS"], None)
        for msg_to_check, dict_to_update, answer_list_to_send in zip(messages_to_check, answers_to_update,
                                                                     answers_to_send):
            ans = check_answer_and_return_it(message.content, msg_to_check)
            if ans is not None and ans not in dict_to_update:  # mandatory/correct/optional answer detected
                if answer_list_to_send:
                    await channel.send(random.choice(answer_list_to_send))
                dict_to_update.add(ans)
                return await self._check_and_handle_victory(channel)

    async def on_voice_state_update(self, member: Member, before: VoiceState, after: VoiceState):
        if self._singer_role_description.object_reference in member.roles:
            if after.channel is None:  # singer not in a voice channel
                return

            for channel, status in self._channels.items():
                if status.waiting:
                    status.waiting = False
                    await channel.send(self._messages["SINGER_ARRIVED"].format(singer_name=member.display_name))
                    await self._send_rules(channel)
