from typing import List, Union

from discord import TextChannel
from discord.abc import GuildChannel

from constants import BOT
from default_collections import RoleCollection, CategoryChannelCollection, ChannelCollection, CharacterCollection, \
    GuildCollection
from helpers import (format_list, format_message, long_send, get_guild_info, get_channels_info,
                     get_roles_info, get_members_info)
from helpers.commands_helpers import find_channel_mentions_in_message
from helpers.message_helpers import safe_send
from helpers.set_channels import fetch_channels
from helpers.set_roles import fetch_roles
from logger import logger
from models import ChannelDescription


async def fetch(guild):
    await fetch_roles(guild, RoleCollection.to_list())
    await fetch_channels(guild, CategoryChannelCollection.to_list())
    await fetch_channels(guild, ChannelCollection.to_list())
    logger.debug("Channels fetched")


def filter_channels(channels: List[GuildChannel], ignore: List[Union[GuildChannel, ChannelDescription]],
                    force: List[Union[GuildChannel, ChannelDescription]]):
    filtered_channels = []
    ignore = [ch.object_reference if isinstance(ch, ChannelDescription) else ch for ch in ignore]
    force = [ch.object_reference if isinstance(ch, ChannelDescription) else ch for ch in force]
    for channel in channels:
        if channel in force or getattr(channel, "category", None) in force:
            filtered_channels.append(channel)
            continue
        if channel in ignore or getattr(channel, "category", None) in ignore:
            continue  # ignore
        filtered_channels.append(channel)
    return filtered_channels


async def clean_channels(channels, limit=None, ignore="default", force=None):
    if ignore == "default":
        ignore = [CategoryChannelCollection.MASTER.value, CategoryChannelCollection.DEV.value]
    ignore = ignore or []
    force = force or []
    filtered_channels = filter_channels(channels, ignore, force)
    logger.info(f"Cleaning channels {filtered_channels}")
    result = True
    for channel_enum in ChannelCollection.to_list():
        channel = channel_enum.value.object_reference
        if channel is None or channel not in filtered_channels:
            continue
        if not await clean_channel(channel, limit):
            result = False
    logger.info("Channels cleared!")
    return result


async def clean_channel(channel: TextChannel, limit: int = None):
    """Remove messages of the channel (up to the limit, 1000 per default)

    You must have the manage_messages permission to delete messages.
    The read_message_history permission is also needed to retrieve message history.
    """
    if not isinstance(channel, TextChannel) or channel not in channel.guild.channels:
        logger.debug(f"Cannot reset a {channel.__class__.__name__} channel, only TextChannel types supported.")
        return False
    await safe_send(channel, f"Deleting messages (up to {limit})...")
    await channel.purge(limit=limit)
    logger.debug(f"Maximum {limit} messages deleted")
    return True


async def delete_channel(channel, reason=None):
    await channel.delete(reason=reason)


async def show_messages(message, args):
    channels = find_channel_mentions_in_message(message, args)
    for channel in channels:
        limit = int(args[0]) if args else 10
        messages = await channel.history(limit=limit).flatten()
        shorten_size = int(args[1]) if len(args) > 1 else 50
        msg = format_list([format_message(msg, shorten_size=shorten_size) for msg in messages])
        await long_send(message.channel, msg, quotes=False)


async def show_roles(message):
    await long_send(message.channel, RoleCollection.to_str(), quotes=True)


async def show_channels(channel: TextChannel):
    await long_send(channel, CategoryChannelCollection.to_str() + "\n" + ChannelCollection.to_str(), quotes=True)


async def show_info(channel: TextChannel):
    await long_send(channel, get_guild_info(BOT, channel.guild), quotes=True)
    await long_send(channel, get_channels_info(channel.guild), quotes=True)
    await long_send(channel, get_roles_info(channel.guild), quotes=True)
    await long_send(channel, get_members_info(channel.guild), quotes=True)


def clear_object_references():
    RoleCollection.reset_object_references()
    ChannelCollection.reset_object_references()
    CategoryChannelCollection.reset_object_references()
    CharacterCollection.reset_object_references()
    GuildCollection.reset_object_references()
