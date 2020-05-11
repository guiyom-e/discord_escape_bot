import random
from time import sleep

from discord import Member

from bot_management import GuildManager
from bot_management.listener_utils import (start_channel_game, stop_channel_game, reset_channel_game,
                                           force_channel_victory, stop_listener,
                                           start_listener, force_victory, game_board, control_panel,
                                           show_listeners_list)
from constants import BOT
from default_collections import RoleCollection, ChannelCollection
from functions import get_number_in_args, is_key_in_args
from game_models import CommandUtils, AbstractMiniGame, AbstractUtils
from helpers import (TranslationDict)
from helpers.commands_helpers import is_int, find_channel_mentions_in_message
from helpers.invitations import delete_invite, create_invite
from logger import logger
from utils_listeners.role_by_reaction import RoleByReactionManager, RoleMenuOptions


class Messages(TranslationDict):
    INTRO = "Dans cette chaîne réinitialisée à chaque démarrage, tu peux écrire tes commandes personnalisées " \
            "parmi la liste suivante. Pour maîtres du jeux avertis uniquement. " \
            "Sinon, utiliser le panneau de contrôle et tableaude bord du jeu dans #tableau-de-bord.\n" \
            "Tu peux taper `!help` pour plus d'inforamtions sur les commandes."
    CONNECTION = "{bot_name} connecté !"
    READY = "{bot_name} prêt !"
    DISCONNECTION = "{bot_name} déconnecté !"
    JOIN = "{user} a rejoint le serveur !"
    QUIT = "{user} a quitté le serveur !"


MESSAGES = Messages()


# noinspection PyUnusedLocal
class GameUtils(CommandUtils, AbstractUtils):
    _default_messages = MESSAGES

    _default_allowed_roles = [RoleCollection.DEV, RoleCollection.MASTER]
    _method_to_commands = {
        "help": [("help", "aide"), "Obtenir de l'aide sur les commandes"],
        "create_invite": [("create_invite", "invite"),
                          "Créer un message d'invitation."
                          "\n - *Arguments*:\n o Durée de validité (secondes) : `-a` / `--max-age` `[entier]`\n"
                          " o Nombre maximal d'utilisations : `-u` / `--max-uses` `[entier]`\n"
                          " o Temporaire : `-t` / `--temp`\n"
                          " o Réutiliser un ancien lien si possible : `--unique`\n"
                          " o Publier le lien sur le site : `-s` / `--website`\n"
                          " o Supprimer l'invitation sur le site : `--delete`"],
        "delete_invite": [("delete_invite", "del_invite"), "Supprimer l'invitation sur le site"],
        "minigames": [("minigames", "listeners"), "Lister l'ensemble des mini-jeux avec leur identifiant."],
        "game_board": [("board", "game_board"), "Afficher le tableau de bord du jeu"],
        "control_panel": [("control_panel", "control_board", "control"), "Afficher le panneau de contrôle général"],
        "update": [("update",), "Mettre à jour le serveur"],
        "start_game": [("start", "start_game"), "Démarrer un mini-jeu. *Argument*: l'identifiant du mini-jeu."],
        "stop_game": [("stop", "stop_game"), "Arrêter un mini-jeu. *Argument*: l'identifiant du mini-jeu."],
        "force_victory": [("force_victory", "victory"),
                          "Forcer la victoire d'un mini-jeu. *Argument*: l'identifiant du mini-jeu."],
        "force_channel_victory": [("force_channel_victory", "channel_victory", "ch_victory", "victory_ch"),
                                  "Forcer la victoire d'un mini-jeu par salon.\n"
                                  " - *Arguments*: l'identifiant du mini-jeu et une mention du salon "
                                  "(si pas de mention, la chaîne courante est utilisée)."],
        "start_channel_game": [("start_channel", "start_channel_game", "start_ch"),
                               "Démarrer un mini-jeu par salon (le mini-jeu lui-même doit être démarré).\n"
                               "- *Arguments*: l'identifiant du mini-jeu et une mention du salon "
                               "(si pas de mention, la chaîne courante est utilisée)."],
        "stop_channel_game": [("stop_channel", "stop_channel_game", "stop_ch"), ""],
        "reset_channel_game": [("reset_ch", "reset_channel"),
                               "Arrêter un mini-jeu par salon.\n"
                               " - *Arguments*: l'identifiant du mini-jeu et une mention du salon "
                               "(si pas de mention, la chaîne courante est utilisée)."],
        "rolemenu": [("rolemenu",), "Créer un menu pour s'auto-attribuer des rôles.\n"
                                    " - *Syntaxe*: `rolemenu [[@ROLE] [emoji] ...] [OPTIONS]`\n"
                                    "   Taper `rolemenu -h` pour plus d'info."],
        "speak_for_bot": [("sfb", "send"), "Parler à la place du bot.\n"
                                           " - *Argument optionnel* : une mention du salon "
                                           "(si pas de mention, la chaîne courante est utilisée)."],
        "randint": [("randint", "alea"),
                    "Génère un entier aléatoire entre 0 et 100.\n"
                    " - *Arguments optionnels*: 1 entier X -> entre 0 et X\n"
                    "   2 entiers X, Y -> entre X et Y\n"
                    "   3 entiers X, Y, Z -> X entiers entre Y et Z (message édité toutes les secondes)"],
        "set_verbose": [("verbose", "bavard"),
                        "Le bot donnera des informations de connexion (nouveau membre, bot déconnecté, etc.). "
                        "Inverse de 'quiet'."],
        "set_quiet": [("quiet", "discret"),
                      "Le bot ne donnera pas d'informations sur les connexions. Inverse de 'verbose'."]
    }

    def __init__(self, **kwargs):
        self._events_channel_description = ChannelCollection.get(kwargs.pop("events_channel_description", "COMMANDS"))
        super().__init__(**kwargs)

    async def _init(self):
        logger.info("Game tools activated!")
        channel = self._events_channel_description.object_reference
        if not channel:
            logger.debug(f"{self._events_channel_description} channel doesn't exist")
            return True
        if self._verbose:
            await channel.purge(limit=1000)
            await channel.send(self._messages["INTRO"])
            await self.show_short_help(channel)
        return True

    async def on_ready(self):
        channel = self._events_channel_description.object_reference
        if not channel:
            return
        if self._verbose:
            await channel.send(self._messages["READY"].format(bot_name=BOT.user.display_name))

    async def on_connect(self):
        channel = self._events_channel_description.object_reference
        if not channel:
            return
        if self._verbose:
            await channel.send(self._messages["CONNECTION"].format(bot_name=BOT.user.display_name))

    async def on_disconnect(self):
        channel = self._events_channel_description.object_reference
        if not channel:
            return
        if self._verbose:
            await channel.send(self._messages["DISCONNECTION"].format(bot_name=BOT.user.display_name))

    async def on_member_join(self, member: Member):
        channel = self._events_channel_description.object_reference
        if not channel:
            return
        if self._verbose:
            await channel.send(self._messages["JOIN"].format(user=member.display_name))

    async def on_member_remove(self, member: Member):
        channel = self._events_channel_description.object_reference
        if not channel:
            return
        if self._verbose and member != member.guild.me:
            await channel.send(self._messages["QUIT"].format(user=member.display_name))

    @staticmethod
    async def create_invite(message, args):
        if "--delete" in args:
            return await delete_invite(message.channel)
        channels = find_channel_mentions_in_message(message, args, message_channel_if_not_found=True)
        channel = channels[0]
        if len(channels) > 1:
            logger.warning("Only one channel can be used to create an invite !")
        kwargs = {}
        for i, arg in enumerate(args):
            if arg in ("--max_age", "--max-age", "-a") and i + 1 < len(args):
                if is_int(args[i + 1]):
                    kwargs["max_age"] = int(args[i + 1])
            elif arg in ("--max_uses", "--max-uses", "-u") and i + 1 < len(args):
                if is_int(args[i + 1]):
                    kwargs["max_uses"] = int(args[i + 1])
            elif arg in ("--temporary", "--temp", "-t"):
                kwargs["temporary"] = True
            elif arg in ("--unique",):
                kwargs["unique"] = True
            elif arg in ("--website", "-s"):
                kwargs["website"] = True
        return await create_invite(channel, message.channel, **kwargs)

    @staticmethod
    async def delete_website_invite(message, args):
        return await delete_invite(message.channel)

    @staticmethod
    async def minigames(message, args):
        return await show_listeners_list(message.channel, listener_type=AbstractMiniGame)

    @staticmethod
    async def game_board(message, args):
        return await game_board(message.channel)

    @staticmethod
    async def control_panel(message, args):
        return await control_panel(message.guild)

    @staticmethod
    async def start_game(message, args):
        return await start_listener(message, args, listener_type=AbstractMiniGame)

    @staticmethod
    async def stop_game(message, args):
        return await stop_listener(message, args, listener_type=AbstractMiniGame)

    @staticmethod
    async def start_channel_game(message, args):
        return await start_channel_game(message, args)

    @staticmethod
    async def stop_channel_game(message, args):
        return await stop_channel_game(message, args)

    @staticmethod
    async def reset_channel_game(message, args):
        return await reset_channel_game(message, args)

    @staticmethod
    async def force_victory(message, args):
        return await force_victory(message, args)

    @staticmethod
    async def force_channel_victory(message, args):
        return await force_channel_victory(message, args)

    @staticmethod
    async def _print_rolemenu_help(channel):
        await channel.send(
            "*Creates a self-role-assignment with reactions.*\n"
            f"Required role: {RoleCollection.VISITOR.value.object_reference.mention}\n"
            f"Ignored role: {RoleCollection.MASTER.value.object_reference.mention}\n\n"
            "**Role menu syntax:**\n"
            "`rolemenu [[@ROLE] [emoji] ...] [OPTIONS]`\n\n"
            "**Rolemenu options:**\n"
            "* `--no-change`: no change allowed\n"
            "* `--no-update`: no reaction removal on role granting failure\n"
            "* `--no-removal`: do not remove role on reaction removal\n"
            "* `--all`: no required role\n"
            "* `--max-reactions NUMBER`: maximum number of reactions per user\n"
            "* `--max-users NUMBER`: maximum number of users per role (including pre-existing users with the role)")

    async def rolemenu(self, message, args):
        """Creates a role menu in one command

        Limitations compared to all RoleByReactionManager possibilities:
        - only one role per emoji, no combination possible
        - impossible to set ignored/required roles
        This command should be used for tests only.

        :param message: discord Message
        :param args: list of args:
        [role_mention_1, emoji_1, role_mention_2, ...] or [emoji_1, role_mention_1, emoji_2, ...]
        Can contain optional arguments (see code)
        """
        if "-h" in args or "--help" in args or "--ahelp" in args:
            await self._print_rolemenu_help(message.channel)
            return
        update_reactions = not is_key_in_args(args, "--no-update")
        allow_role_change = not is_key_in_args(args, "--no-change")
        remove_role_on_reaction_removal = not is_key_in_args(args, "--no-removal")
        max_number_of_reactions_per_user = get_number_in_args(args, "--max-reactions", None)
        max_users_with_role = get_number_in_args(args, "--max-users", None)
        no_required_role = is_key_in_args(args, "--all")
        role_ids = message.raw_role_mentions
        if len(role_ids) * 2 != len(args):
            await message.channel.send("Error with `rolemenu`: all roles must match an emoji")
            return await self._print_rolemenu_help(message.channel)
        menu = {}
        for i, role_id in enumerate(message.raw_role_mentions):
            emoji = args.pop(0)
            if emoji.strip("<>@&") == str(role_id):  # emoji and roles are just exchanged: no problem
                emoji = args.pop(0)
            elif args.pop(0).strip("<>@&") != str(role_id):  # error: two adjacent args must be role_id and emoji
                await message.channel.send("Error with `rolemenu`: a role must match an emoji")
                return await self._print_rolemenu_help(message.channel)
            menu.update({emoji: [message.guild.get_role(role_id)]})
        manager = RoleByReactionManager.get(self.guild)
        options = RoleMenuOptions(required_roles=None if no_required_role else [RoleCollection.VISITOR.value],
                                  ignored_roles=[RoleCollection.MASTER.value],
                                  update_reactions=update_reactions,
                                  allow_role_change=allow_role_change,
                                  max_number_of_reactions_per_user=max_number_of_reactions_per_user,
                                  max_users_with_role=max_users_with_role,
                                  remove_role_on_reaction_removal=remove_role_on_reaction_removal
                                  )
        await manager.add(message, menu, options)
        logger.debug("Rolemenu created. Now you can edit your post to make it prettier.")

    async def speak_for_bot(self, message, args):
        channels = find_channel_mentions_in_message(message, args, message_channel_if_not_found=True)
        msg = self._sep.join(args)
        if not msg:  # cannot send empty message
            return
        for channel in channels:
            await channel.send(msg)

    @staticmethod
    async def update(message, args, force=False):
        return await GuildManager().update_guild(message.channel.guild, message.channel,
                                                 force=force, clear_references=True)

    async def randint(self, message, args):
        if len(args) == 0:
            number = random.randint(0, 100)
        elif len(args) == 1:
            number = random.randint(0, int(args[0]))
        elif len(args) == 2:
            number = random.randint(int(args[0]), int(args[1]))
        elif len(args) == 3:
            bot_msg = await message.channel.send(0)
            return await self._randint_edit(bot_msg, 5, int(args[0]), int(args[1]), int(args[2]))
        else:
            return
        await message.channel.send(number)

    @staticmethod
    async def _randint_edit(message, nb_iter, min_val, max_val, wait=1):
        async def rand_fn():
            async with message.channel.typing():
                for i in range(nb_iter):
                    sleep(wait)
                    number = random.randint(min_val, max_val)
                    await message.edit(content=number)

        await rand_fn()
