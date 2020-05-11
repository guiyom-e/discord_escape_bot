import inspect
from typing import Dict

import discord

from default_collections import CharacterCollection, RoleCollection
from game_models.abstract_channel_mini_game import ChannelGameStatus, ChannelGameStatuses, TextChannelMiniGame
from helpers import TranslationDict
from helpers.commands_helpers import find_channel_mentions_in_message
from logger import logger
from models import CharacterDescription, RoleDescription


class Messages(TranslationDict):
    INTRO = "Welcome!"
    VICTORY = "Game over!"


MESSAGES = Messages(path="configuration/minigames/story_telling")


class StoryTellingChannelStatus(ChannelGameStatus):
    def __init__(self, channel):
        super().__init__(channel)
        self.webhooks = {}

    def clear(self):
        super().clear()
        self.webhooks.clear()


class StoryTelling(TextChannelMiniGame):
    _default_messages = MESSAGES

    def __init__(self, **kwargs):
        self._prefix = kwargs.pop("prefix", ".")
        self._master_role_description = RoleCollection.get(kwargs.pop("master_role_description", "MASTER"))
        self._emoji_key = kwargs.pop("emoji_key", "👋")
        self._role_to_character_description_dict: Dict[RoleDescription, CharacterDescription] = {
            RoleCollection.get(role_key): CharacterCollection.get(character_key)
            for role_key, character_key in kwargs.pop(
                "role_to_character_description_dict", {"CHARACTER1": "CHARACTER1", "CHARACTER2": "CHARACTER2"}).items()}
        super().__init__(**kwargs)
        self._sep = " "
        self._channels = ChannelGameStatuses(StoryTellingChannelStatus)

    async def _init_channel(self, channel) -> bool:
        if not await super()._init_channel(channel):
            return False
        logger.debug(f"StoryTelling started for channel {channel}")
        return True

    #
    # async def _on_channel_victory(self, channel):
    #     await channel.send(self._messages["VICTORY"])

    async def _analyze_message(self, message: discord.Message):
        if message.author.bot:
            return

        channel = message.channel

        # Start channel with an emoji
        if self._master_role_description.has_the_role(message.author) and self._emoji_key in message.content:
            await self.start_channel(channel)
        if not self._simple_mode and (channel not in self._channels or not self._channels[channel].active):
            return
        if not message.content.startswith(self._prefix):
            return

        # get channels
        content = message.content[len(self._prefix):].strip()
        args = list(filter(None, content.split(self._sep)))
        target = find_channel_mentions_in_message(message, args, message_channel_if_not_found=True,
                                                  only_first_args=True)[0]
        msg = self._sep.join(args)
        if not msg:  # Cannot send an empty message
            return

        for role_descr, webhook_descr in self._role_to_character_description_dict.items():
            if role_descr.has_the_role(message.author):
                if channel == target:
                    try:
                        await message.delete()
                    except discord.NotFound:
                        pass
                webhook = await webhook_descr.get_instance(target)
                res = webhook.send(msg)
                if inspect.isawaitable(res):
                    await res
                break  # Play only one role at once
