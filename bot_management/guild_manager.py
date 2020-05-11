import asyncio
from collections import defaultdict
from enum import Enum
from typing import Dict, Optional, Union, Callable, Any

import discord
from discord import Guild, NotFound, TextChannel, HTTPException, Permissions, Message, Reaction, Member

from bot_management.listener_manager import ListenerManager, get_safe_text_channel
from constants import PASSWORD_KICK_BOT, PASSWORD_REMOVE_BOT
from default_collections import (GuildCollection, CharacterCollection, RoleCollection, CategoryChannelCollection,
                                 ChannelCollection, MinigameCollection)
from game_models.admin_tools import clear_object_references
from helpers import TranslationDict
from helpers.bot_availability import remove_bot_availability_on_website, add_bot_availability_on_website
from helpers.set_channels import delete_channels
from helpers.set_server import update_guild_channels, update_guild_roles, update_guild_properties
from logger import logger
from models.guilds import GuildWrapper
from models.types import Singleton, AbstractGuildListener

LOCK = asyncio.Lock()


class Messages(TranslationDict):
    PENDING_GUILD_OPTIONS = "Not available yet, 3 options"
    ALREADY_ELSEWHERE = "*Hello! I am already present in another guild, I can't duplicate myself, " \
                        "so I'll leave this server!\nWait that I am available to invite me again :wink:*"


MESSAGES = Messages(path="configuration/game_manager")


class PendingOptions(Enum):
    quit = "❌"
    try_again = "🔄"
    force = "♾️"


class GuildManager(metaclass=Singleton):
    """Unique class to manage all guilds the bot is member of."""

    def __init__(self):
        self._bot: Optional[discord.Client] = None
        self._init_coroutine: Optional[Callable] = None
        self._max_guilds = 0
        self._max_pending_guilds = 0
        self._guilds: Dict[int, GuildWrapper] = {}
        self._pending_guild: Dict[int, Dict[str, Any]] = defaultdict(dict)
        self._messages = MESSAGES

    def set_bot(self, bot: discord.Client, init_coroutine: Callable, max_guilds: int = 1,
                max_pending_guilds: int = 5) -> bool:
        if not isinstance(bot, discord.Client):
            logger.error(f"{bot} is not a Discord Client!")
            return False
        self._bot = bot
        self._init_coroutine = init_coroutine
        self._max_guilds = max_guilds
        self._max_pending_guilds = max_pending_guilds
        return True

    async def _init_guild(self, guild_wrapper: GuildWrapper, versions):
        guild_wrapper.versions = versions
        await guild_wrapper.clear_listeners()
        await self._init_coroutine(guild_wrapper)

    async def reset_guild(self, guild_wrapper: GuildWrapper, versions):
        """Reset guild version"""
        await self._init_guild(guild_wrapper, versions)

    async def change_guild_version(self, guild, versions, clear=True, origin_channel=None):
        guild_wrapper = self.get_guild(guild)
        msg = f"Reloading guild to {versions if versions else 'default'} version(s) {'' if clear else ' (update)'}..."
        logger.info(msg)
        if origin_channel:
            await origin_channel.send(msg)
        try:
            await GuildCollection.reload(versions=versions, clear=clear)
            await CharacterCollection.reload(versions=versions, clear=clear)
            await RoleCollection.reload(versions=versions, clear=clear)
            await CategoryChannelCollection.reload(versions=versions, clear=clear)
            await ChannelCollection.reload(versions=versions, clear=clear)
            await MinigameCollection.reload(versions=versions, clear=clear)
            await guild_wrapper.listener_manager.reload(versions=versions, clear=clear)
            await GuildManager().reset_guild(guild_wrapper,
                                             versions=versions)  # todo: make reset_guild take versions into account
            for listener in guild_wrapper.listeners:
                listener.reload(versions=versions, clear=clear)
            guild_wrapper.versions = versions
        except Exception as err:
            msg = f"Guild could not be reloaded to `{versions if versions else 'default'}` version(s)." \
                  f"The version(s) are invalid or an error occurred."
            logger.warning(msg)
            if origin_channel:
                await origin_channel.send(msg)
            raise err
        else:
            msg = f"Guild reloaded to `{versions if versions else 'default'}` version(s) " \
                  f"{'' if clear else ' (update)'}. It is highly recommended to update the guild."
            logger.info(msg)
            if origin_channel:
                await origin_channel.send(msg)

    async def init_guilds(self, versions):
        logger.debug(f"Adding all bot guilds to GuildManager: {self._bot.guilds}")
        if self._bot is None:
            logger.critical(f"No bot defined in {self.__class__.__name__}! Cannot init guilds!")
            return False
        guilds = self._bot.guilds
        for guild in guilds:
            await self.add_guild(guild, versions=versions)
        if not guilds:
            add_bot_availability_on_website()
            bot_invite_link = discord.utils.oauth_url(client_id=self._bot.user.id, permissions=Permissions(8))
            logger.info(f"The bot is not in a guild! To invite it, use the following link: {bot_invite_link}")
        return True

    async def add_guild(self, guild_ref: Union[int, Guild, GuildWrapper], versions=None) -> Optional[GuildWrapper]:
        async with LOCK:
            logger.debug(f"Guilds available: {self._bot.guilds}")
            if isinstance(guild_ref, (Guild, GuildWrapper)):
                guild_ref: int = guild_ref.id
            guild = self._bot.get_guild(guild_ref)  # Use guild ID
            if not guild:  # Guild not found
                logger.warning(f"Guild with id {guild_ref} not found!")
                return None
            if guild_ref in self._guilds:  # Guild already exists
                logger.warning(f"Guild {guild} already exists in GuildManager! It won't be initialized again.")
                return self._guilds[guild_ref]
            # Handle pending guilds
            if len(self._guilds) >= self._max_guilds:
                logger.warning(f"Cannot add the guild {guild_ref} to GuildManager: "
                               f"limit of {self._max_guilds} guilds reached! Remove some guilds to add this one.")
                # Guild already pending
                if guild_ref in self._pending_guild:
                    message = self._pending_guild[guild_ref].get("pending_message")
                    if message and message.channel:
                        try:
                            await message.channel.send("Not available yet")
                            return None
                        except (NotFound, HTTPException) as err:
                            logger.info(err)
                    channel = await get_safe_text_channel(guild, name_key="BOARD", create=False)
                    await channel.send("Not available yet")
                    return None
                # New guild pending
                channel = await get_safe_text_channel(guild, name_key="BOARD", create=False)
                if channel:
                    try:
                        await channel.send(self._messages["ALREADY_ELSEWHERE"])
                    except (NotFound, HTTPException) as err:
                        logger.warning(f"Impossible to send message to channel {channel}: {err}")
                if len(self._pending_guild) > self._max_pending_guilds:
                    await guild.leave()
                else:
                    await self.show_pending_guild_panel(guild, channel)
                return None
            # Add the guild
            remove_bot_availability_on_website()
            guild_wrapper = GuildWrapper(self._bot, guild)
            guild_wrapper.listener_manager = ListenerManager(self, guild_wrapper)
            await guild_wrapper.listener_manager.self_start()
            await self._init_guild(guild_wrapper, versions=versions)
            self._guilds[guild_ref] = guild_wrapper
            self._pending_guild.pop(guild_ref, None)
            logger.info(f"Guild {guild_wrapper} initialized correctly!")
            return guild_wrapper

    async def remove_guild(self, guild_ref: Union[int, Guild, GuildWrapper], kick=False):
        if isinstance(guild_ref, (Guild, GuildWrapper)):
            guild_ref = guild_ref.id
        # Listeners no more referenced in AbstractGuildListener.instances
        AbstractGuildListener.reset_guild(guild_ref)
        # Listeners stop
        guild_wrapper = self.get_guild(guild_ref)
        if guild_wrapper:
            await guild_wrapper.clear_listeners()
        if kick:
            try:
                await guild_wrapper.leave()
            except HTTPException as err:
                logger.debug(f"Error on guild leave: {err}")
        # guild was removed from GuildManager, but the bot is still present
        if guild_ref in [guild.id for guild in self._bot.guilds]:
            await self.show_pending_guild_panel(self._bot.get_guild(guild_ref))
        # Object references are reset
        clear_object_references()
        # Guild reference is removed
        self._guilds.pop(guild_ref, None)
        add_bot_availability_on_website()
        logger.warning(f"Guild {guild_ref} was removed.")

    def get_guild(self, guild_ref: Union[int, Guild, GuildWrapper], default=None) -> Optional[GuildWrapper]:
        """Retrieve the GuildWrapper associated to guild_ref.

        :param guild_ref: can be a Guild object or a Guild id.
        :param default: default value if guild not found
        :return: the GuildWrapper associated to the guild_ref, if it exists, else default.
        """
        if isinstance(guild_ref, (Guild, GuildWrapper)):
            guild_ref = guild_ref.id
        return self._guilds.get(guild_ref, default)

    @staticmethod
    async def update_guild(guild, origin_channel: TextChannel = None, force=False, clear_references=True):
        force_str = ' (forced update)' if force else ''
        logger.debug(f"Updating roles and channels!{force_str}")
        bot_msg = None
        try:
            bot_msg = await origin_channel.send(f"Updating roles and channels{force_str}...")
        except NotFound:
            pass
        errors = []

        # Roles + ensure the bot has the BOT role
        # (necessary for role hierarchy, because the automatic bot role has bad position (bug in discord.py ?))
        if RoleCollection.BOT.object_reference and not RoleCollection.BOT.has_the_role(guild.me):
            await guild.me.edit(roles=guild.me.roles + [RoleCollection.BOT.object_reference])
        if not await update_guild_roles(guild, delete_old=force, clear_references=clear_references):
            errors.append("guild roles")
        if RoleCollection.BOT.object_reference and not RoleCollection.BOT.has_the_role(guild.me):
            await guild.me.edit(roles=guild.me.roles + [RoleCollection.BOT.object_reference])

        # Channels + ensure the board is always present
        board_channel_reference = getattr(getattr(ChannelCollection.get("BOARD"), "object_reference", None), "id", None)
        if not await update_guild_channels(guild, delete_old=force, clear_references=clear_references):
            errors.append("guild channels")
        new_board_channel_reference = getattr(getattr(ChannelCollection.get("BOARD"), "object_reference", None), "id",
                                              None)
        if board_channel_reference != new_board_channel_reference:
            logger.info("Board channel has just changed! Creating a new board...")
            await GuildManager().get_guild(guild).show_control_panel()

        # Guild + bot + webhooks
        if not await update_guild_properties(guild):
            errors.append("guild properties")

        errors_str = "" if not errors else "\nERRORS (please check the server with ✅): " + ", ".join(errors)
        try:
            if bot_msg:
                await bot_msg.edit(content=f"Roles and channels updated!{force_str}{errors_str}")
        except discord.NotFound:
            pass
        logger.debug(f"Roles and channels updated!{force_str}{errors_str}")

    @classmethod
    async def reset_all_channels(cls, guild: Union[Guild, GuildWrapper], origin_channel=None):
        await delete_channels(guild)
        return await cls.update_guild(guild, origin_channel=origin_channel, clear_references=True)

    # HANDLE PENDING GUILDS
    async def show_pending_guild_panel(self, guild: Guild, channel: TextChannel = None):
        if not guild:
            return
        if channel is None or channel not in guild.channels or not isinstance(channel, TextChannel):
            channel = await get_safe_text_channel(guild, "BOARD", create=False)
        pending_message = await channel.send(self._messages["PENDING_GUILD_OPTIONS"])
        self._pending_guild[guild.id] = {"position": len(self._pending_guild),
                                         "pending_message": pending_message,
                                         "waiting_for_password": False}
        for enum_inst in PendingOptions:
            await pending_message.add_reaction(enum_inst.value)

    async def handle_pending_guild_message(self, message: Message):
        if message.author.bot:
            return
        if message.guild.id not in self._pending_guild:
            return
        if not self._pending_guild[message.guild.id]:
            return
        if not self._pending_guild[message.guild.id]["waiting_for_password"]:
            return
        self._pending_guild[message.guild.id]["waiting_for_password"] = False
        if message.content == PASSWORD_REMOVE_BOT:
            logger.warning(f"Removing bot from its guilds: {self._bot.guilds}")
            msg = await message.channel.send("Removing bot from other guilds....")
            for guild_id in list(self.keys()):
                await self.remove_guild(guild_id)
            await msg.edit(content="The bot was removed from other guilds. You can try again!")
        elif message.content == PASSWORD_KICK_BOT:
            logger.warning(f"Kicking bot from its guilds: {self._bot.guilds}")
            msg = await message.channel.send("Kicking bot from other guilds....")
            for guild_id in list(self.keys()):
                await self.remove_guild(guild_id, kick=True)
            await msg.edit(content="The bot was kicked from other guilds. You can try again!")
        else:
            logger.warning(f"Bad password to kick bot from its guilds! User: {message.author} in guild {message.guild}")
            await message.channel.send("Bad password! Try again (button must be pressed again)")

    async def handle_pending_guild_reaction_add(self, reaction: Reaction, user: Member):
        if user.bot:
            return
        guild: Guild = reaction.message.guild
        if guild.id not in self._pending_guild:
            return
        if reaction.message.id != getattr(self._pending_guild[guild.id].get("pending_message", None), "id", None):
            return
        if reaction.emoji == PendingOptions.quit.value:
            logger.info(f"User {user} asked the bot to leave the guild {guild}.")
            await reaction.message.channel.send("Leaving guild... Bye!")
            await guild.leave()
            self._pending_guild.pop(guild.id, None)
        elif reaction.emoji == PendingOptions.try_again.value:
            logger.info(f"User {user} asked to add its guild {guild} again.")
            msg = await reaction.message.channel.send("Retrying to add guild...")
            if await self.add_guild(guild):
                await msg.edit(content="Guild added successfully!")
        elif reaction.emoji == PendingOptions.force.value:
            logger.info(f"User {user} of guild {guild} asked to kick bot from other guilds.")
            await reaction.message.channel.send("Please enter the password to kick bot from other guilds.")
            self._pending_guild[guild.id]["waiting_for_password"] = True
        else:
            logger.debug(f"Bad reaction {reaction} for message id {reaction.message.id}")

    def __iter__(self):
        for guild_id in self._guilds:
            return guild_id

    def keys(self):
        return self._guilds.keys()

    def values(self):
        return self._guilds.values()

    def items(self):
        return self._guilds.items()

    def __contains__(self, item: Union[int, Guild, GuildWrapper]):
        if isinstance(item, int):
            return item in self._guilds
        if isinstance(item, (Guild, GuildWrapper)):
            return item.id in self._guilds
        return False

    def __len__(self):
        return len(self._guilds)

    def __getitem__(self, item):
        return self.get_guild(guild_ref=item, default=None)
