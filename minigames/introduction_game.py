from collections import OrderedDict
import inspect

import discord
from discord import TextChannel, PermissionOverwrite, File

from bot_management import GuildManager
from constants import BOT
from default_collections import Emojis, ChannelCollection, RoleCollection
from game_models.abstract_minigame import AbstractMiniGame
from helpers import send_dm_message, long_send
from helpers.json_helpers import TranslationDict
from logger import logger
from models import PermissionOverwriteDescription
from utils_listeners import MusicTools
from utils_listeners.role_by_reaction import RoleByReactionManager, RoleMenuOptions


class Messages(TranslationDict):
    # Default values (overridden if a translation is loaded)
    WELCOME = "Welcome !\n For help, call {master} in {channel}!"
    WELCOME_FILE = "files/placeholder.png"
    DM_MESSAGE_WELCOME = "Welcome {user}!"
    DM_MESSAGES_ERROR = "{user_mention} change your settings, then send a message to {bot_mention}! (See image below)"
    DM_MESSAGES_ERROR_FILE = "files/param_privacy_discord.png"

    INTRO_MASTER = "Emojis to pass steps:\n" \
                   "step_0->1: {emoji_1}\nstep_1->2: {emoji_2} or {key_words}\nstep_2->3: {emoji_3}\n" \
                   "step_3->4: {emoji_4}\n" \
                   "{emoji_5}" \
                   "To change team constitutions: {change_teams_command}"

    SYNOPSIS = "Synopsis. Characters: {character_1}{character_2}{character_3}{character_4}"

    SYNOPSIS_2 = "Synopsis 2"

    BECOME_VISITOR = "Rules. Problem: {support_mention} / {master_role_mention}\n\n" \
                     "Sign with emoji {emoji_sign}to continue!"

    TEAM_MAKING = "Organization in {nb_teams} teams ! Please react. Maximum number per team: {max_number_per_team}."
    TEAM_MAKING_SIMPLE = "Let {master} create teams!"

    END_OF_INTRO = "Let's go!"
    EMOJI_1 = Emojis.european_castle
    EMOJI_2 = Emojis.lock
    TRIGGERS_2 = ["restricted", "closed"]
    EMOJI_3 = Emojis.mag
    EMOJI_RULES = Emojis.pen_ballpoint
    EMOJI_4 = Emojis.ok_hand
    EMOJI_5 = Emojis.ok_hand
    JINGLES = "🔥 sample.wav"


MESSAGES = Messages(path="configuration/minigames/introduction_game")

"""
Steps:
Between each step, the master can explain the rules.
0: message WELCOME: auto
1: message SYNOPSIS: manually by master
2: message SYNOPSIS_2: manually by master or by a member with a trigger
3: message BECOME_VISITOR: manually by master or after 2 messages of a member (!== master)
4: message TEAM_MAKING: when everyone has accepted the rules presented by BECOME_VISITOR message
5: end of introduction
"""


class IntroductionGame(AbstractMiniGame):
    _default_messages = MESSAGES

    def __init__(self, **kwargs):
        self._introduction_channel_d = ChannelCollection.get(kwargs.pop("introduction_channel", "WELCOME"))
        self._support_channel_d = ChannelCollection.get(kwargs.pop("support_channel", "SUPPORT"))
        self._master_role_description = RoleCollection.get(kwargs.pop("master_role_description", "MASTER"))
        self._default_role_description = RoleCollection.get(
            kwargs.pop("default_role_description", "DEFAULT"))  # no right
        self._visitor_role_description = RoleCollection.get(
            kwargs.pop("visitor_role_description", "VISITOR"))  # see/send
        self._emoji_to_team_role_key = OrderedDict([(k, RoleCollection.get(v)) for k, v in kwargs.pop(
            "emoji_to_team_role_key",
            OrderedDict([(Emojis.red_circle, "TEAM1"), (Emojis.blue_circle, "TEAM2"), (Emojis.white_circle, "TEAM3")])
        ).items()])
        self._character_role_descriptions_dict = {
            key: RoleCollection.get(role_key)
            for key, role_key in kwargs.pop("character_role_descriptions_dict",
                                            {"character_1": "CHARACTER1", "character_2": "CHARACTER2",
                                             "character_3": "CHARACTER3", "character_4": "CHARACTER4"}).items()}
        self._nb_teams = kwargs.pop("nb_teams", 3)
        self._max_number_per_team = kwargs.pop("max_number_per_team", 8)

        super().__init__(**kwargs)
        self._step = 0
        self._max_step = 5
        self._counter_2_to_3 = 0
        self._rolemenu_manager = None
        self._rules_msg_id = None
        self._choose_team_msg = None
        self._nb_players = None
        self._nb_teams_command = "!teams"

    async def _init(self):
        self._step = 0
        self._counter_2_to_3 = 0
        self._rolemenu_manager = None
        self._rules_msg_id = None
        self._choose_team_msg = None
        self._nb_players = None
        GuildManager().get_guild(self.guild).nb_teams = self._nb_teams  # Change number of teams globally.
        # Update channel permissions to forbid send messages and read message history
        permissions = PermissionOverwriteDescription(read_message_history=True, add_reactions=False,
                                                     send_messages=False, view_channel=True)
        master_perm = PermissionOverwriteDescription(read_message_history=True, add_reactions=True,
                                                     send_messages=True, view_channel=True)
        overwrites = {self._default_role_description.object_reference: PermissionOverwrite(**permissions.to_dict()),
                      self._master_role_description.object_reference: PermissionOverwrite(**master_perm.to_dict()),
                      }
        await self._introduction_channel_d.object_reference.edit(overwrites=overwrites)
        # Send a welcome message to pre-existing users
        for member in self._introduction_channel_d.object_reference.members:
            if (self._default_role_description.has_the_role(member)
                    and not self._master_role_description.has_the_role(member)):
                await self.welcome_dm_message(member, origin_channel=self._support_channel_d.object_reference)
        # Purge introduction channel and send the first message
        intro_channel: TextChannel = self._introduction_channel_d.object_reference
        while await intro_channel.history(limit=1).flatten():  # completely purge the channel
            await self._introduction_channel_d.object_reference.purge(limit=1000)
        await self.welcome_general_message(self._introduction_channel_d.object_reference)
        # Send instructions to master channel
        msg = self._messages["INTRO_MASTER"].format(emoji_1=self._messages["EMOJI_1"],
                                                    emoji_2=self._messages["EMOJI_2"],
                                                    key_words=self._messages["TRIGGERS_2"],
                                                    emoji_3=self._messages["EMOJI_3"],
                                                    emoji_4=self._messages["EMOJI_4"],
                                                    emoji_5=self._messages["EMOJI_5"],
                                                    change_teams_command=f"`{self._nb_teams_command} "
                                                                         f"NUMBER_TEAMS MAX_NUMBER_PER_TEAM`")
        await long_send(self._master_channel_description.object_reference, msg, quotes=False)
        music_msg = await long_send(self._music_channel_description.object_reference, self._messages["JINGLES"])
        await MusicTools.jingle_palette_from_message(music_msg)
        return True

    async def welcome_general_message(self, channel):
        reception_channel = self._support_channel_d.object_reference
        master_mention = self._master_role_description.object_reference.mention
        await channel.send(
            self._messages["WELCOME"].format(master=master_mention, channel=reception_channel.mention),
            file=discord.File(self._messages["WELCOME_FILE"])
        )

    async def handle_dm_message_error(self, reason, user: discord.user.User, origin_channel=None):
        logger.info(f"Impossible to send DM message to {user.name} (id: {user.id}). Reason: {reason}")
        if origin_channel:
            await origin_channel.send(
                self._messages["DM_MESSAGES_ERROR"].format(user_mention=user.mention, bot_mention=BOT.user.mention),
                file=discord.File(self._messages["DM_MESSAGES_ERROR_FILE"])
            )

    async def welcome_dm_message(self, user: discord.user.User, origin_channel=None):
        message = self._messages["DM_MESSAGE_WELCOME"].format(user=user.display_name)
        await send_dm_message(user, message, origin_channel, callback_on_forbidden_error=self.handle_dm_message_error)

    async def on_member_join(self, member):
        if member.bot:
            return
        await self.welcome_dm_message(member, origin_channel=self._support_channel_d.object_reference)

    async def on_connect(self):
        pass

    async def step_0(self, message):
        if self._step != 0:
            return
        if (self._master_role_description.object_reference in message.author.roles
                and self._messages["EMOJI_1"] in message.content):
            self._step = 1
            msg = self._messages["SYNOPSIS"].format(**{key: descr.object_reference.mention
                                                       for key, descr in
                                                       self._character_role_descriptions_dict.items()})
            await message.channel.send(msg, file=File(self._messages["SYNOPSIS_FILE"]))
            # Update channel permissions to allow send messages
            permissions = PermissionOverwriteDescription(read_message_history=True, add_reactions=False,
                                                         send_messages=True, view_channel=True)
            await message.channel.edit(overwrites={
                self._default_role_description.object_reference: PermissionOverwrite(**permissions.to_dict())})

    async def step_1(self, message):
        if self._step != 1:
            return
        if ((self._master_role_description.object_reference in message.author.roles
             and self._messages["EMOJI_2"] in message.content)
                or (self._master_role_description.object_reference not in message.author.roles
                    and any(trigger.lower() in message.content.lower() for trigger in self._messages["TRIGGERS_2"]))):
            self._step = 2
            await message.channel.send(self._messages["SYNOPSIS_2"])

    async def step_2(self, message):
        if self._step != 2:
            return
        if (self._master_role_description.object_reference in message.author.roles
                and self._messages["EMOJI_3"] in message.content):
            self._step = 3
        elif self._master_role_description.object_reference not in message.author.roles:
            self._counter_2_to_3 += 1
            if self._counter_2_to_3 >= 2:
                self._step = 3
        if self._step == 3:
            msg = self._messages["BECOME_VISITOR"].format(
                emoji_sign=self._messages["EMOJI_RULES"],
                support_mention=self._support_channel_d.object_reference.mention,
                master_role_mention=self._master_role_description.object_reference.mention
            )
            rules_msg = await message.channel.send(msg)
            self._rules_msg_id = rules_msg.id
            self._rolemenu_manager = RoleByReactionManager.get(self.guild)
            menu = {self._messages["EMOJI_RULES"]: [self._visitor_role_description]}
            options = RoleMenuOptions(ignored_roles=[self._master_role_description])
            await self._rolemenu_manager.add(rules_msg, menu, options)

    async def _update_number_of_players(self, channel):
        rules_msg = await channel.fetch_message(self._rules_msg_id)
        for reaction in rules_msg.reactions:
            if reaction.emoji == self._messages["EMOJI_RULES"]:
                reaction_users = await reaction.users().flatten()
                self._nb_players = len(reaction_users) - 1  # -1: bot reaction does not count
                return
        self._nb_players = None

    async def step_3(self, message):
        if self._step != 3:
            return
        if (self._master_role_description.object_reference in message.author.roles
                and self._messages["EMOJI_4"] in message.content):
            self._step = 4
        elif self._master_role_description.object_reference not in message.author.roles:
            await self._update_number_of_players(message.channel)
            members = [mb for mb in message.channel.members if
                       not mb.bot and not self._master_role_description.has_the_role(mb)]
            if self._nb_players and len(members) == self._nb_players:
                self._step = 4
        if self._step == 4:
            await self._update_number_of_players(message.channel)
            if self._simple_mode:
                await message.channel.send(self._messages["TEAM_MAKING_SIMPLE"].format(
                    master=self._master_role_description.object_reference.mention))
            else:
                msg = self._messages["TEAM_MAKING"].format(nb_teams=self._nb_teams,
                                                           max_number_per_team=self._max_number_per_team)
                self._choose_team_msg = await message.channel.send(msg)
                menu = {}
                for i, (k, v) in enumerate(self._emoji_to_team_role_key.items()):
                    menu[k] = [v]
                    if i >= self._nb_teams - 1:
                        break
                options = RoleMenuOptions(ignored_roles=[self._master_role_description], allow_role_change=False,
                                          max_number_of_reactions_per_user=1,
                                          max_users_with_role=self._max_number_per_team)
                await self._rolemenu_manager.add(self._choose_team_msg, menu, options)

    async def step_4(self, message):
        if self._step != 4:
            return
        if (self._master_role_description.object_reference in message.author.roles
                and self._messages["EMOJI_5"] in message.content):
            self._step = 5
        elif self._master_role_description.object_reference not in message.author.roles:
            teams_msg = await message.channel.fetch_message(self._choose_team_msg.id)
            count_players = 0
            for reaction in teams_msg.reactions:
                if reaction.emoji in self._rolemenu_manager.get_menu(teams_msg.id)[0]:
                    reaction_users = await reaction.users().flatten()
                    count_players += len(reaction_users) - 1
            if count_players == self._nb_players:
                self._step = 5
        if self._step == 5:
            await self.on_victory()

    async def _on_victory(self, *args, **kwargs):
        await self._introduction_channel_d.object_reference.send(self._messages["END_OF_INTRO"])
        # Update channel permissions to forbid send messages
        permissions = PermissionOverwriteDescription(read_message_history=True, add_reactions=False,
                                                     send_messages=False, view_channel=True)
        overwrites = {self._default_role_description.object_reference: PermissionOverwrite(**permissions.to_dict())}
        await self._introduction_channel_d.object_reference.edit(overwrites=overwrites)

    async def change_channel_number(self, message):
        # For game master only
        if self._step >= 4:
            await message.channel.send("Too late to change number of teams :/")
        else:
            try:
                args = list(filter(None, message.content.split(" ")))
                nb_teams, max_number_per_team = int(args[1]), int(args[2])
                if nb_teams < 1 or nb_teams > 3 or max_number_per_team < 1:
                    raise ValueError(f"Bad interval for values {nb_teams} {max_number_per_team}")
                self._nb_teams, self._max_number_per_team = nb_teams, max_number_per_team
                GuildManager().get_guild(self.guild).nb_teams = nb_teams  # Change number of teams globally.
            except (ValueError, IndexError) as err:
                err_msg = f"Error to convert command to team number: {message.content} (Error: {err})"
                logger.warning(err_msg)
                await message.channel.send(err_msg)
            else:
                await message.channel.send(f"Changed number of teams to {self._nb_teams} with a maximum "
                                           f"of {self._max_number_per_team} members per team")

    async def _analyze_message(self, message: discord.Message):
        if not self._active:
            return
        if self._step >= self._max_step:
            return
        if (message.channel == self._master_channel_description.object_reference
                and self._nb_teams_command in message.content):
            await self.change_channel_number(message)
            return
        if not message.channel == self._introduction_channel_d.object_reference:
            return
        self._step_methods = {i: f"step_{i}" for i in range(self._max_step)}
        res = getattr(self, self._step_methods[self._step])(message)
        if inspect.isawaitable(res):
            await res
