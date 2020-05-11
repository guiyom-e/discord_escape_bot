import asyncio

from discord import TextChannel, ChannelType, File, HTTPException, NotFound

from default_collections import ChannelCollection, RoleCollection
from game_models import AbstractMiniGame
from helpers import (TranslationDict, long_send)
from logger import logger
from utils_listeners import RoleByReactionManager, MusicTools, RoleMenuOptions


class Messages(TranslationDict):
    MASTER = "Master"
    MASTER_FILE = ""
    INITIAL_MESSAGES = {"WELCOME": {"WELCOME-0": "Welcome!"}}
    JINGLES = ""
    INIT_ROLEMENU = "Lorsque vous êtes prêt à entrer dans la mine, prenez votre pioche en cliquant sur :pick:"
    ROLE_MENU_EMOJI = "⛏"


MESSAGES = Messages(path="configuration/minigames/mine_messages/")


class MineMessages(AbstractMiniGame):
    _default_messages = MESSAGES

    def __init__(self, **kwargs):
        description_names = kwargs.pop("channel_descriptions", None)
        self._channel_descriptions = ChannelCollection.to_list() if description_names is None \
            else [ChannelCollection.get(name) for name in description_names]
        self._init_channel_description = ChannelCollection.get(kwargs.pop("init_channel_description", "WELCOME"))
        self._visitor_role_description = RoleCollection.get(kwargs.pop("visitor_role_description", "VISITOR"))
        super().__init__(**kwargs)

    async def create_init_rolemenu(self):
        message = await self._init_channel_description.object_reference.send(self._messages["INIT_ROLEMENU"])
        await RoleByReactionManager.get(self.guild).add(
            message,
            menu={self._messages["ROLE_MENU_EMOJI"]: [self._visitor_role_description]},
            options=RoleMenuOptions(remove_role_on_reaction_removal=False))

    async def create_default_jingle_palette(self):
        music_msg = await long_send(self._music_channel_description.object_reference, self._messages["JINGLES"])
        await MusicTools.jingle_palette_from_message(music_msg)

    async def _init(self):
        master_channel: TextChannel = self._master_channel_description.object_reference
        try:
            await long_send(master_channel, self._messages["MASTER"])
            await master_channel.send(file=File(self._messages["MASTER_FILE"]))
        except (HTTPException, NotFound, FileNotFoundError) as err:
            logger.error(f"Cannot send master infos: {err}")
        init_messages = self._messages.get("INITIAL_MESSAGES", {})
        for channel_key, messages_dict in init_messages.items():
            for channel_descr in self._channel_descriptions:
                if channel_descr.channel_type is ChannelType.text and channel_descr.key.startswith(channel_key):
                    if self._simple_mode:
                        try:
                            await channel_descr.object_reference.purge(limit=1000)
                        except (HTTPException, NotFound, AttributeError, FileNotFoundError) as err:
                            logger.warning(f"Cannot purge channel before sending messages: {err}")
                    for key, message_value in messages_dict.items():
                        if "FILE" in key:
                            try:
                                await channel_descr.object_reference.send(file=File(message_value))
                            except (HTTPException, NotFound, AttributeError, FileNotFoundError) as err:
                                logger.error(f"Cannot send game file: {err}")
                        else:
                            try:
                                await channel_descr.object_reference.send(content=message_value)
                            except (HTTPException, NotFound, AttributeError, FileNotFoundError) as err:
                                logger.error(f"Cannot send game message: {err}")
            await asyncio.sleep(0.1)  # wait to avoid Discord errors due to lots of messages
        await self.create_init_rolemenu()
        await self.create_default_jingle_palette()
        logger.info("Mine init OK")
        return True

    async def on_message(self, message):
        if self.active:  # end the listener whenever a message is sent.
            await self.on_victory()
