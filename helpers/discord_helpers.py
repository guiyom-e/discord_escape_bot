import inspect
from typing import Union, Awaitable, Any, Optional

import discord
from discord import Guild, CategoryChannel, Message, Reaction

from logger import logger

MAX_MSG_SIZE = 2000


async def return_(result_maybe_awaitable: Union[Any, Awaitable[Any]]):
    if inspect.isawaitable(result_maybe_awaitable):
        result_maybe_awaitable = await result_maybe_awaitable
    return result_maybe_awaitable


def user_to_member(guild: Union[Guild, 'GuildWrapper'], user: discord.User):
    """Convert a user to a member (which has more attributes)"""
    if guild is None:
        return None
    for member in guild.members:
        if member.id == user.id:
            return member
    if not user.bot:  # webhooks are not members
        logger.warning(f"User {user} not found in current guild!")
    return None


def find_other_channel_in_same_category(category: Optional[CategoryChannel], channel_name_pattern):
    if category is None:
        channels = []
    else:
        channels = [channel for channel in category.channels if channel_name_pattern in channel.name]
    if not channels:
        logger.error(f"Channel with pattern {channel_name_pattern} in category {category} doesn't exist!")
        return None
    if len(channels) > 1:
        logger.warning(f"More than one channel with the pattern {channel_name_pattern} in category {category}! "
                       f"Only the first is used.")
    return channels[0]


async def try_to_delete_message(message: Message, delay: int = None):
    try:
        await message.delete(delay=delay)
    except Exception as err:
        logger.debug(f"Failed to delete message {message}: {err}")


async def try_to_remove_emoji_on_message(message: Message, emoji, user):
    try:
        await message.remove_reaction(emoji, user)
    except Exception as err:
        logger.debug(f"Failed to remove reaction {emoji} of user {user} in message {message}: {err}")


async def try_to_remove_reaction(reaction: Reaction, user):
    try:
        await reaction.remove(user)
    except Exception as err:
        logger.debug(f"Failed to remove reaction {reaction} of user {user}: {err}")
