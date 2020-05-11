# bot.py
# MAIN FILE
import asyncio
import datetime
import random
import traceback
from typing import Union, List, Optional

import discord
import requests
from aiohttp import ClientConnectorError
from discord import Member, Message, User, Guild, Reaction, VoiceState, RawReactionActionEvent

from bot_management import GuildManager, get_safe_text_channel
from constants import (_TOKEN, BOT, DEBUG_MODE, AWAKE_REFRESH_PERIOD, WEBSITE, MAX_GUILDS, MAX_PENDING_GUILDS,
                       GAME_LANGUAGE, VERBOSE)
from default_collections import RoleCollection, CategoryChannelCollection, ChannelCollection, MinigameCollection
from game_models import AbstractListener
from helpers import (format_member, format_message, get_guild_info, get_members_info,
                     get_roles_info, get_channels_info, send_dm_pending_messages)
from helpers.bot_availability import add_bot_availability_on_website, remove_bot_availability_on_website
from helpers.set_channels import fetch_channels
from helpers.set_roles import fetch_roles
from listeners_configuration import ListenersEnum, UtilsList
from logger import logger
from models import Event, GuildWrapper


############################
# Initialization functions #
############################

async def stay_awake(guild, duration):
    """Checks regularly if the website is up. Important in production mode."""
    while BOT_STAYING_AWAKE:
        logger.info("Staying awake !")
        channel = await get_safe_text_channel(guild, name_key="LOG")
        try:
            requests.get(WEBSITE)
        except Exception as err:
            logger.error(f"Error while staying awake! The website {WEBSITE} may be down: {err}")
            if channel and VERBOSE:
                await channel.send(f"I am here ! But the website {WEBSITE} may be down: {err}")
        else:
            logger.debug("Bot stays awake !")
            if channel:
                await channel.send(f"I am here ! And the website {WEBSITE} too !")
            # Update bot availability (in case it is not up-to-date, which can happen in production mode)
            if BOT.guilds:
                remove_bot_availability_on_website()
            else:
                add_bot_availability_on_website()
        await asyncio.sleep(duration - random.randint(0, 10))


async def init_guild(guild_wrapper) -> bool:
    """Coroutine to initialize a new a guild or to reset it when the version has changed."""
    # Print information on the guild
    logger.info(get_guild_info(BOT, guild_wrapper))
    logger.info(get_members_info(guild_wrapper))
    logger.info(get_roles_info(guild_wrapper))
    logger.info(get_channels_info(guild_wrapper))

    # Get existing channels and roles, but do not set/create/update anything
    await fetch_roles(guild_wrapper, RoleCollection.to_list())
    await fetch_channels(guild_wrapper, CategoryChannelCollection.to_list())
    await fetch_channels(guild_wrapper, ChannelCollection.to_list())

    # Add guild listeners and show the control panel
    await guild_wrapper.add_listeners(UtilsList(guild_wrapper))  # add utils
    await guild_wrapper.add_listeners(MinigameCollection.get_guild_instances(guild_wrapper))  # add minigames
    await guild_wrapper.listener_manager.show_control_panel(guild_wrapper.guild)  # show control panel

    # Send a success message
    try:
        channel = await get_safe_text_channel(guild_wrapper.guild, "BOARD", create=False)
        await channel.send("Bot redémarré !")
    except discord.DiscordException as err:
        logger.error(f"Failed to send reboot message: {err}")
        return False
    else:
        logger.info("Guild initialized successfully")
        return True


async def init_bot():
    """Coroutine to initialize the bot once it is ready for the first time."""
    logger.info("Bot initialization")
    # Add the enum of all available listeners
    MinigameCollection.set_listener_enum(ListenersEnum)
    # Initialize all available guilds
    is_ok = await GuildManager().init_guilds(GAME_LANGUAGE)
    if is_ok:
        logger.info("Bot initialized correctly!")
    else:
        logger.critical("Bot initialization failure!")


#########################
# Handle Discord events #
#########################

# Dispatch Discord events to guilds and listeners

async def handle_event(listener: AbstractListener, event: Event, *args, **kwargs):
    """Trigger the dedicated method in listener to handle Discord event."""
    await getattr(listener, event.value)(*args, **kwargs)


async def handle_event_in_all_listeners(guild_wrapper: GuildWrapper, event: Event, *args, **kwargs):
    """Handle the Discord event in all listeners of the guild."""
    for listener in guild_wrapper.active_listeners.copy():  # Copy to avoid Runtime error on item removal
        await handle_event(listener, event, *args, **kwargs)


async def handle_event_in_all_guilds(guild: Optional[Guild], event: Event, *args, **kwargs):
    """Handle the Discord event in all listeners of the concerned guilds."""
    await asyncio.gather(*(handle_event_in_all_listeners(guild_wrapper, event, *args, **kwargs)
                           for guild_wrapper in GuildManager().values() if guild_wrapper == guild or guild is None))


# Discord events

@BOT.event
async def on_guild_join(guild):
    logger.info(f"Bot joined a new guild: {guild}")
    await GuildManager().add_guild(guild, versions=GAME_LANGUAGE)
    # In production mode: ensure the bot stays awake
    global BOT_STAYING_AWAKE
    if not BOT_STAYING_AWAKE and not DEBUG_MODE:
        for guild_wrapper in GuildManager().values():  # do it for the first guild found
            logger.info("Starting awakening coroutine...")
            BOT_STAYING_AWAKE = True
            return await stay_awake(guild_wrapper, AWAKE_REFRESH_PERIOD)


@BOT.event
async def on_guild_remove(guild):
    logger.info(f"Bot was removed from the guild: {guild}")
    await GuildManager().remove_guild(guild)
    global BOT_STAYING_AWAKE
    BOT_STAYING_AWAKE = False


@BOT.event
async def on_ready():
    logger.info(f"Bot ready!")
    global BOT_INITIALIZED
    if not BOT_INITIALIZED:
        BOT_INITIALIZED = True
        await init_bot()
    await handle_event_in_all_guilds(None, Event.READY)
    # In production mode: ensure the bot stays awake
    global BOT_STAYING_AWAKE
    if not BOT_STAYING_AWAKE and not DEBUG_MODE:
        logger.info("Starting awakening coroutine...")
        for guild_wrapper in GuildManager().values():  # do it for the first guild found
            BOT_STAYING_AWAKE = True
            return await stay_awake(guild_wrapper, AWAKE_REFRESH_PERIOD)


@BOT.event
async def on_error(event, *args, **kwargs):
    try:
        logger.error(f"Unhandled error in event: {event} with parameters\n{args}, {kwargs}"[-1500:])
        err_trace = str(traceback.format_exc())
        if len(err_trace) > 1500:
            logger.error(err_trace[:1500])
            logger.error("[...]")
            logger.error(err_trace[-1500:])
        else:
            logger.error(err_trace)
    except Exception as err:  # should not happen!
        logger.critical(f"Critical error after catching an unhandled error: {err}")


@BOT.event
async def on_connect():
    logger.info(f"Bot connected!")
    await handle_event_in_all_guilds(None, Event.CONNECT)


@BOT.event
async def on_disconnect():
    logger.info(f"Bot disconnected!")
    await handle_event_in_all_guilds(None, Event.DISCONNECT)


@BOT.event
async def on_member_join(member: Member):
    logger.info(f"{member} has just joined!")
    await handle_event_in_all_guilds(member.guild, Event.MEMBER_JOIN, member)


@BOT.event
async def on_member_remove(member: Member):
    logger.info(f"{member} has just left!")
    await handle_event_in_all_guilds(member.guild, Event.MEMBER_REMOVE, member)


@BOT.event
async def on_typing(channel: discord.abc.Messageable, user: Union[User, Member], when: datetime.datetime):
    # logger.debug(f"{format_member(user)} is typing in {format_channel(channel)} at {when}")
    await handle_event_in_all_guilds(getattr(channel, 'guild', None), Event.TYPING, channel, user, when)


@BOT.event
async def on_message_edit(before: Message, after: Message):
    logger.debug(f"Message {format_message(before)} edited to {format_message(after)}")
    await handle_event_in_all_guilds(before.guild, Event.MESSAGE_EDIT, before, after)


@BOT.event
async def on_reaction_add(reaction: Reaction, user: Union[Member, User]):
    logger.debug(f"The reaction {reaction} has been added to message "
                 f"{format_message(reaction.message, 50)} by {format_member(user)}")
    await handle_event_in_all_guilds(reaction.message.guild, Event.REACTION_ADD, reaction, user)
    await GuildManager().handle_pending_guild_reaction_add(reaction, user)


@BOT.event
async def on_raw_reaction_add(payload: RawReactionActionEvent):
    logger.debug(f"The raw reaction {payload} has been added")
    await handle_event_in_all_guilds(payload.guild_id, Event.RAW_REACTION_ADD, payload)


@BOT.event
async def on_raw_reaction_remove(payload: RawReactionActionEvent):
    logger.debug(f"The raw reaction {payload} has been added")
    await handle_event_in_all_guilds(payload.guild_id, Event.RAW_REACTION_REMOVE, payload)


@BOT.event
async def on_reaction_remove(reaction: Reaction, user: Union[Member, User]):
    logger.debug(f"The reaction {reaction} has been removed from message "
                 f"{format_message(reaction.message, 50)} by {format_member(user)}")
    await handle_event_in_all_guilds(reaction.message.guild, Event.REACTION_REMOVE, reaction, user)


@BOT.event
async def on_reaction_clear(message: Message, reactions: List[Reaction]):
    # logger.debug(f"All reactions {reactions} have been removed from message {format_message(message, 50)}")
    await handle_event_in_all_guilds(message.guild, Event.REACTION_CLEAR, message, reactions)


@BOT.event
async def on_member_update(before: Member, after: Member):
    logger.debug(f"Member {format_member(before)} updated to {format_member(after)}")
    await handle_event_in_all_guilds(before.guild, Event.MEMBER_UPDATE, before, after)


@BOT.event
async def on_member_ban(guild: Guild, user: Union[User, Member]):
    logger.debug(f"Member {format_member(user)} was banned from {guild}")
    await handle_event_in_all_guilds(guild, Event.MEMBER_BAN, guild, user)


@BOT.event
async def on_member_unban(guild: Guild, user: Union[User, Member]):
    logger.debug(f"Member {format_member(user)} was unbanned from {guild}")
    await handle_event_in_all_guilds(guild, Event.MEMBER_UNBAN, guild, user)


@BOT.event
async def on_message(message: Message):
    if message.author == BOT.user:
        return
    # logger.debug(f"Message received: {format_message(message, 100)}")

    if isinstance(message.channel, discord.GroupChannel):
        logger.warning("Group channels not supported for the moment !")
        return
    if isinstance(message.channel, discord.DMChannel):
        logger.debug("DM channels not fully supported for the moment !")
        await send_dm_pending_messages(message.author)
        return
    await handle_event_in_all_guilds(message.guild, Event.MESSAGE, message)
    await GuildManager().handle_pending_guild_message(message)


@BOT.event
async def on_voice_state_update(member: Member, before: VoiceState, after: VoiceState):
    logger.debug(f"Member {format_member(member)} changed its voice state from {before} to {after}")
    await handle_event_in_all_guilds(member.guild, Event.VOICE_STATE_UPDATE, member, before, after)


#################
# Main function #
#################

def main():
    logger.info("Bot starting")
    # Init singleton GuildManager
    _is_ok = GuildManager().set_bot(BOT, init_guild, max_guilds=MAX_GUILDS, max_pending_guilds=MAX_PENDING_GUILDS)
    if not _is_ok:
        logger.critical("Setting bot in GuildManager failed!")
    # Run the bot
    try:
        logger.info("Bot entering run loop...")
        BOT.run(_TOKEN)
    except ClientConnectorError as err:
        logger.error(f"Connection error, failed to connect: {err}")
        logger.exception(err)
    logger.info("Bot stopped")


if __name__ == '__main__':
    BOT_INITIALIZED = False
    BOT_STAYING_AWAKE = False
    main()
