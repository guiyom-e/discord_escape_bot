import asyncio
import random
from enum import Enum

from default_collections import Emojis, GeneralMessages, ChannelCollection, RoleCollection, MinigameCollection
from functions.text_analysis import check_answer
from game_models.abstract_channel_mini_game import ChannelGameStatuses, ChannelGameStatus, \
    TextChannelMiniGame
from helpers import send_dm_message
from bot_management.listener_utils import start_next_minigame
from helpers.json_helpers import TranslationDict
from logger import logger


class Messages(TranslationDict):
    INTRO = "Trouve les ingrédients avec les bonnes quantités pour la recette de 'chocolat au beurre'!"
    REPEAT = INTRO + "\nPour chaque ingrédient envoie dans un message son nom et sa quantité. " \
                     "Un message personnel a dû t'être envoyé !"
    VICTORY = "Bravo ! La recette est complète !"
    CLUE_MESSAGES = [
                        "Il faut 2 fois plus de beurre que de sucre",
                        "Il faut 1kg de sucre",
                        "If faut autant de chocolat que de sucre"
                    ],
    USELESS_MESSAGES = [
        "Le chocolat doit être bon.",
        "Il ne faut pas de batteur à oeufs."
    ]
    SOLUTIONS = {
        "beurre": {"solution": ["2", "2kg"],
                   "forbidden": ["1", "3", "4", "5", "sucre", "chocolat"]},
        "sucre": {"solution": ["1", "1kg"],
                  "forbidden": ["2", "3", "4", "5", "beurre", "chocolat"]},
        "chocolat": {"solution": ["1", "1kg"],
                     "forbidden": ["2", "3", "4", "5", "sucre", "beurre"]}
    }


MESSAGES = Messages(path="configuration/minigames/find_the_recipe")


class Status(Enum):
    NEW = 0
    TENTATIVE = 1
    ANSWERED = 2


class FTRGameStatus(ChannelGameStatus):
    def __init__(self, channel):
        super().__init__(channel)
        self.members = {}
        self.statuses = {}
        self.count_bad_answers = 0

    def clear(self):
        super().clear()
        self.members.clear()
        master_role = self._data.get("master_role", RoleCollection.MASTER.value)
        self.members.update({member: 0 for member in self._channel.members if
                             not member.bot and not master_role.has_the_role(member)})
        self.statuses.clear()
        self.statuses.update({key: Status.NEW for key in self._data.get("solutions", [])})
        self.count_bad_answers = 0


class FindTheRecipe(TextChannelMiniGame):
    _default_messages = MESSAGES

    def __init__(self, **kwargs):
        self._next_minigame_class_d = MinigameCollection.get(kwargs.pop("next_minigame_class", None))
        self._next_channel_description = ChannelCollection.get(kwargs.pop("next_channel_description", "ATTIC1"))
        self._master_role_description = RoleCollection.get(kwargs.pop("master_role_description", "MASTER"))
        super().__init__(**kwargs)
        self._channels: ChannelGameStatuses = ChannelGameStatuses(FTRGameStatus)

    async def _init_channel(self, channel):
        self._channels[channel].set_data(solutions=self._messages["SOLUTIONS"],
                                         master_role=self._master_role_description)
        if not await super()._init_channel(channel):
            return False
        steps = "- " + "\n - ".join([f"{k}: {v['solution']}" for k, v in self._messages["SOLUTIONS"].items()])
        await self._master_channel_description.object_reference.send(self._messages["MASTER"].format(steps=steps))
        await channel.send(self._messages["INTRO"])
        members = self._channels[channel].members
        messages = self._messages["CLUE_MESSAGES"]
        if not self._simple_mode:
            messages += self._messages["USELESS_MESSAGES"]
        for i, member in enumerate(members):
            ind = i % len(messages)  # handle not enough clues: some members with the same clue
            # handle not enough members: multiple clues per number
            max_val = len(messages) // len(members) + (1 if (len(messages) % len(members) > ind) else 0)
            for k in range(max_val):
                message = messages[ind + k * len(members)]
                await send_dm_message(member, message)
        await asyncio.sleep(10)
        await channel.send(self._messages["INTRO_2"])
        return True

    def _check_victory(self, channel):
        for status in self._channels[channel].statuses.values():
            if status is not Status.ANSWERED:
                return False
        return True

    async def _on_channel_victory(self, channel):
        await channel.send(self._messages["VICTORY"])
        await start_next_minigame(channel, self._next_channel_description, self._next_minigame_class_d)

    async def _analyze_message(self, message):
        if not self._active or not self._channels[message.channel].active:
            if message.content == Emojis.fork_and_knife:
                return await self.start_channel(message.channel)
            return

        if message.content == Emojis.fork_and_knife:
            await message.channel.send(self._messages["REPEAT"])
            return

        if message.author.bot:
            return

        if not self._channels[message.channel].active:  # game already ended
            logger.debug(f"Game {self.__class__.__name__} already ended")
            return

        for key, solution in self._messages["SOLUTIONS"].items():
            # check the presence of the key
            if not check_answer(message.content, possible_answers=[key]):
                continue
            # check the presence of the solution
            possible_answers = solution["solution"]
            forbidden_answers = solution.get("forbidden", None)

            if check_answer(message.content, possible_answers=possible_answers, forbidden_answers=forbidden_answers):
                if self._channels[message.channel].statuses[key] is Status.ANSWERED:
                    await message.channel.send(random.choice(GeneralMessages["ALREADY_SAID"]))
                    break
                self._channels[message.channel].statuses[key] = Status.ANSWERED
                await message.channel.send(random.choice(GeneralMessages["GOOD_ANSWERS"]))
                break
            else:
                if self._channels[message.channel].statuses[key] is not Status.ANSWERED:
                    self._channels[message.channel].statuses[key] = Status.TENTATIVE
                await message.channel.send(random.choice(GeneralMessages["BAD_ANSWERS"]))
                self._channels[message.channel].count_bad_answers += 1
                if self._channels[message.channel].count_bad_answers % 10 == 3:
                    await message.channel.send(self._messages["REPEAT"])
                break

        if self._check_victory(message.channel):
            await self.on_channel_victory(message.channel)
            logger.debug(f"Game {self.__class__.__name__} ended in channel {message.channel}")
