from typing import Dict, Iterable, Tuple

from discord import Forbidden, NotFound, HTTPException, TextChannel

from constants import VERBOSE
from game_models.abstract_filtered_listener import AbstractFilteredListener
from helpers import long_send, return_
from helpers.commands_helpers import get_args_from_text
from logger import logger


class AbstractUtils(AbstractFilteredListener):
    """Base class for Utils listeners"""
    pass


def format_help_item(key, value, prefix):
    commands = " / ".join([f"`{prefix}{command}`" for command in value[0]])
    return f"**{key}**\n - *Commandes*: {commands}\n - *Description*: {value[1]}\n"


def format_help_dict(dico, prefix):
    res = ""
    for k, v in dico.items():
        res += "* " + format_help_item(k, v, prefix)
    return res


def format_short_help_dict(dico, prefix):
    res = ""
    for k, v in dico.items():
        commands = " / ".join([f"`{prefix}{command}`" for command in v[0]])
        res += f"- **{k}**: {commands}\n"
    return res


# noinspection PyUnusedLocal
class CommandUtils(AbstractFilteredListener):
    _method_to_commands: Dict[str, Tuple[Iterable[str], str]] = {
        "help": [("help", "aide"),
                 "Obtenir de l'aide sur les commandes"],
        "set_verbose": [("verbose", "bavard"),
                        "Le bot donnera des informations de connexion (nouveau membre, bot déconnecté, etc.). "
                        "Inverse de 'quiet'."],
        "set_quiet": [("quiet", "discret"),
                      "Le bot ne donnera pas d'informations sur les connexions. Inverse de 'verbose'."]}
    _default_methods: Iterable[str] = None
    _method_pretreatment = {"_auto_delete": ("-d", "--auto-delete")}

    def __init__(self, **kwargs):
        self._prefix = kwargs.pop("prefix", "!")
        self._verbose = kwargs.pop("verbose", VERBOSE)
        self._sep = kwargs.pop("sep", " ")
        _default_methods = list(self._method_to_commands) if self._default_methods is None else self._default_methods
        self._active_methods = kwargs.pop("commands", _default_methods)
        super().__init__(**kwargs)
        self._channels = {}

    def set_verbose(self, message, args):
        self._verbose = True

    def set_quiet(self, message, args):
        self._verbose = False

    async def show_help(self, channel):
        title = f"**Commandes** [préfixe: {self._prefix}]"
        description = format_help_dict(self._method_to_commands, prefix=self._prefix)
        if not channel.permissions_for(channel.guild.me).embed_links:
            await long_send(channel, f"{title}\n{description}", quotes=False)
        else:
            await long_send(channel, description, embed=True, title=title, colour=channel.guild.me.colour)

    async def show_short_help(self, channel: TextChannel):
        title = "**Commandes** *[abrégé]*"
        description = format_short_help_dict(self._method_to_commands, prefix=self._prefix)
        if not channel.permissions_for(channel.guild.me).embed_links:
            await long_send(channel, f"{title}\n{description}", quotes=False)
        else:
            await long_send(channel, description, embed=True, title=title, colour=channel.guild.me.colour)

    async def help(self, message, args):
        await self.show_help(message.channel)

    # noinspection PyUnusedLocal
    @staticmethod
    async def _auto_delete(message, args):
        try:
            await message.delete()
        except (Forbidden, NotFound, HTTPException) as err:
            logger.debug(f"Fail to auto-delete message: {err}")

    async def _handle_message(self, message, command, args):
        for method, possible_commands in self._method_to_commands.items():
            if method not in self._active_methods:  # method deactivated
                return
            if command not in possible_commands[0]:
                continue
            if "--help" in args:
                return await message.channel.send(format_help_item(method, possible_commands, self._prefix))
            for pre_method, possible_args in self._method_pretreatment.items():
                for arg in possible_args:
                    if arg in args:
                        args.pop(args.index(arg))
                        await getattr(self, pre_method)(message, args)
            return await return_(getattr(self, method)(message, args))
        logger.debug(f"Command not found: {command}")

    async def _analyze_message(self, message):
        if not message.content.startswith(self._prefix):
            return
        if message.author.bot:
            return

        content = message.content[len(self._prefix):].strip()

        command, *args = get_args_from_text(content)
        for i, arg in enumerate(args):
            args[i] = arg.strip()
        logger.debug(f"Command received: {command}")

        await self._handle_message(message, command, args)
