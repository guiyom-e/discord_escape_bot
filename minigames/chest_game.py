import asyncio
from collections import OrderedDict

import discord
from discord import File

from bot_management import GuildManager
from default_collections import RoleCollection, Emojis
from functions.text_analysis import check_answer
from game_models.abstract_channel_mini_game import ChannelGameStatus, ChannelGameStatuses, TextChannelMiniGame
from helpers.json_helpers import TranslationDict
from utils_listeners.role_by_reaction import RoleByReactionManager, RoleMenuOptions


class Messages(TranslationDict):
    INTRO = "You found the chest with a 5-letter-code. Write it here when found"
    INTRO_FILE = "files/chest_game/chest_closed.png"
    ERROR_MESSAGE = "No ! {code} is incorrect"
    FINAL_CODES = ["ABCDEF", "12345"]
    MULTIPLE_CODES_LINK = " or "
    VICTORY = "Chest open, what's inside ?"
    VICTORY_FILE = "files/chest_game/chest_open.png"
    FIRST_REACTION = "Nothing !?"
    COMMENT = "No, there are 4 items  = 4 roles = 4 rooms to explore"
    COMMENT_SIMPLE = "There is a key !"
    HELPED_VICTORY = "Ok, I help! The code was '{code}'"
    CHARACTER_1 = "🌻"
    CHARACTER_2 = "⚓"
    CHARACTER_3 = "🔍"
    CHARACTER_4 = "🔎"


MESSAGES = TranslationDict(path="configuration/minigames/chest_game")


class ChestGameChannelStatus(ChannelGameStatus):
    def __init__(self, channel):
        super().__init__(channel)
        self.success = False

    def clear(self):
        super().clear()
        self.success = False


class ChestGame(TextChannelMiniGame):
    _default_messages = MESSAGES

    def __init__(self, **kwargs):
        self._max_users_with_role = kwargs.pop("max_users_with_role", 2)
        self._max_number_of_reactions_per_user = kwargs.pop("max_number_of_reactions_per_user", 1)
        self._allow_role_change = kwargs.pop("allow_role_change", True)
        self._visitor_d = RoleCollection.get(kwargs.pop("visitor_d", "VISITOR"))
        self._characters_menu = OrderedDict([(k, [RoleCollection.get(v)]) for k, v in kwargs.pop(
            "characters_menu",
            OrderedDict([(Emojis.sunflower, "CHARACTER1"), (Emojis.anchor, "CHARACTER2"), (Emojis.mag, "CHARACTER"),
                         (Emojis.mag_right, "CHARACTER4")])
        ).items()])
        super().__init__(**kwargs)
        self._channels = ChannelGameStatuses(ChestGameChannelStatus)

    async def _init_channel(self, channel) -> bool:
        if not await super()._init_channel(channel):
            return False
        await channel.edit(sync_permissions=True)
        await self._master_channel_description.object_reference.send(
            self._messages["MASTER"].format(
                code=self._messages["MULTIPLE_CODES_LINK"].join(self._messages["FINAL_CODES"])))
        await channel.send(self._messages["INTRO"], file=File(self._messages["INTRO_FILE"]))
        return True

    async def _on_channel_helped_victory(self, channel):
        self._channels[channel].success = True
        await channel.send(self._messages["HELPED_VICTORY"].format(
            code=self._messages["MULTIPLE_CODES_LINK"].join(self._messages["FINAL_CODES"])))
        await self._on_channel_victory(channel)

    async def _on_channel_victory(self, channel):
        self._channels[channel].success = True
        await channel.send(self._messages["VICTORY"], file=File(self._messages["VICTORY_FILE"]))
        await channel.send(self._messages["FIRST_REACTION"])
        await asyncio.sleep(4)
        if self._simple_mode:
            await channel.send(self._messages["COMMENT_SIMPLE"])
        else:
            role_message = await channel.send(
                self._messages["COMMENT"].format(nb_roles_per_player=self._max_number_of_reactions_per_user,
                                                 nb_players_per_role=self._max_users_with_role))
            manager = RoleByReactionManager.get(self.guild)
            options = RoleMenuOptions(
                required_roles=[self._visitor_d],
                max_users_with_role=self._max_users_with_role * GuildManager().get_guild(self.guild).nb_teams,
                max_number_of_reactions_per_user=self._max_number_of_reactions_per_user,
                remove_role_on_reaction_removal=True,
                allow_role_change=self._allow_role_change,
            )
            await manager.add(role_message, menu=self._characters_menu, options=options)
        await asyncio.sleep(20)
        await channel.edit(send_messages=False)

    async def _analyze_message(self, message: discord.Message):
        if not self._active or not self._channels[message.channel].active:
            return

        if message.author.bot:
            return

        if check_answer(message.content, self._messages["FINAL_CODES"]):
            if not self._channels[message.channel].success:
                await self.on_channel_victory(message.channel)
            return
        elif len(message.content) in [len(code) for code in self._messages["FINAL_CODES"]]:
            await message.channel.send(self._messages["ERROR_MESSAGE"].format(code=message.content))
