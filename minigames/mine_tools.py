from default_collections import RoleCollection, ChannelCollection
from game_models import CommandUtils, AbstractMiniGame
from helpers import (TranslationDict, long_send)
from logger import logger
from utils_listeners import RoleByReactionManager, RoleMenuOptions, MusicTools


class Messages(TranslationDict):
    INTRO = "Commandes de contrôle du jeu initialisées ! Pur utiliser les commandes, " \
            "se référer à l'aide disponible via {prefix}help"
    INIT_ROLEMENU = "Lorsque vous êtes prêt à entrer dans la mine, prenez votre pioche en cliquant sur :pick:"
    ROLE_MENU_EMOJI = "⛏"
    JINGLES = ""


MESSAGES = Messages("configuration/minigames/mine_messages/")


class MineTools(CommandUtils, AbstractMiniGame):
    _default_messages = MESSAGES

    _default_allowed_roles = [RoleCollection.DEV, RoleCollection.MASTER]
    _method_to_commands = {
        "help": [("help", "aide"), "Obtenir de l'aide sur les commandes"],
        "create_init_rolemenu": [("menu_intro", "init_rolemenu",),
                                 "Créer le menu d'introduction pour que les joueurs acquierrent le rôle Mineur"],
        "create_default_jingle_palette": [("musique", "ambiance", "default_palette"),
                                          "Créer la palette de musiques et sons d'ambiance par défaut"]
    }

    def __init__(self, **kwargs):
        self._commands_channel_description = ChannelCollection.get(
            kwargs.pop("commands_channel_description", "COMMANDS"))
        self._init_channel_description = ChannelCollection.get(kwargs.pop("init_channel_description", "WELCOME"))
        self._visitor_role_description = RoleCollection.get(kwargs.pop("visitor_role_description", "VISITOR"))
        super().__init__(**kwargs)
        self._simple_mode = None

    async def _init(self):
        channel = self._commands_channel_description.object_reference
        if not channel:
            logger.debug(f"{self._commands_channel_description} channel doesn't exist")
            return True
        await channel.send(self._messages["INTRO"].format(prefix=self._prefix))
        await self.show_help(channel)
        return True

    async def create_init_rolemenu(self, messages, args):
        message = await self._init_channel_description.object_reference.send(self._messages["INIT_ROLEMENU"])
        await RoleByReactionManager.get(self.guild).add(
            message,
            menu={self._messages["ROLE_MENU_EMOJI"]: [self._visitor_role_description]},
            options=RoleMenuOptions(remove_role_on_reaction_removal=False))

    async def create_default_jingle_palette(self, message, args):
        music_msg = await long_send(self._music_channel_description.object_reference, self._messages["JINGLES"])
        await MusicTools.jingle_palette_from_message(music_msg)
