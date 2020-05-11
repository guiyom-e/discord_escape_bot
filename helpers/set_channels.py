import asyncio
from typing import List, Union, Tuple

from discord import Guild
from discord.abc import GuildChannel

from logger import logger
from models import ChannelDescription
from models.abstract_models import reorder_items
from models.guilds import GuildWrapper

LOCK = asyncio.Lock()


async def create_channels(guild: Union[Guild, GuildWrapper], channel_descriptions: List[ChannelDescription]):
    # You must have the manage_channels permission to do this.
    for channel_description in channel_descriptions:
        await channel_description.create_object(guild)


async def edit_channels(old_channels: List[GuildChannel], new_channels_descriptions: List[ChannelDescription]):
    # You must have the manage_channels permission to do this.
    for channel, channel_description in zip(old_channels, new_channels_descriptions):
        await channel_description.update_object(channel)


async def delete_channels(guild: Union[Guild, GuildWrapper], reason=None):
    # You must have the manage_channels permission to do this.
    for channel in guild.channels:
        await channel.delete(reason=reason)


def clear_channel_descriptions(channel_descriptions: List[ChannelDescription], clear_category=True):
    """Clear object references of ChannelDescription objects (including references of categories if clear_category)"""
    for channel_description in channel_descriptions:
        channel_description.object_reference = None
        if clear_category and channel_description.category_description:
            channel_description.category_description.object_reference = None


async def update_channels(guild: Union[Guild, GuildWrapper], channel_descriptions: List[ChannelDescription],
                          delete_old=True, key="name", reorder=True, clear_references=True) -> bool:
    return await fetch_channels(guild, channel_descriptions, key=key, clear_references=clear_references,
                                check_category=True, update=True, create=True, delete_old=delete_old, reorder=reorder)


def _assign_channel(ind_to_pop: List[Tuple[int, GuildChannel]], guild_channels: List[GuildChannel],
                    channel_description: ChannelDescription, key: str, strict=True):
    """Set the ChannelDescription.object_reference to one channel in ind_to_pop,
    preferably (or only, if strict=True) if the channel is in the expected category."""
    # WARN: ChannelDescription objects representing CategoryChannel channels must be assigned prior to other channels!
    for i, channel in ind_to_pop:  # check if categories match
        if channel.category is None and channel_description.category is None:
            channel_description.object_reference = channel
            guild_channels.pop(i)
            if len([_channel for _i, _channel in ind_to_pop if _channel.category is None]) > 1:
                logger.warning(f"Multiple guild channels with no category correspond to {channel_description} "
                               f"for key '{key}'. The first one in guild_channels (arbitrary order) is taken.")
            return channel
        if (channel.category
                and getattr(channel.category, key) == getattr(channel_description.category_description, key, None)):
            channel_description.object_reference = channel
            channel_description.category_description.object_reference = channel.category
            guild_channels.pop(i)
            if len([_channel for _i, _channel in ind_to_pop
                    if getattr(_channel.category, key, None) == getattr(channel_description, key, None)]) > 1:
                logger.warning(f"Multiple guild channels with category {channel.category} correspond to "
                               f"{channel_description} for key '{key}'. "
                               f"The first one in guild_channels (arbitrary order) is taken.")
            return channel
    if len(ind_to_pop) > 1:
        logger.warning(f"More than one channel ({len(ind_to_pop)}) correspond to {channel_description} in the guild "
                       f"and no matching category was found!"
                       f"{'Nothing set!' if strict else 'The first one in guild_channels (arbitrary order) is taken.'}")
    if strict:
        return None
    else:
        # if no category is matching, use the first channel found. In general, it is a bad thing!
        ind, channel = ind_to_pop[0]
        channel_description.object_reference = channel
        guild_channels.pop(ind)
        return channel


async def fetch_channels(guild, channel_descriptions: List[ChannelDescription],
                         key: str = "name", clear_references=True,
                         check_category=True, update=False, create=False, delete_old=False, reorder=False) -> bool:
    """Detect existing channels and set them to ChannelDescription.object_reference attribute.

    :param guild: Guild
    :param channel_descriptions: list of channel descriptions
    :param key: matching key between guild channels and channel_descriptions. Default and recommended is 'name'. Note that the channel type must always match whatever is the key.
    :param clear_references: if True, reset pre-existing object references. True RECOMMENDED.
    :param check_category: if True, check strictly the category (after the key matching). If False, check the category, but take an arbitrary channel if the category doesn't match. True RECOMMENDED.
    :param update: if True, update channels found with channel description
    :param create: if True, create missing channels
    :param delete_old: if True, channels that are not in channel_descriptions list are deleted
    :param reorder: if True, channels are reordered in the order they appear in channel_descriptions
    :return: True if fetch/update was correct, False if at least one error was found.
    """
    # Sort by Category (ChannelType value: 4), then VoiceChannel (2), then TextChannel (0)
    channel_descriptions = sorted(channel_descriptions, key=lambda cd: - cd.channel_type.value)
    async with LOCK:  # Lock channel_descriptions
        channels_ok = True
        if clear_references:  # clear pre-existing object references
            clear_channel_descriptions(channel_descriptions)
        guild_channels = guild.channels
        for channel_description in channel_descriptions:
            # if the object reference already exists.
            if channel_description.object_reference and update:
                if await channel_description.update_object(channel_description.object_reference):
                    continue

            c_d_value = getattr(channel_description, key)
            ind_to_pop = []
            # Check matching channels in guild channels
            for i, channel in enumerate(guild_channels):
                if getattr(channel, key) == c_d_value and channel.type is channel_description.channel_type:
                    ind_to_pop.append((i, channel))
                    continue
            if ind_to_pop:  # assign object_reference to channel + remove channel attributed from guild_channels
                channel = _assign_channel(ind_to_pop, guild_channels, channel_description, key, strict=check_category)
                if channel and update:
                    await channel_description.update_object(channel)
            if channel_description.object_reference is None:  # channel not found
                if create:
                    await channel_description.create_object(guild)
                else:
                    logger.debug(f"WARN: Channel {channel_description} doesn't exist in the guild!")
                    channels_ok = False
        if channels_ok:
            logger.info(f"Channels {'updated' if update else 'fetched'} successfully: {channel_descriptions}")
        else:
            logger.warning(f"Channels {'updated' if update else 'fetched'} with errors: {channel_descriptions}")
        if reorder:
            if not await reorder_items(channel_descriptions):
                channels_ok = False
                logger.warning("Channels reordered with errors")
            else:
                logger.info("Channels reordered successfully")
        if delete_old:
            references = [ch_d.object_reference for ch_d in channel_descriptions]
            for channel in guild_channels:
                if channel not in references:
                    await channel.delete(reason="fetch_channels: delete_old arg is True")
        return channels_ok
