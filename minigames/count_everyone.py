from typing import List, Optional

from discord import Message, TextChannel

from default_collections import Emojis, ChannelCollection, RoleCollection, MinigameCollection
from game_models import ChannelGameStatus, ChannelGameStatuses
from game_models.abstract_channel_mini_game import TextChannelMiniGame
from helpers import TranslationDict, format_channel
from bot_management.listener_utils import start_next_minigame
from logger import logger
from models import RoleDescription


class Messages(TranslationDict):
    START = "Comptez-vous !"
    MASTER = "Started in {channel}"
    NOT_A_NUMBER = "Tu sais comptez {user_mention} ??"
    IN_ORDER = "Dans l'ordre {user_mention} !"
    TOO_MUCH = "Tu ne comptes pas double tu sais {user_mention} !"
    VICTORY = "Bravo ! Vous êtes la {rank}e équipe sur {nb_channels} à avoir réussi à vous compter !"


MESSAGES = Messages(path="configuration/minigames/count_everyone")


def filter_members(members, forbidden_role_descriptions: List[RoleDescription],
                   allowed_role_descriptions: Optional[List[RoleDescription]] = None, no_bot=True):
    return [member for member in members
            if (not no_bot or not member.bot)
            and not any([role_descr.has_the_role(member) for role_descr in forbidden_role_descriptions])
            and (not allowed_role_descriptions
                 or any([role_descr.has_the_role(member) for role_descr in allowed_role_descriptions]))
            ]


class CountEveryoneChannelStatus(ChannelGameStatus):
    def __init__(self, channel):
        super().__init__(channel)
        self.members = {}
        self.counter = 1
        self.started_once = False
        self.success = False  # not reset by clear

    def clear(self):
        super().clear()
        self.members.clear()
        self.members.update(
            {member: 0 for member in filter_members(self._channel.members,
                                                    forbidden_role_descriptions=self._data.get("ignored_role_d", []),
                                                    allowed_role_descriptions=self._data.get("allowed_role_d", []))})
        self.counter = 1

    def reset(self):
        super().reset()
        self.started_once = False
        self.success = False

    @property
    def members_count(self):  # computed live
        return len(filter_members(self._channel.members,
                                  forbidden_role_descriptions=self._data.get("ignored_role_d", []),
                                  allowed_role_descriptions=self._data.get("allowed_role_d", [])))


class CountEveryone(TextChannelMiniGame):
    _default_messages = MESSAGES

    def __init__(self, **kwargs):
        self._next_minigame_class_d = MinigameCollection.get(kwargs.pop("next_minigame_class", "KITCHEN"))
        self._next_channel_description = ChannelCollection.get(kwargs.pop("next_channel_description", "KITCHEN1"))
        self._ignored_role_descriptions = [RoleCollection.get(item)
                                           for item in kwargs.pop("ignored_role_descriptions", ["MASTER"])]
        self._allowed_role_descriptions = [RoleCollection.get(item)
                                           for item in kwargs.pop("allowed_role_descriptions", ["VISITOR"])]
        super().__init__(**kwargs)
        self._channels = ChannelGameStatuses(CountEveryoneChannelStatus)

    async def _init_channel(self, channel) -> bool:
        if not isinstance(channel, TextChannel):
            logger.warning(f"Channel {channel} is not a text channel")
            return False
        self._channels[channel].set_data(ignored_role_d=self._ignored_role_descriptions,
                                         allowed_role_d=self._allowed_role_descriptions)
        if not await super()._init_channel(channel):
            return False
        await self._master_channel_description.object_reference.send(
            self._messages["MASTER"].format(channel=format_channel(channel, pretty=True)))
        await channel.send(self._messages["START"])
        self._channels[channel].started_once = True
        return True

    def reset_counter(self, channel):
        if not self._simple_mode:
            self.reset_channel_stats(channel)
        self._channels[channel].active = True

    async def _on_channel_victory(self, channel):
        self._channels[channel].success = True
        already_ended = sum(int(game_status.success) for game_status in self._channels.values())
        nb_channels_in_game = sum(int(game_status.started_once) for game_status in self._channels.values())
        await channel.send(self._messages["VICTORY"].format(rank=already_ended, nb_channels=nb_channels_in_game))
        if already_ended == len(self._channels):
            logger.debug("All games ended")
        logger.debug(f"Starting next minigame {self._next_minigame_class_d} "
                     f"in channel {self._next_channel_description}...")
        await start_next_minigame(channel, self._next_channel_description, self._next_minigame_class_d)
        logger.debug(f"Channel victory ended for game {self.__class__.__name__} in channel {channel}.")

    async def _analyze_message(self, message: Message):
        if not self._active or not self._channels[message.channel].active:
            if message.content == Emojis.thumbsup:
                return await self.start_channel(message.channel)
            return

        if message.author.bot:
            return

        if not self._channels[message.channel].active:  # game already ended
            logger.debug("Game already ended")
            return

        # Check roles
        for role_description in self._ignored_role_descriptions:
            if role_description.has_the_role(message.author):
                return

        member_allowed = True
        if self._allowed_role_descriptions:
            member_allowed = False
            for role_description in self._allowed_role_descriptions:
                if role_description.has_the_role(message.author):
                    member_allowed = True
                    break
        if not member_allowed:
            return

        try:
            number = int(message.content)
        except ValueError:
            await message.channel.send(self._messages["NOT_A_NUMBER"].format(user_mention=message.author.mention))
            await message.add_reaction(Emojis.tired_face)
            self.reset_counter(message.channel)
            return

        if number != self._channels[message.channel].counter:
            await message.channel.send(self._messages["IN_ORDER"].format(user_mention=message.author.mention))
            self.reset_counter(message.channel)
            return

        if message.author not in self._channels[message.channel].members:
            return  # TODO: custom message ? Handle this ?
        if self._channels[message.channel].members[message.author] > 0:
            await message.channel.send(self._messages["TOO_MUCH"].format(user_mention=message.author.mention))
            self.reset_counter(message.channel)
            return

        self._channels[message.channel].counter += 1
        self._channels[message.channel].members[message.author] += 1

        if self._channels[message.channel].counter - 1 >= self._channels[message.channel].members_count:
            # victory
            await self.on_channel_victory(message.channel)
