import inspect
import logging
from asyncio import Queue, QueueFull

import discord
from discord import HTTPException, Forbidden, Message

from bot_management import GuildManager
from bot_management.listener_utils import (stop_listener, start_listener, game_board, admin_board, control_panel,
                                           show_listeners_list, reload_listener_messages, change_version)
from constants import BOT, DEBUG_MODE
from default_collections import RoleCollection, ChannelCollection, CharacterCollection
from game_models import CommandUtils, AbstractUtils
from game_models.admin_tools import (show_info, clean_channel, show_channels,
                                     show_roles, show_messages, delete_channel,
                                     fetch)
from helpers import (long_send, get_guild_info, format_member, TranslationDict)
from helpers.set_channels import delete_channels
from helpers.set_roles import delete_roles
from logger import logger
from models import CharacterDescription


def if_debug_mode(func):
    if DEBUG_MODE:
        return func
    return lambda *_, **__: None


class Messages(TranslationDict):
    pass


MESSAGES = Messages()


class DiscordHandler(logging.StreamHandler):
    """
    A handler class which allows the cursor to stay on
    one line for selected messages
    """

    def __init__(self, log_channel_description, maxsize=100, **kwargs):
        self._discord_channel_description = log_channel_description
        super().__init__(**kwargs)
        self._log_queue = Queue(maxsize=maxsize)
        self._log_handler_thread = None
        self._webhook = None

    @property
    def log_channel(self):
        return self._discord_channel_description.object_reference

    async def start_discord_handler(self, character_description: CharacterDescription):
        try:
            self._webhook = await character_description.get_instance(self.log_channel)
            if self._webhook is None:
                return False
            res = self._webhook.send('Starting log bot !', username=character_description.name)
            if inspect.isawaitable(res):
                # bad async webhook adapter!
                await res
                character_description.object_reference = None
                self._webhook = await character_description.get_instance(self.log_channel)
                res2 = self._webhook.send('Reloading log webhook (sync) !', username=character_description.name)
                if inspect.isawaitable(res2):
                    logger.error(f"Bad adapter for log webhook!")
        except (HTTPException, Forbidden) as err:
            logger.exception(err)
            self._webhook = None
            return False
        else:
            return True

    def emit(self, record):
        if not self._webhook:
            return
        try:
            msg = self.format(record)
            self._webhook.send(msg)
        except QueueFull as err:
            logger.warning(f"Too much errors to handle in Discord handler! This error won't be send Discord: {err}")
        except (discord.NotFound, discord.HTTPException, discord.Forbidden) as err:
            logger.debug(f"Discord error while logging ! Channel may not exist. Error: {err}")
            # logger.exception(err)
            return
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


async def add_discord_logging_handler(character_description):
    discord_handler = DiscordHandler(ChannelCollection.LOG.value)
    discord_handler.setLevel(logging.WARNING)
    formatter = logging.Formatter(u"**%(levelname)s** *[%(module)s %(funcName)s %(lineno)d]*: ```%(message)s```")
    discord_handler.setFormatter(formatter)
    if await discord_handler.start_discord_handler(character_description):
        logger.addHandler(discord_handler)
        logger.info("Discord logging handler added!")
    return discord_handler


# noinspection PyUnusedLocal
class DebugFunctions(CommandUtils, AbstractUtils):
    _default_messages = MESSAGES

    _default_allowed_roles = [RoleCollection.DEV]
    _method_to_commands = {
        "help": [("help", "aide"), "Help"],
        "change_logging_level": [("change_logging_level", "log_level"), "*Arguments:* DEBUG / INFO / WARNING / ERROR"],
        "info": [("info", "get_info", "getinfo"), "Get guild info"],
        "roles": [("roles",), "Show guild roles"],
        "channels": [("channels",), "Show guild channels"],
        "messages": [("messages",), "Show the last messages of text channels.\n"
                                    " - *Arguments:*\n"
                                    " o text channel mention(s) (if not set, the current channel is used).\n"
                                    " o number of messages to show (default is 10)."],
        "listeners": [("minigames", "listeners", "utils"), "Show all listeners (utils + mini-games)."],
        "game_board": [("board", "game_board"), "Show game board."],
        "admin_board": [("admin_board",), "Show administration board."],
        "control_panel": [("control_panel", "control_board", "control"), "Show control panel"],
        "delete_channel": [("delete_channel",), "Delete the channel you are in.\n*Arguments:* reason message"],
        "clean_channel": [("reset_channel", "clean_channel"),
                          "Remove messages of the channel you are in.\n"
                          "*Arguments:* [int] maximum number of messages to delete (default: 1000)."],
        "update": [("update",), "Update the guild (guild, roles, channels)."],
        "fetch": [("fetch",), "Fetch the guild, i.e. try to match existing roles/channels to expected ones."],
        "forced_update": [("forced-update", "force-update"), "Update the guild and delete not expected roles/channels"],
        "delete_all_roles": [("delete_all_roles",),
                             "Delete all roles lower than bot top role, in the guild. "
                             "**WARNING**: Not recommended as some administration roles may be deleted and "
                             "administration commands will become unavailable (unless the bot is removed and "
                             "invited again)! Do it only if you are the guild owner and you know what you are doing!"],
        "delete_all_channels": [("delete_all_channels",),
                                "Delete all channels in the guild. *WARNING*: Not recommended as the only way "
                                "to control the guild would be with commands!"],
        "reset_all_channels": [("reset_all_channels",),
                               "Delete all channels and update the guild. *WARNING*: The control board will not "
                               "show up automatically after restart. "
                               "The channel #log won't be usable unless you restart admin_tools"],
        "start_listener": [("start", "start_listener"), "Start a listener given its id as argument."],
        "stop_listener": [("stop", "stop_listener"),
                          "Stop a listener given its id as argument. *WARNING:* Do not stop admin tools "
                          "if you don't have another way to start it (control panel for example)!"],
        "kick_member": [("kick", "kick_member", "expulser"), "Kick a member given a role or member mention."],
        "kick_bot": [("kick_bot", "remove_bot", "expulser_bot"), "Ask the bot to leave the guild."],
        "reload_listener_messages": [("reload", "reload_json"),
                                     "Reload messages of the listener. JSON source files are reloaded.\n"
                                     " - *Arguments:*\n o [int] listener id\n"
                                     " o (Optional) list of version strings (item separated by a whitespace)\n"
                                     " o `--update` to update versions (instead of reloading completely)\n"
                                     " - *Example:* `reload 4 fr en special --update` will overload "
                                     "the versions `fr`, `en` and `special` of the listener #4"],
        "change_version": [("change_version",), "Change all versions of minigames and utils.\n"
                                                " - *Arguments:* (Optional) `--update`"],
        "set_verbose": [("verbose", "bavard"),
                        "Le bot donnera des informations de connexion (nouveau membre, bot déconnecté, etc.). "
                        "Inverse de 'quiet'."],
        "set_quiet": [("quiet", "discret"),
                      "Le bot ne donnera pas d'informations sur les connexions. Inverse de 'verbose'."],
        "eval": [("eval",), "*For debug mode only.*"],
        "exec": [("exec",), "*For debug mode only.*"],
        "raise_value_error": [("raise", "raise_value_error"), "*For debug mode only.*"]
    }

    def __init__(self, **kwargs):
        kwargs["prefix"] = kwargs.get("prefix", ">")
        self._log_webhook_description = CharacterCollection.get(kwargs.pop("log_webhook_description", "LOG"))
        self._events_channel_description = ChannelCollection.get(kwargs.pop("events_channel_description", "EVENTS"))
        super().__init__(**kwargs)
        self._logger_handler_added = False
        self._logging_handler = None

    async def _init(self):
        logger.debug("Bot connected - Admin tools activated!")
        channel = self._events_channel_description.object_reference
        if not self._logger_handler_added:
            self._logging_handler = await add_discord_logging_handler(self._log_webhook_description)
            self._logger_handler_added = True
        if not channel:
            logger.debug(f"{self._events_channel_description} channel doesn't exist")
            return True
        if self._verbose:
            await channel.purge(limit=1000)
            await long_send(channel, get_guild_info(BOT, channel.guild), quotes=True)
            # await long_send(channel, get_channels_info(GUILD))
            # await long_send(channel, get_roles_info(GUILD))
            # await long_send(channel, get_members_info(GUILD))
            await self.show_short_help(channel)
            # await long_send(channel, f"Mini-games allowed:\n{format_list(GUILD.minigames)}")
        return True

    async def stop(self) -> bool:
        if self._logger_handler_added:
            try:
                logger.removeHandler(self._logging_handler)
                self._logger_handler_added = False
            except Exception as err:
                logger.error(f"Failed to remove Discord logging handler: {err}")
        return await super().stop()

    async def on_ready(self):
        channel = self._events_channel_description.object_reference
        if not channel:
            return
        if self._verbose:
            await channel.send(f"Bot {BOT} ready!")

    async def on_connect(self):
        channel = self._events_channel_description.object_reference
        if not channel:
            return
        if self._verbose:
            await channel.send(f"Bot {BOT} connected!")

    async def on_disconnect(self):
        channel = self._events_channel_description.object_reference
        if not channel:
            return
        if self._verbose:
            await channel.send(f"Bot {BOT} disconnected!")

    @staticmethod
    async def info(message, args):
        return await show_info(message.channel)

    @staticmethod
    async def listeners(message, args):
        return await show_listeners_list(message.channel)

    @staticmethod
    async def game_board(message, args):
        return await game_board(message.channel)

    @staticmethod
    async def admin_board(message, args):
        return await admin_board(message.channel)

    @staticmethod
    async def control_panel(message: Message, args):
        return await control_panel(message.guild)

    async def change_logging_level(self, message, args):
        if args and args[0] in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            self._logging_handler.setLevel(getattr(logging, args[0]))
            await message.channel.send(f"Changed logging level to {args[0]}")

    @staticmethod
    async def channels(message, args):
        return await show_channels(message.channel)

    @staticmethod
    async def roles(message, args):
        return await show_roles(message)

    @staticmethod
    async def start_listener(message, args):
        return await start_listener(message, args)

    @staticmethod
    async def stop_listener(message, args):
        return await stop_listener(message, args)

    @staticmethod
    async def kick_member(message: Message, args):
        guild = message.guild
        member_mentioned = message.mentions
        roles_mentioned = message.role_mentions
        members_with_role = [member for role in roles_mentioned for member in role.members]
        members = member_mentioned + members_with_role
        kicked_members = []
        for member in members:
            try:
                await guild.kick(member, reason="Asked by an admin command.")
            except Forbidden as err:
                logger.warning(f"Impossible to kick member {member.mention} (Forbidden): {err}")
            except HTTPException as err:
                logger.warning(f"Impossible to kick member {member.mention}: {err}")
            else:
                kicked_members.append(format_member(member))
        await message.channel.send(f"These members were kicked:\n{kicked_members}")

    @staticmethod
    async def kick_bot(message, args):
        await message.guild.leave()
        logger.warning(f"Bot {message.guild.me.id} left the guild {message.guild}")

    @staticmethod
    async def reload_listener_messages(message, args):
        return await reload_listener_messages(message, args)

    @staticmethod
    async def change_version(message, args):
        if "--update" in args:
            args.remove("--update")
            clear = False
        else:
            clear = True
        versions = args or None
        return await change_version(message.channel, versions, clear)

    @if_debug_mode  # no arbitrary code execution in production mode
    async def eval(self, message, args, auto_delete=False):
        """Evaluation of arbitrary Python code !"""
        code = self._sep.join(args)
        try:
            logger.warning(f"Evaluating code: {code}")
            result = eval(code)
            if inspect.isawaitable(result):
                result = await result
            logger.debug(f"Result of code evaluation: {result}")
        except Exception as err:
            logger.exception(err)
        if auto_delete:
            await message.delete()

    @if_debug_mode
    async def exec(self, message, args):  # no arbitrary code execution in production mode
        """Execution of arbitrary Python code !"""
        code = self._sep.join(args)
        try:
            logger.warning(f"Executing code: {code}")
            exec(code)
        except Exception as err:
            logger.exception(err)

    @if_debug_mode
    async def raise_value_error(self, message, args):  # no arbitrary code execution in production mode
        """Raises a ValueError"""
        err = ValueError("Test error")
        await message.channel.send(f"Raising a value error: {err}")
        raise err

    @staticmethod
    async def messages(message, args):
        return await show_messages(message, args)

    @staticmethod
    async def delete_channel(message, args):
        return await delete_channel(message.channel, reason=f"asked by command {message.content}")

    @staticmethod
    async def clean_channel(message, args, limit=None):
        try:
            limit = int(args[0])
        except (ValueError, IndexError):
            limit = limit or 1000
        return await clean_channel(message.channel, limit)

    @staticmethod
    async def fetch(message, args):
        return await fetch(message.guild)

    @staticmethod
    async def update(message, args, force=False):
        return await GuildManager().update_guild(message.channel.guild, message.channel, force,
                                                 clear_references=True)

    @staticmethod
    async def forced_update(message, args):
        return await GuildManager().update_guild(message.channel.guild, message.channel,
                                                 force=True, clear_references=True)

    @staticmethod
    async def delete_all_channels(message, args):
        return await delete_channels(message.guild, reason=f"asked by command {message.content}")

    @staticmethod
    async def delete_all_roles(message, args):
        return await delete_roles(message.guild, reason=f"asked by command {message.content}")

    @staticmethod
    async def reset_all_channels(message, args):
        return await GuildManager().reset_all_channels(message.guild, origin_channel=message.channel)
