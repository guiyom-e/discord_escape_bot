from discord import PermissionOverwrite

from default_collections import RoleCollection, ChannelCollection
from game_models import CommandUtils, AbstractMiniGame
from helpers import (TranslationDict)
from logger import logger


class Messages(TranslationDict):
    INTRO = "Cette chaîne est dédiée au contrôle de la veillée par commandes simples " \
            "(changement de nom de chaînes, changement de permissions, etc.)"


MESSAGES = Messages()


class IslandTools(CommandUtils, AbstractMiniGame):
    _default_messages = MESSAGES

    _default_allowed_roles = [RoleCollection.DEV, RoleCollection.MASTER]
    _method_to_commands = {
        "help": [("help", "aide"), "Obtenir de l'aide sur les commandes"],
        "cacher_embarquement": [("step1", "cacher_embarquement"), "La chaîne d'embarquement n'est plus visible"],
        "bateau_en_plage": [("step2", "bateau_en_plage"), "Renommer le bateau en plage"],
        "plage_en_jungle": [("step3", "plage_en_jungle"), "Renommer la plage en jungle"],
        "coins_de_plage": [("step4", "coins_de_plage"), "Faire apparaître les coins de plage"],
        "plage_commune": [("step5", "coins_de_plage"), "Faire apparaître la plage commune"],
    }

    def __init__(self, **kwargs):
        self._memo_channel_description = ChannelCollection.get(kwargs.pop("memo_channel_description", "MEMO"))
        super().__init__(**kwargs)
        self._simple_mode = None

    async def _init(self):
        channel = self._memo_channel_description.object_reference
        if not channel:
            logger.debug(f"{self._memo_channel_description} channel doesn't exist")
            return True
        await channel.purge(limit=1000)
        await channel.send(self._messages["INTRO"])
        await self.show_help(channel)
        return True

    async def cacher_embarquement(self, message, args):
        channels = [ChannelCollection.get("WELCOME").object_reference,
                    ChannelCollection.get("SUPPORT_VOICE").object_reference]
        for channel in channels:
            await channel.edit(
                overwrites={RoleCollection.get("DEFAULT").object_reference: PermissionOverwrite(view_channel=False)})
        await self._memo_channel_description.object_reference.send(f"OK step {message.content}")

    async def bateau_en_plage(self, message, args):
        channels = [ChannelCollection.get("BOAT1").object_reference,
                    ChannelCollection.get("BOAT2").object_reference,
                    ChannelCollection.get("BOAT_VOICE1").object_reference,
                    ChannelCollection.get("BOAT_VOICE2").object_reference
                    ]
        for channel in channels:
            await channel.edit(name="La plage")
        await self._memo_channel_description.object_reference.send(f"OK step {message.content}")

    async def plage_en_jungle(self, message, args):
        channels = [ChannelCollection.get("BOAT1").object_reference,
                    ChannelCollection.get("BOAT2").object_reference,
                    ChannelCollection.get("BOAT_VOICE1").object_reference,
                    ChannelCollection.get("BOAT_VOICE2").object_reference
                    ]
        for channel in channels:
            await channel.edit(name="La jungle")
        await self._memo_channel_description.object_reference.send(f"OK step {message.content}")

    async def coins_de_plage(self, message, args):
        strings = [f"ROOM{i}{j}" for i in (1, 2) for j in (1, 2, 3, 4, 5, 6)]
        channels = [ChannelCollection.get(string).object_reference
                    for string in strings]
        for channel in channels:
            await channel.edit(sync_permissions=True)
        await self._memo_channel_description.object_reference.send(f"OK step {message.content}")

    async def plage_commune(self, message, args):
        channels = [ChannelCollection.get("MAIN_ROOM").object_reference,
                    ChannelCollection.get("MAIN_ROOM_VOICE").object_reference]
        for channel in channels:
            await channel.edit(
                overwrites={RoleCollection.get("DEFAULT").object_reference: PermissionOverwrite(view_channel=True)})
        await self._memo_channel_description.object_reference.send(f"OK step {message.content}")
