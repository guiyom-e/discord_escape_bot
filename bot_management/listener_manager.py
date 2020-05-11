import asyncio
import random
from collections import defaultdict
from typing import Union, List, Set, Type, Dict, Tuple, Collection, Optional

import discord
from discord import (TextChannel, Reaction, Member, User, HTTPException, Forbidden, NotFound, Guild,
                     RawReactionActionEvent, ChannelType, Permissions)

from constants import WEBSITE
from default_collections import ChannelCollection, CategoryChannelCollection, RoleCollection
from default_collections.game_versions import VersionsEnum
from game_models import ChannelMiniGame, AbstractListener, AbstractMiniGame, AbstractUtils
from game_models.abstract_listener import reconstitute_reaction_and_user
from game_models.admin_tools import clean_channels
from helpers import format_channel, long_send, TranslationDict
from helpers.checks import check_channel_description, check_role_description
from helpers.invitations import create_invite, delete_invite
from logger import logger
from models import ChannelDescription, GuildWrapper
from models.types import ControlEmojiEnum

LOCK = asyncio.Lock()


############
# Messages #
############
class Messages(TranslationDict):
    HELP = "*Aide pour l'administrateur {dev} et les maîtres du jeu {master}*\n**Astuces**\n" \
           "- Pour refaire une action sur le tableau de contrôle, retirer sa réaction et réagir à nouveau.\n" \
           "- Les maîtres du jeu peuvent déplacer n'importe quel membre d'une chaîne vocal à une autre !\n" \
           "\n**Démarrage sur un nouveau serveur**\n" \
           "- S'assurer que le rôle automatique de Tintin est bien le premier rôle de la liste de rôles. " \
           "Cela se vérifie dans 'Paramètres du serveur/Rôles'. Déplacer Tintin tout en haut de la liste de rôles.\n" \
           "- Mettre à jour le serveur ({update}) et le nettoyer si besoin ({danger} then {clean}🧹)." \
           "- Démarrer le tableau de bord du jeu\n" \
           "- Démarrer les mini-jeux voulus dans l'ordre pré-établi. Certains jeux sont des jeux par salon." \
           "Pour ces jeux, il faut d'abord démarrer le jeu globalement et démarrer le jeu pour chaque chaîne voulue.\n" \
           "- Au démarrage des jeux, un mémo s'affiche le plus souvent dans la chaîne #memo !" \
           "- Ne pas oublier que la plupart des lancements de mini-jeux sont manuels !" \
           "- De même le contrôle de la musique est fait par un bot externe et doit être géré manuellement."
    CONTROL_BOARD_INTRO = "**==================== [version(s): {versions}] ====================**\n" \
                          "Bonjour et bienvenue cher maître du jeu ! Pour commencer, choisis une action !\n" \
                          "Tu peux d'abord mettre à jour le serveur en cliquant sur {update}," \
                          "puis vérifier que le serveur est bien configuré en cliquant sur {check}." \
                          "Si c'est le cas, démarrer le tableau de bord en cliquant sur {board}, sinon essayer " \
                          "{force_update} (supprimera les rôles et salons non présents dans le jeu)" \
                          "\nTu peux aussi nettoyer les salons de jeu ({clean}) " \
                          "avant de débuter."
    GAME_BOARD_INTRO = "Don't forget to get {master} role!\n**Board**\n{play} : add reaction = start\n" \
                       "{pause} : add reaction = suspend / remove reaction = unsuspend\n" \
                       "{stop} : add reaction = stop\n" \
                       "{finish} : ends the game and continue as if it was a victory\n" \
                       "{reset} : reset the channel mini-game\n" \
                       "{running} : running / " \
                       "{suspended} : suspended / " \
                       "{stopped} : stopped"
    DANGER_REQUIRED = "Danger emoji must be pressed to clean game channels!"
    CONTROL_BOARD_COMMANDS = "**==================== [version(s): {versions}] ====================**\n" \
                             "**Tableau de contrôle**\n" \
                             "{help} : Aide\n" \
                             "{admin_tool} : Afficher le contrôleur d'adminstration\n" \
                             "{update} : Mettre à jour le serveur (rôles, salons, serveur)\n" \
                             "{force_update} : Mettre à jour et supprimer les salons/rôles en trop\n" \
                             "{check} : Vérifier que le serveur est prêt\n" \
                             "{board} : Vérifier le serveur et ouvrir un nouveau tableau de bord.\n" \
                             "Si {danger} est appuyé, le tableau de bord s'ouvre, même si le serveur n'est pas prêt\n" \
                             "{clean} : Nettoyer ce salon pour ne garder que ce tableau de contrôle\n" \
                             "Si {danger} est appuyé, tous les salons de jeu du serveur sont nettoyés.\n" \
                             "{invite} : Créer un message d'invitation (30 personnes, validité 3h). " \
                             "Si {danger} appuyé, le lien d'invitation du site est mis à jour. " \
                             "{danger} + Réaction retirée = lien d'invitation supprimé du site\n" \
                             "{version} : Changer de version du jeu (Bêta). {danger} doit être appuyé\n" \
                             "{leave} : kick bot from guild, with {danger}"
    GUILD = "Serveur"
    CHANGE_VERSION = "For which version do you want to change ? After change, {force_update} highly recommended." \
                     "\n{versions}\n"
    VERSION_CHANGED = "Changed to {versions}. Now, update with {force_update}"


MESSAGES = Messages(path="configuration/game_manager")


#################
# Emoji classes #
#################

class ToDictClass:
    @classmethod
    def to_dict(cls):
        return {ele: getattr(cls, ele) for ele in dir(cls) if not ele.startswith("_")}


class ListenerActions(ToDictClass):
    play = "▶️"
    pause = "⏸"
    stop = "⏹️"


class ListenerGameActions(ToDictClass):
    finish = "🎉"
    reset = "🔄"
    simple = "👶"


class OptionalModes(ToDictClass):
    simple_mode = "🚼"


class ListenerStatus(ControlEmojiEnum):
    running = ("💚", "_play_reaction")
    suspended = ("💛", "_pause_reaction")
    stopped = ("❤️", "_stop_reaction")


class ControlBoardEnum(ControlEmojiEnum):
    help = "❓"
    danger = "⚠"
    admin_tool = "🕹️"
    update = "♻"
    force_update = "🆙"
    check = "✅"
    board = "🆕"
    clean = "🧹"
    # reset_hard = "🆘"
    invite = "📨"
    version = "🏳️"
    infinity = "♾"
    leave = "❌"


def get_emoji_dict():
    format_dict = ListenerActions.to_dict()
    format_dict.update(ControlBoardEnum.to_dict())
    format_dict.update(ListenerGameActions.to_dict())
    format_dict.update(ListenerStatus.to_dict())
    format_dict.update(OptionalModes.to_dict())
    return format_dict


####################
# Helper functions #
####################

async def get_safe_text_channel(guild: Guild, name_key="MEMO", create=True) -> Optional[TextChannel]:
    # If create: prefer create a new channel instead of joining an existing one.
    # First: check if a channel with the corresponding name_key is available
    channel_description: ChannelDescription = ChannelCollection.get(name_key, None)
    if channel_description and channel_description.channel_type is ChannelType.text:
        channel = channel_description.object_reference
        if channel and channel.guild.id == guild.id and channel.permissions_for(guild.me).send_messages:
            return channel
        elif create:  # If create, create a channel corresponding to the description
            if await channel_description.create_object(guild, raises_on_category_error=False):
                return channel_description.object_reference

    # If not found and not create, look for a random channel with send_messages rights
    if not create:
        for channel in [_channel for _channel in guild.channels if isinstance(_channel, TextChannel)]:
            if channel.permissions_for(guild.me).send_messages:
                return channel
        logger.warning("No safe channel with send_messages available!")
        return None

    # If create, create a channel with the name_key
    channel_description = ChannelDescription(name=name_key, channel_type=ChannelType.text)
    try:
        return await guild.create_text_channel(name=channel_description.name, reason="No existing channel")
    except Exception as err:
        logger.error(err)
        return None


def _check_bot_privileges(guild: Guild):
    highest_game_role_description = max(r.object_reference or guild.default_role for r in RoleCollection.to_list())
    highest_bot_role = guild.me.top_role
    if highest_bot_role >= highest_game_role_description:
        return []
    err = f"Highest bot role ({highest_bot_role}) must be higher than other game roles in hierarchy! " \
          f"At least one role with a higher position ({highest_game_role_description}) was found."
    logger.error(err)
    return [err]


def _check_guild(guild: Guild):
    """Check that the guild has a correct configuration. Some properties may not be tested."""
    logger.info("Checking game guild !")
    errors_bot_role = _check_bot_privileges(guild)
    if errors_bot_role:
        return errors_bot_role
    guild_channels = guild.channels
    errors = []
    for ch_descr in CategoryChannelCollection.to_list():
        check_channel_description(ch_descr, guild, guild_channels, errors,
                                  allowed_role_descriptions=RoleCollection.to_list())

    for ch_descr in ChannelCollection.to_list():
        check_channel_description(ch_descr, guild, guild_channels, errors,
                                  allowed_role_descriptions=RoleCollection.to_list())

    for r_descr in RoleCollection.to_list():
        check_role_description(r_descr, guild, errors)
    return errors


##################
# Helper classes #
##################
class ChannelListener(AbstractMiniGame):
    """Wrapper to add listener methods to a mini-game in a specific channel"""

    def __init__(self, listener, channel, **kwargs):
        super().__init__(**kwargs)
        self._listener: ChannelMiniGame = listener
        self._channel = channel

    @property
    def name(self):
        return f"{self._name} ({format_channel(self._channel, pretty=True)})"

    @property
    def channel(self):
        return self._channel

    @property
    def active(self):
        return self._listener.channels[self._channel].active

    @property
    def description(self):
        return f"[{self._channel.name} ({self._channel.category.name})] {self._listener.description}"

    def __repr__(self):
        return f"**[{self._channel.name} ({self._channel.category.name})]** *{self._listener.__class__.__name__}*"

    async def start(self) -> bool:
        return await self._listener.start_channel(self._channel)

    async def stop(self) -> bool:
        return await self._listener.stop_channel(self._channel)

    async def reset(self):
        return self._listener.channels[self._channel].reset()

    async def on_ready(self):
        if self._auto_start:
            await self._listener.start_channel(self._channel)

    async def on_victory(self, *args, **kwargs):
        return await self._listener.on_channel_victory(self._channel)

    async def on_helped_victory(self, *args, **kwargs):
        return await self._listener.on_channel_helped_victory(self._channel)


class ManagerListener(AbstractListener):
    """Listener linked to the ListenerManager. It must always listen to events."""

    def __init__(self, manager):
        self._manager = manager
        super().__init__()

    async def on_raw_reaction_add(self, payload: RawReactionActionEvent):
        # Avoid that a disconnection breaks on_reaction_remove
        reaction, user = await reconstitute_reaction_and_user(payload)
        return await self.reaction_add(reaction, user) if reaction else None

    async def on_raw_reaction_remove(self, payload: RawReactionActionEvent):
        # Avoid that a disconnection breaks on_reaction_remove
        reaction, user = await reconstitute_reaction_and_user(payload)
        return await self.reaction_remove(reaction, user) if reaction else None

    async def reaction_add(self, reaction: Reaction, user: Union[Member, User]):
        if user.bot:
            return
        if reaction.message.id in self._manager.control_boards:
            return await self._manager.handle_control_panel_commands_add(reaction, user)
        if reaction.message.id == self._manager.version_choice_message:
            return await self._manager.handle_version_choice(reaction, user)
        if reaction.message.id not in self._manager.listener_menus:
            return
        listener = self._manager.listener_menus[reaction.message.id]
        if reaction.emoji == ListenerActions.play:
            await listener.start()
            await self._manager.start_listener(listener)
        elif reaction.emoji == ListenerActions.pause:
            await self._manager.close_listener(listener)
        elif reaction.emoji == ListenerActions.stop:
            await listener.stop()
            await self._manager.close_listener(listener)
        elif reaction.emoji == ListenerGameActions.finish:
            await listener.on_helped_victory()
            await self._manager.update_listener(listener)
        elif reaction.emoji == ListenerGameActions.simple:
            listener.simple_mode = True
            await self._manager.update_listener(listener)
        elif reaction.emoji == ListenerGameActions.reset and isinstance(listener, ChannelListener):
            await listener.reset()
            await self._manager.update_listener(listener)

    async def reaction_remove(self, reaction: Reaction, user: Union[Member, User]):
        if user.bot:
            return
        if reaction.message.id in self._manager.control_boards:
            return await self._manager.handle_control_panel_commands_remove(reaction, user)
        if reaction.message.id not in self._manager.listener_menus:
            return
        listener = self._manager.listener_menus[reaction.message.id]
        if reaction.emoji == ListenerActions.pause and listener.active:
            await self._manager.start_listener(listener)
        elif reaction.emoji == ListenerGameActions.simple:
            listener.simple_mode = False
            await self._manager.update_listener(listener)

    async def on_ready(self):
        await self._manager.update_listeners()


######################
# Main manager class #
######################

class ListenerManager:
    """Class to manage all AbstractListener objects listening to Discord events"""

    def __init__(self, guild_manager: 'GuildManager', guild_wrapper: GuildWrapper):
        self._messages = MESSAGES
        self._all_listeners: List[AbstractListener] = []
        self._channel_listeners: Set[ChannelListener] = set()
        self._active_listeners: Set[AbstractListener] = set()
        self._listener_menus: Dict[int, AbstractListener] = {}
        self._listeners_to_menu_msg_ids: Dict[AbstractListener, List[Tuple[TextChannel, int]]] = defaultdict(list)
        self._control_boards: Dict[int, ControlBoardEnum] = {}
        self._self_listener = ManagerListener(self)
        self._version_choice_message_id = None
        self._guild_manager: 'GuildManager' = guild_manager  # GuildManager instance
        self._guild_wrapper: GuildWrapper = guild_wrapper  # GuildWrapper instance

    async def reload(self, versions=None, clear=True):
        return self._messages.load(versions=versions, clear=clear)

    async def self_start(self):
        await self._self_listener.start()

    @property
    def versions(self):
        return self._guild_wrapper.versions

    @property
    def all_listeners(self) -> List[AbstractListener]:
        return self._all_listeners

    @property
    def active_listeners(self) -> Set[AbstractListener]:
        return self._active_listeners | {self._self_listener}  # self_listener is always active.

    @property
    def listener_menus(self) -> Dict[int, AbstractListener]:
        return self._listener_menus

    @property
    def control_boards(self) -> Dict[int, ControlBoardEnum]:
        return self._control_boards

    #####################################
    # Game board / Listeners management #
    #####################################
    async def clear_listeners(self):
        await self.stop_listeners(self._all_listeners)
        self._all_listeners.clear()
        self._active_listeners.clear()

    async def add_listener(self, listener, start_if_active=True):
        listener.set_listener_manager(self)
        self._all_listeners.append(listener)
        if listener.auto_start:
            await listener.start()
        if start_if_active and listener.active:  # todo : avoid useless duplicate start
            await self.start_listener(listener)

    async def add_listeners(self, listeners, start_if_active=True):
        for listener in listeners:
            await self.add_listener(listener, start_if_active=start_if_active)

    async def remove_listener(self, listener):
        await self.stop_listener(listener)
        async with LOCK:
            if listener in self._all_listeners:
                self._all_listeners.remove(listener)

    async def remove_listeners(self, listeners):
        for listener in listeners:
            await self.remove_listener(listener)

    @staticmethod
    async def _pause_reaction(message):
        await message.clear_reaction(ListenerStatus.stopped.emoji)
        await message.clear_reaction(ListenerStatus.running.emoji)
        await message.add_reaction(ListenerStatus.suspended.emoji)

    @staticmethod
    async def _play_reaction(message):
        await message.clear_reaction(ListenerStatus.stopped.emoji)
        await message.clear_reaction(ListenerStatus.suspended.emoji)
        await message.add_reaction(ListenerStatus.running.emoji)

    @staticmethod
    async def _stop_reaction(message):
        await message.clear_reaction(ListenerStatus.suspended.emoji)
        await message.clear_reaction(ListenerStatus.running.emoji)
        await message.add_reaction(ListenerStatus.stopped.emoji)

    @staticmethod
    async def _change_simple_mode(message, simple_mode: bool):
        if simple_mode:
            await message.add_reaction(OptionalModes.simple_mode)
        else:
            await message.clear_reaction(OptionalModes.simple_mode)

    async def _change_reaction(self, listener, status: ListenerStatus):
        for channel, msg_id in self._listeners_to_menu_msg_ids[listener]:
            try:
                msg = await channel.fetch_message(msg_id)
            except (NotFound, Forbidden, HTTPException) as err:
                logger.debug(f"Message impossible to get: {err}")
                self._listeners_to_menu_msg_ids[listener].remove((channel, msg_id))
            else:
                await getattr(self, status.method)(msg)
                if isinstance(listener, AbstractMiniGame):
                    await self._change_simple_mode(msg, listener.simple_mode)

    async def start_listener(self, listener: AbstractListener):
        self._active_listeners.add(listener)
        logger.info(f"{listener.name} listening!")
        if listener.active:
            await self._change_reaction(listener, ListenerStatus.running)
        else:
            await self._change_reaction(listener, ListenerStatus.stopped)

    async def stop_listener(self, listener: AbstractListener):
        await listener.stop()
        await self.close_listener(listener)

    async def stop_listeners(self, listeners: Collection[AbstractListener]):
        for listener in listeners:
            await self.stop_listener(listener)

    async def close_listener(self, listener: AbstractListener):
        if listener in self._active_listeners:
            self._active_listeners.remove(listener)
            logger.info(f"{listener.name} no more listening!")
        if listener.active:
            await self._change_reaction(listener, ListenerStatus.suspended)
        else:
            await self._change_reaction(listener, ListenerStatus.stopped)

    async def update_listener(self, listener):
        if listener in self._active_listeners | self._channel_listeners and listener.active:
            await self._change_reaction(listener, ListenerStatus.running)
        elif not listener.active:
            await self._change_reaction(listener, ListenerStatus.stopped)
        else:
            await self._change_reaction(listener, ListenerStatus.suspended)

    async def update_listeners(self):
        for listener in self._all_listeners + list(self._channel_listeners):
            await self.update_listener(listener)

    async def _show_channel_listener(self, listener, origin_channel):
        if not isinstance(listener, ChannelMiniGame):
            logger.error(f"Listener {listener} is not a ChannelMiniGame!")
            return
        for listener_channel in listener.channels_list:
            message = await origin_channel.send(f"{format_channel(listener_channel, pretty=True)}")
            channel_listener = ChannelListener(listener, listener_channel)
            self._channel_listeners.add(channel_listener)
            self._listener_menus.update({message.id: channel_listener})
            self._listeners_to_menu_msg_ids[channel_listener].append((origin_channel, message.id))
            await message.add_reaction(ListenerActions.play)
            # await message.add_reaction(ListenerActions.pause)  # pause not supported
            await message.add_reaction(ListenerActions.stop)
            await message.add_reaction(ListenerGameActions.finish)
            await message.add_reaction(ListenerGameActions.reset)

    async def show_listeners(self, channel: TextChannel, base_class: Type[AbstractListener] = AbstractListener):
        if self._all_listeners and issubclass(base_class, AbstractMiniGame):
            format_dict = get_emoji_dict()
            format_dict.update({"master": getattr(RoleCollection.MASTER.object_reference, "mention", "MASTER")})
            await channel.send(self._messages["GAME_BOARD_INTRO"].format(**format_dict))
            # await channel.send(embed=discord.Embed(
            #     description=self._messages["GAME_BOARD_INTRO"].format(**format_dict)))

        for listener in self._all_listeners:
            if not listener.show_in_listener_manager or not isinstance(listener, base_class):
                continue
            # message = await channel.send(f"---------------\n**[{listener.name}]** {listener.description}")
            embed = discord.Embed(description=listener.description)
            message = await channel.send(content=f"---------------\n**[{listener.name}]**", embed=embed)
            self._listener_menus.update({message.id: listener})
            self._listeners_to_menu_msg_ids[listener].append((channel, message.id))
            await message.add_reaction(ListenerActions.play)
            await message.add_reaction(ListenerActions.pause)
            await message.add_reaction(ListenerActions.stop)
            if isinstance(listener, AbstractMiniGame):
                await message.add_reaction(ListenerGameActions.finish)
                if listener.simple_mode is not None:
                    await message.add_reaction(ListenerGameActions.simple)
            if isinstance(listener, ChannelMiniGame):
                await self._show_channel_listener(listener, origin_channel=channel)
        await self.update_listeners()

    #################
    # Control Panel #
    #################
    async def show_control_panel(self, guild: Guild, channel: TextChannel = None):
        if channel is None or channel not in guild.channels or not isinstance(channel, TextChannel):
            channel = await get_safe_text_channel(guild, "BOARD", create=True)
        format_dict = ControlBoardEnum.to_dict()
        format_dict.update({"versions": ", ".join(self.versions)})
        # await channel.send(self._messages["CONTROL_BOARD_INTRO"].format(**format_dict))
        # await channel.send(embed=discord.Embed(
        #     description=self._messages["CONTROL_BOARD_INTRO"].format(**format_dict)))
        message = await channel.send(
            content=self._messages["CONTROL_BOARD_COMMANDS"].format(**format_dict),
            embed=discord.Embed(description=self._messages["CONTROL_BOARD_INTRO"].format(**format_dict))
        )
        # message = await channel.send(embed=discord.Embed(
        #     description=self._messages["CONTROL_BOARD_COMMANDS"].format(**format_dict)))
        self._control_boards.update({message.id: ControlBoardEnum.infinity})
        for reaction in list(ControlBoardEnum):
            await message.add_reaction(reaction.emoji)

    async def check_guild(self, channel):
        result = _check_guild(channel.guild)
        if result:
            format_result = ' * ' + '\n * '.join(result)
            await long_send(channel, f"**{self._messages['GUILD']} NOT OK 📛**\n{format_result}",
                            quotes=False, embed=True)
            return False
        await long_send(channel, f"**{self._messages['GUILD']} OK ✅**", quotes=False, embed=True)
        return True

    async def reset_guild(self, message):
        logger.critical("Resetting game guild !")
        await self._guild_manager.reset_all_channels(message)
        channel = await get_safe_text_channel(guild=message.guild, name_key="BOARD")
        await self.show_control_panel(message.guild, channel)
        logger.info("Game guild reset !")

    @staticmethod
    async def _is_danger_pressed(reaction, user):
        for _r in reaction.message.reactions:
            _users = await _r.users().flatten()
            if user in _users and _r.emoji == ControlBoardEnum.danger.emoji:
                try:
                    await _r.remove(user)
                except (HTTPException, NotFound) as _err:
                    logger.debug(_err)
                return True
        return False

    @staticmethod
    async def _grant_dev_role_if_not_set(user: Member, channel: TextChannel = None):
        if getattr(RoleCollection.DEV, "object_reference", None):
            if not RoleCollection.DEV.object_reference.members:
                try:
                    await user.edit(roles=user.roles + [RoleCollection.DEV.object_reference])
                    if channel:
                        await long_send(channel, "💪", embed=True)
                except Exception as err:
                    logger.error(f"Impossible to edit role of user {user}: {err}")
                    return False
                else:
                    return True
        return False

    async def handle_control_panel_commands_add(self, reaction: Reaction, user: Union[Member, User]):
        assert reaction.message.id in self._control_boards
        if reaction.emoji == ControlBoardEnum.help.emoji:
            format_dict = get_emoji_dict()
            format_dict.update({"auth_url": discord.utils.oauth_url(reaction.message.guild.me.id,
                                                                    permissions=Permissions(8)),
                                "website": WEBSITE})
            try:
                format_dict.update({"dev": RoleCollection.DEV.object_reference.mention,
                                    "master": RoleCollection.MASTER.object_reference.mention,
                                    "logs": ChannelCollection.LOG.object_reference.mention,
                                    "memo": ChannelCollection.MEMO.object_reference.mention,
                                    "music": ChannelCollection.MUSIC.object_reference.mention,
                                    "commandes": ChannelCollection.COMMANDS.object_reference.mention,
                                    "commandes_dev": ChannelCollection.EVENTS.object_reference.mention
                                    })
            except AttributeError as err:
                logger.info(f"Object references of channels and roles are not set: {err}")
                format_dict.update({"dev": "", "master": "", "logs": "LOG",
                                    "memo": "MEMO", "music": "MUSIC",
                                    "commandes": "COMMANDES", "commandes_dev": "COMMANDES-DEV"
                                    })
            await long_send(reaction.message.channel, self._messages["HELP"].format(**format_dict), quotes=False)
        elif reaction.emoji == ControlBoardEnum.admin_tool.emoji:
            await self.show_listeners(reaction.message.channel, AbstractUtils)
        elif reaction.emoji == ControlBoardEnum.update.emoji:
            await self._grant_dev_role_if_not_set(user, reaction.message.channel)
            await self._guild_manager.update_guild(reaction.message.channel.guild, reaction.message.channel,
                                                   force=False, clear_references=False)
            await self._grant_dev_role_if_not_set(user, reaction.message.channel)
        elif reaction.emoji == ControlBoardEnum.force_update.emoji:
            await self._grant_dev_role_if_not_set(user, reaction.message.channel)
            await self._guild_manager.update_guild(reaction.message.channel.guild, reaction.message.channel,
                                                   force=True, clear_references=True)
            await self._grant_dev_role_if_not_set(user, reaction.message.channel)
        elif reaction.emoji == ControlBoardEnum.check.emoji:
            await self.check_guild(reaction.message.channel)
        elif reaction.emoji == ControlBoardEnum.board.emoji:
            if await self.check_guild(reaction.message.channel) or await self._is_danger_pressed(reaction, user):
                await self.show_listeners(reaction.message.channel, AbstractMiniGame)
        elif reaction.emoji == ControlBoardEnum.clean.emoji:
            channel = reaction.message.channel
            if await self._is_danger_pressed(reaction, user):
                await clean_channels(reaction.message.guild.channels,
                                     ignore=[CategoryChannelCollection.MASTER.value,
                                             CategoryChannelCollection.DEV.value],
                                     force=[ChannelCollection.BOARD.value])
            else:
                await long_send(channel, self._messages["DANGER_REQUIRED"].format(**get_emoji_dict()),
                                embed=True)
                return
                # await clean_channel(reaction.message.channel)
            await self.show_control_panel(channel.guild)
        # elif reaction.emoji == ControlBoardEnum.reset_hard.emoji:
        #     if await self._is_danger_pressed(reaction, user):
        #         return await self.reset_guild(reaction.message)
        #     await reaction.message.channel.send(self._messages["DANGER_REQUIRED"].format(** get_emoji_dict()))
        elif reaction.emoji == ControlBoardEnum.invite.emoji:
            if await self._is_danger_pressed(reaction, user):
                post_on_website = True
            else:
                post_on_website = False
            return await create_invite(channel=ChannelCollection.WELCOME.value.object_reference,
                                       origin_channel=reaction.message.channel,
                                       **{"max_uses": 30, "max_age": 10800, "website": post_on_website})
        elif reaction.emoji == ControlBoardEnum.version.emoji:
            if await self._is_danger_pressed(reaction, user):
                channel = reaction.message.channel
                await self._change_version_dialog(channel)
        elif reaction.emoji == ControlBoardEnum.infinity.emoji:
            if not await self._grant_dev_role_if_not_set(user, reaction.message.channel):
                return await reaction.message.channel.send(random.choice("🦓🙈🦄🐛"))
        elif reaction.emoji == ControlBoardEnum.leave.emoji:
            if await self._is_danger_pressed(reaction, user) and RoleCollection.DEV.has_the_role(user):
                await long_send(reaction.message.channel, "Bot is leaving the server!", embed=True)
                await delete_invite(origin_channel=reaction.message.channel)
                await reaction.message.guild.leave()
            else:
                await long_send(reaction.message.channel, self._messages["DANGER_REQUIRED"].format(**get_emoji_dict()),
                                embed=True)

    async def handle_control_panel_commands_remove(self, reaction: Reaction, user: Union[Member, User]):
        assert reaction.message.id in self._control_boards
        if reaction.emoji == ControlBoardEnum.invite.emoji:
            if await self._is_danger_pressed(reaction, user):
                return await delete_invite(origin_channel=reaction.message.channel)
        return

    ##################
    # Version choice #
    ##################

    async def _change_version_dialog(self, channel):
        format_dict = ControlBoardEnum.to_dict()
        format_dict.update({"versions": VersionsEnum.to_str()})
        message = await long_send(channel, self._messages["CHANGE_VERSION"].format(**format_dict), embed=True)
        for version_descr in VersionsEnum.to_list():
            await message.add_reaction(version_descr.emoji)
        self._version_choice_message_id = message.id
        await message.delete(delay=120)  # deleted after 2 minutes

    @property
    def version_choice_message(self):
        return self._version_choice_message_id

    async def handle_version_choice(self, reaction, user):
        self._version_choice_message_id = None
        versions_dict = VersionsEnum.to_emoji_dict()
        if reaction.emoji in versions_dict:
            new_version_descr = versions_dict[reaction.emoji]
            await self._guild_manager.change_guild_version(reaction.message.guild, new_version_descr.versions,
                                                           origin_channel=reaction.message.channel)
            format_dict = ControlBoardEnum.to_dict()
            format_dict.update({"versions": new_version_descr.name})
            await long_send(reaction.message.channel, self._messages["VERSION_CHANGED"].format(**format_dict),
                            embed=True)
