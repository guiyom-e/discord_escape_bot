import inspect
from collections import defaultdict
from typing import Union, Callable, Coroutine, Optional

import discord
from discord import Forbidden, InvalidArgument, HTTPException, User, Member, NotFound, Message, TextChannel

from helpers.discord_helpers import MAX_MSG_SIZE
from logger import logger

PENDING_DM_MESSAGES = defaultdict(list)


async def send_dm_message(user: Union[Member, User], message: Union[str, dict], origin_channel=None,
                          callback_on_forbidden_error: Union[Callable, Coroutine] = None,
                          keep_pending_message_on_forbidden_error=True):
    if user.bot:
        return
    if isinstance(message, str):
        message = {"content": message}
    try:
        await user.send(**message)
    except Forbidden as err:
        # You do not have the proper permissions to send the message.
        if keep_pending_message_on_forbidden_error:
            PENDING_DM_MESSAGES[user].append(message)
        if callback_on_forbidden_error:
            _res = callback_on_forbidden_error(err, user, origin_channel)
            if inspect.isawaitable(_res):
                await _res
    except InvalidArgument as err:
        #  The files list is not of the appropriate size or you specified both file and files.
        logger.error(f"InvalidArgument for message: {message}")
        logger.exception(err)
    except AttributeError as err:
        #  Invalid user
        logger.error(f"AttributeError for message: {message}")
        logger.exception(err)
    except HTTPException as err:
        # Sending the message failed.
        logger.error(f"HTTPException for message: {message}")
        logger.exception(err)
        PENDING_DM_MESSAGES[user].append(message)


async def send_dm_pending_messages(user: Union[Member, User]):
    pending_msg = PENDING_DM_MESSAGES.get(user, [])
    for i in range(len(pending_msg)):
        msg = pending_msg.pop(0)
        await send_dm_message(user, msg)
    return True


async def safe_send(channel: discord.abc.Messageable, *args, allow_long_send=True, **kwargs):
    """Send a message without raising error."""
    if not isinstance(channel, discord.abc.Messageable):
        logger.debug(f"Cannot send a message to {channel.__class__.__name__}, only discord.abc.Messageable supported.")
        return False
    content = kwargs.get("content", args[0] if args else "")
    try:
        if len(content) > MAX_MSG_SIZE and allow_long_send:
            message = await long_send(channel, content, quotes=False)
        else:
            message = await channel.send(*args, **kwargs)
    except TypeError as err:
        logger.warning(f"TypeError (bad arguments ?): {err}")
    except Forbidden as err:
        logger.debug(f"You do not have the proper permissions to send the message: {err}")
    except NotFound as err:
        logger.debug(f"Not found error: {err}")
    except HTTPException as err:
        logger.debug(f"Sending the message failed: {err}")
    except InvalidArgument as err:
        logger.debug(f"The files list is not of the appropriate size or you specified both file and files: {err}")
    else:
        return message
    return None


def _split_message(message, quotes=False):
    max_size = MAX_MSG_SIZE - 8 if quotes else MAX_MSG_SIZE
    message = str(message)
    res = []
    for i in range(len(message) // max_size + 1):
        msg = message[max_size * i:max_size * (i + 1)]
        if quotes:
            msg = f"```\n{msg}\n```"
        res.append(msg)
    return res


def _split_on_new_lines_message(message, quotes=False):
    max_size = MAX_MSG_SIZE - 8 if quotes else MAX_MSG_SIZE
    start_ind = int(0.7 * MAX_MSG_SIZE)  # 30% of 2000
    res = []
    buffer = str(message)
    while buffer:
        search_str = buffer[start_ind: max_size][::-1]
        ind_to_cut = search_str.find("\n")
        if ind_to_cut == -1:
            ind_to_cut = max_size
        else:
            ind_to_cut = max_size - 1 - ind_to_cut
        msg = buffer[0:ind_to_cut]
        buffer = buffer[ind_to_cut:]
        if quotes:
            msg = f"```\n{msg}\n```"
        res.append(msg)
    return res


async def _send_embed(channel, messages, **kwargs):
    if kwargs.pop('description', None):
        logger.debug(f"Invalid arg 'description': message is used as description")
    res = None
    for i, msg in enumerate(messages):
        embed = discord.Embed(description=msg, **kwargs)
        if not i:
            kwargs.pop('title', None)
        res = await channel.send(embed=embed)
    return res


async def long_send(channel: discord.abc.Messageable, message: str,
                    quotes=False, cut_on_new_line=True, embed=False, **kwargs) -> Optional[Message]:
    """Send multiples messages for long contents. Returns the last message sent if one."""
    if cut_on_new_line:
        messages = _split_on_new_lines_message(message, quotes)
    else:
        messages = _split_message(message, quotes)
    if embed and (isinstance(channel, TextChannel) and channel.permissions_for(channel.guild.me).embed_links):
        return await _send_embed(channel, messages, **kwargs)
    else:
        res = None
        for msg in messages:
            res = await channel.send(msg)
        return res
