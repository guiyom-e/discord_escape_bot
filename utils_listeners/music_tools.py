import os
import re

from discord import Message

from constants import SONG_PATH
from default_collections import RoleCollection, ChannelCollection
from functions import is_key_in_args
from game_models import CommandUtils, AbstractUtils
from helpers import long_send, TranslationDict
from helpers.commands_helpers import get_args_from_text
from helpers.sound_helpers import SoundTools
from logger import logger
from models import RoleDescription
from utils_listeners.jingle_palette import JinglePaletteOptions, JinglePaletteManager


class Messages(TranslationDict):
    INTRO = "Music tools"


MESSAGES = Messages(path="configuration/utils/music_tools/")


# noinspection PyUnusedLocal
class MusicTools(SoundTools, CommandUtils, AbstractUtils):
    _default_messages = MESSAGES
    _default_allowed_roles = [RoleCollection.DEV, RoleCollection.MASTER]
    _method_to_commands = {
        "help": [("help", "aide"), "Obtenir de l'aide sur les commandes"],
        "play_song": [("play", "jouer"), "Jouer une musique (locale ou YouTube)\n"
                                         " - *Arguments*:\n o Couper la musique en cours : `-f` / `--force`"],
        "pause": [("pause",), "Mettre la musique en pause"],
        "resume": [("resume",), "Reprendre la musique mise en pause"],
        "stop_song": [("stop", "disconnect", "stop_song",), "Se déconnecter de la voix"],
        "show_songs": [("show_songs", "songs"), "Voir les musiques disponibles"],
        "jingle_palette": [("jingle", "jingles", "palette"),
                           "Créer une palette de bruitages et musiques.\n"
                           " - *Syntaxe*: `jingles [[emoji] [lien YouTube]...] [OPTIONS]`\n"
                           "   Taper `jingles -h` pour plus d'info."],
    }
    _method_pretreatment = {"_auto_delete": ("-d", "--auto-delete"),
                            "stop": ("-f", "--force")}

    def __init__(self, **kwargs):
        self._music_channel_description = ChannelCollection.get(kwargs.pop("music_channel_description", "MUSIC"))
        super().__init__(**kwargs)

    async def _init(self):
        logger.info("Music tools activated!")
        channel = self._music_channel_description.object_reference
        if not channel:
            logger.debug(f"{self._music_channel_description} channel doesn't exist")
            return True
        if self._verbose:
            await channel.purge(limit=1000)
            await channel.send(self._messages["INTRO"])
            await self.show_short_help(channel)
        return True

    async def play_song(self, message, args):
        logger.debug("Play command")
        if not len(args):
            args = ["sample.wav"]
        if "-f" in args or "--force" in args:
            force = True
        else:
            force = False
        song_path = args[0]
        # if os.path.isfile(os.path.join(SONG_PATH, args[0])):
        #     song_path = os.path.join(SONG_PATH, args[0])
        voice = message.author.voice
        if voice:
            voice_channel = voice.channel
            logger.debug("connection")
            success = await self.play(voice_channel, song_path, force=force)
            if not success:
                await message.channel.send("Une musique est déjà en cours !")
        else:
            logger.debug("The user is not connected to a voice channel")
            await message.channel.send("Choisis une pièce avec une bonne acoustique pour que je t'explique !")

    @staticmethod
    async def show_songs(message, args):
        await long_send(message.channel, "- " + "\n- ".join(os.listdir(SONG_PATH)), quotes=False)

    async def stop_song(self, message, args):
        if "stop" in message.content[1:].split() and args:
            # Possible conflict with game_tools command 'stop' if the prefix is the same!
            # But 'stop' is a convenient name to stop the music...
            # So, if args are passed, 'stop' is ignored in music tools
            return
        await self.disconnect()

    @staticmethod
    async def _print_jingle_palette_help(channel):
        await channel.send(
            "*Creates a jingle palette with reactions.*\n"
            "**Role menu syntax:**\n"
            '`jingles [[emoji] [link] "[optional comment]" ...] [OPTIONS]`\n\n'
            "**Menu options:**\n"
            "* `--no-update`: no reaction removal if the user doesn't have the required role.\n"
            "* `--no-auto-remove`: do not remove the reaction after the user clicked on it.\n"
            "* `--stop-on-remove`: stop the current song on reaction removal. Works with `--no-auto-remove` only.\n"
            "* `--allow-embed`: allow embed links in the message menu.\n"
            "* `[@ROLE]`: role mentions of roles allowed to use the palette. "
            f"If no role mention, the default required role is {RoleCollection.MASTER.object_reference.mention}."
        )

    @staticmethod
    def _get_menu_from_args(args):
        menu = {}
        ind_emoji = 0
        ind_link = 0
        try:
            while ind_link < len(args):
                ind_emoji = ind_link
                comment = False
                if args[ind_emoji].startswith('"') and args[ind_emoji].endswith('"'):
                    # this is a comment
                    ind_emoji += 1
                    comment = True
                if (not comment and ind_emoji + 1 < len(args)
                        and args[ind_emoji + 1].startswith('"') and args[ind_emoji + 1].endswith('"')):
                    # this is a comment
                    ind_link = ind_emoji + 2
                    comment = True
                else:
                    ind_link = ind_emoji + 1
                menu.update({args[ind_emoji].replace("\n", "").strip(): args[ind_link].replace("\n", "").strip()})
                ind_link += 1
                if (not comment and ind_link < len(args)
                        and args[ind_link].startswith('"') and args[ind_link].endswith('"')):
                    # this is a comment
                    ind_link += 1
        except IndexError as err:
            logger.warning(f"Error while creating jingle menu: {err}")
            return None
        return menu

    @classmethod
    async def jingle_palette_from_message(cls, message: Message):
        args = get_args_from_text(message.content)
        return await cls.jingle_palette(message, args)

    @classmethod
    async def jingle_palette(cls, message, args):
        """Creates a jingle palette in one command

        Limitations compared to all JinglePaletteManager possibilities:
        - impossible to set ignored roles

        :param message: discord Message
        :param args: list of args:
        [emoji_1, song_local_path_1, emoji_2, ...] or [emoji_1, youtube_link_1, emoji_2, ...]
        Can contain optional arguments (see code)
        """
        if "-h" in args or "--help" in args or "--ahelp" in args:
            await cls._print_jingle_palette_help(message.channel)
            return
        update_reactions = not is_key_in_args(args, "--no-update")
        stop_jingle_on_reaction_removal = is_key_in_args(args, "--stop-on-remove")
        auto_remove = not is_key_in_args(args, "--no-auto-remove")
        suppress_embed = not is_key_in_args(args, "--allow-embed")
        required_roles = [RoleDescription.from_role(role) for role in message.role_mentions] or [RoleCollection.MASTER]
        for ind_emoji in range(len(args) - 1, -1, -1):
            if re.match(r".*<@&[0-9]+>.*", args[ind_emoji]):
                args.pop(ind_emoji)
        nb_comments = sum(1 for ele in args if ele.startswith('"') and ele.endswith('"'))
        if (len(args) - nb_comments) % 2 or (len(args) - nb_comments) // 2 < nb_comments:  # not a pair number
            await message.channel.send("Error with `jingles`: all jingles must match an emoji "
                                       "and comments must be inside quotes (\")")
            return await cls._print_jingle_palette_help(message.channel)
        menu = cls._get_menu_from_args(args)
        if menu is None:
            await message.channel.send("Error with `jingles`: all jingles must match an emoji "
                                       "and comments must be inside quotes (\")")
            return await cls._print_jingle_palette_help(message.channel)
        manager = JinglePaletteManager.get(message.guild)
        options = JinglePaletteOptions(required_roles=required_roles, update_reactions=update_reactions,
                                       stop_jingle_on_reaction_removal=stop_jingle_on_reaction_removal,
                                       auto_remove=auto_remove, suppress_embed=suppress_embed)
        await manager.add(message, menu, options)
        logger.debug("Jingle palette created. Now you can edit your post to make it prettier.")
