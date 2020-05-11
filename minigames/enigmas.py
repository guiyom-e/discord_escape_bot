import asyncio
import random
from enum import Enum

import discord
from discord import File

from default_collections import Emojis, GeneralMessages, CharacterCollection
from functions.text_analysis import TextAnalysisOptions, check_answer_and_return_it
from game_models.abstract_channel_mini_game import ChannelGameStatus, ChannelGameStatuses, TextChannelMiniGame
from helpers import TranslationDict, long_send
from logger import logger


class Messages(TranslationDict):
    MASTER = "[ROOM]\nEnigmas and answers: {answers}",
    START = "La boîte aux énigmes est ouverte !"
    START_2 = "Hey!"
    REPEAT = "Je répète mon énigme :\n"
    ASK_FOR_NEW_ENIGMA = "Si tu veux une nouvelle énigme, envoie une clé {emoji}!"
    EMOJI_NEXT = Emojis.key2
    EMOJI_START = Emojis.sunflower
    VICTORY = "Bravo ! Tu as trouvé toutes les énigmes !"
    NO_MORE_ENIGMA = "Désolé, tu as épuisé toutes mes énigmes !"
    MODE = "RANDOM"  # must be one of EnigmaMode name
    ENIGMAS = {
        "cheval_blanc": {
            "question": "Quelle est la couleur du cheval blanc d'Henri IV ?",
            "answers": ["blanc"],
            "forbidden": ["bleu", "rouge"],
            "options": [0],
            "files": [],
            "type": 0
        },
        "cheval_bleu": {
            "question": "Quelle est la couleur du cheval bleu d'Henri IV ?",
            "answers": ["bleu"],
            "options": [1],
        },
        "cheval_rouge": {
            "question": "Quelle est la couleur du cheval rouge d'Henri IV ?",
            "answers": ["rouge", "sang"],
            "options": [2],
            "type": 2,
            "proportion": 0.5,
            "nb_min": 1,
        }
    }


MESSAGES = Messages(path="configuration/minigames/enigmas")
MESSAGES_MAP = Messages(path="configuration/minigames/enigmas/map")


class Status(Enum):
    NEW = 0
    ASKED = 1
    ANSWERED = 2


class EnigmaMode(Enum):
    RANDOM = 0
    ORDERED = 1


class EnigmaType(Enum):
    ANY = 0  # one answer in answer list is sufficient to win
    ALL = 1  # all answers in answer must be sent to win
    PARTIAL = 2  # a proportion of answers defined must be sent to win.
    # proportion or nb_min must be defined for PARTIAL, otherwise it is considered ALL


class EnigmaChannelStatus(ChannelGameStatus):
    def __init__(self, channel):
        # data must be {"enigmas": enigmas}
        super().__init__(channel)
        self.members = {}
        self.statuses = {}
        self.answered_answers = {}  # for enigmas of type 1
        self.current = None
        self.webhook = None

    def clear(self):
        super().clear()
        self.members.clear()
        self.members.update({member: 0 for member in self._channel.members if not member.bot})
        self.statuses.clear()
        self.statuses.update({key: Status.NEW for key in self._data.get("enigmas", [])})
        self.answered_answers.clear()
        self.answered_answers.update({key: set() for key in self._data.get("enigmas", [])})
        self.current = None


class EnigmasGame(TextChannelMiniGame):
    _default_messages = MESSAGES

    def __init__(self, **kwargs):
        self._ask_for_next_enigma = kwargs.pop("ask_for_next_enigma", True)
        self._character_description = CharacterCollection.get(kwargs.pop("character_key", "CHARACTER1"))
        super().__init__(**kwargs)
        self._simple_mode = None  # No simple mode
        self._channels = ChannelGameStatuses(EnigmaChannelStatus)
        self._enigma_mode: EnigmaMode = None

    async def _init(self) -> bool:
        self._enigma_mode = EnigmaMode[self._messages.get("MODE", "ORDERED")]
        return True

    async def _init_channel(self, channel) -> bool:
        self._channels[channel].set_data(enigmas=self._messages["ENIGMAS"])
        if not await super()._init_channel(channel):
            return False
        answers = "\n" + "\n".join([f"{v['question']} : {v['answers']}" for v in self._messages["ENIGMAS"].values()])
        await long_send(self._master_channel_description.object_reference,
                        self._messages["MASTER"].format(answers=answers), quotes=False)
        self._channels[channel].webhook = await self._character_description.get_instance(channel)
        self._channels[channel].webhook.send(self._messages["START"])
        await asyncio.sleep(7)
        self._channels[channel].webhook.send(self._messages["START_2"])
        await self.ask_enigma(channel)
        logger.debug(f"Enigmas started for channel {channel}")
        return True

    def reset_channel_stats(self, channel):
        super().reset_channel_stats(channel)
        logger.debug(f"Playing members: {self._channels[channel].members}")

    def get_new_enigmas(self, channel):
        all_enigmas = self._messages["ENIGMAS"]
        all_statuses = self._channels[channel].statuses
        enigma_keys = [enigma for enigma in all_enigmas if all_statuses[enigma] is Status.NEW]
        return enigma_keys

    def get_new_enigma(self, channel):
        random_choice = True if self._enigma_mode is EnigmaMode.RANDOM else False
        enigma_keys = self.get_new_enigmas(channel)
        if not enigma_keys:
            return None
        if random_choice:
            return random.choice(enigma_keys)
        return enigma_keys[0]

    async def _on_channel_victory(self, channel):
        self._channels[channel].webhook.send(self._messages["VICTORY"])

    async def _analyze_message(self, message: discord.Message):
        if message.author.bot:
            return

        if not self._active or not self._channels[message.channel].active:
            if message.content == self._messages["EMOJI_START"]:
                return await self.start_channel(message.channel)
            return

        if message.content == self._messages["EMOJI_NEXT"]:
            current_enigma = self._channels[message.channel].current
            if current_enigma is None:
                # Ask a new enigma is not current enigma
                await self.ask_enigma(message.channel)
            else:
                # Repeat the current enigma
                self._channels[message.channel].webhook.send(
                    self._messages["REPEAT"] + self._messages["ENIGMAS"][current_enigma]["question"]
                )
            return

        if not self._channels[message.channel].active:  # game already ended
            logger.debug("Game already ended")
            return

        current_enigma = self._channels[message.channel].current
        if current_enigma is None:
            # No enigma for the moment
            return
        enigmas = self._messages["ENIGMAS"]
        possible_answers = set(enigmas[current_enigma]["answers"])
        forbidden_answers = enigmas[current_enigma].get("forbidden", None)
        options = [TextAnalysisOptions(option) for option in enigmas[current_enigma].get("options", [])]

        statuses = self._channels[message.channel].statuses
        answered_answers = self._channels[message.channel].answered_answers

        enigma_type = EnigmaType(enigmas[current_enigma].get("type", 0))
        if enigma_type is EnigmaType.ANY:  # ANY: one answer is sufficient
            answer = check_answer_and_return_it(message.content, possible_answers, forbidden_answers=forbidden_answers,
                                                options=options)
        else:  # ALL/PARTIAL: all/a proportion of answers are necessary
            answer = None
            for possible_answer in possible_answers:
                _answer = check_answer_and_return_it(message.content, [possible_answer],
                                                     forbidden_answers=forbidden_answers, options=options)
                if _answer is not None:
                    if _answer not in answered_answers[current_enigma]:
                        self._channels[message.channel].webhook.send(random.choice(GeneralMessages["GOOD_ANSWERS"]))
                        answered_answers[current_enigma].add(_answer)
                    answer = _answer

        if answer is not None:  # check victory
            max_nb_to_find = len(set(enigmas[current_enigma]["answers"]))
            nb_to_find = max_nb_to_find if enigma_type is EnigmaType.ALL \
                else min(enigmas[current_enigma].get("nb_min", max_nb_to_find),
                         enigmas[current_enigma].get("proportion", 1) * max_nb_to_find)

            if enigma_type is EnigmaType.ANY or len(answered_answers[current_enigma]) >= nb_to_find:
                # Complete answer validated !
                statuses[current_enigma] = Status.ANSWERED
                self._channels[message.channel].current = None
                self._channels[message.channel].webhook.send(random.choice(GeneralMessages.GOOD_ANSWERS))
                logger.info(f"Successfully answered to {current_enigma}")
                if not self.get_new_enigma(message.channel):
                    await self.on_channel_victory(message.channel)
                    return  # all enigmas answered !
                if self._ask_for_next_enigma:
                    self._channels[message.channel].webhook.send(
                        self._messages["ASK_FOR_NEW_ENIGMA"].format(emoji=self._messages["EMOJI_NEXT"]))
                else:
                    await self.ask_enigma(message.channel)
            return
        # Bad answer
        self._channels[message.channel].webhook.send(random.choice(GeneralMessages["BAD_ANSWERS"]))

    async def ask_enigma(self, channel):
        enigma_key = self.get_new_enigma(channel)
        if not enigma_key:
            self._channels[channel].webhook.send(self._messages["NO_MORE_ENIGMA"])
            return  # end of enigmas
        files = [File(path) for path in self._messages["ENIGMAS"][enigma_key].get("files", [])]
        self._channels[channel].webhook.send(self._messages["ENIGMAS"][enigma_key]["question"], files=files or None)
        self._channels[channel].statuses[enigma_key] = Status.ASKED
        self._channels[channel].current = enigma_key


class MapEnigmasGame(EnigmasGame):
    _default_messages = MESSAGES_MAP

    async def _init_channel(self, channel) -> bool:
        is_ok = await super()._init_channel(channel)
        if is_ok:
            await channel.edit(sync_permissions=True)
        return is_ok
