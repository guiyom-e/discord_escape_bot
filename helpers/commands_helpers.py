# -*- coding: utf-8 -*-
import re
from typing import Sequence, List

from discord import Message

from logger import logger


def get_args_from_text(content: str, sep: str = r"\s", string_delimiter=r'".+?"') -> Sequence[str]:
    """Returns a list of args given a text content.

    Example:

    >>> get_args_from_text(' My name   is "Stephan Harper". <"Oh">  Hey"!   ')
    ('My', 'name', 'is', '"Stephan Harper"', '.', '<', '"Oh"', '>', 'Hey"!')
    """
    texts = re.findall(string_delimiter, content)
    others = []
    for ele in re.split(string_delimiter, content):
        others += re.split(sep, ele)
    args = []
    end = False
    i, i_t, i_o = 0, 0, 0
    while not end:
        if i_t < len(texts) and texts[i_t] == content[i:i + len(texts[i_t])]:
            args.append(texts[i_t])
            i += len(texts[i_t])
            i_t += 1
        elif re.match(sep, content[i:]) and re.match(sep, content[i:]).start() == 0:
            # ignore it
            i += re.match(sep, content[i:]).end()
        elif i_o < len(others) and others[i_o] == content[i:i + len(others[i_o])]:
            args.append(others[i_o])
            i += len(others[i_o])
            i_o += 1
        else:
            end = True
    for i, arg in enumerate(args):
        args[i] = arg.strip()
    return tuple(filter(None, args))


def is_int(value):
    try:
        int(value)
    except Exception as err:
        logger.debug(f"{value} is not an int: {err}")
        return False
    else:
        return True


def find_channel_mentions_in_message(message: Message, args: List[str], delete_channel_args=True,
                                     message_channel_if_not_found=True, only_first_args=False):
    channels = message.channel_mentions
    to_pop, matches = [], []
    for i, arg in enumerate(args):
        match = re.match(r"<#[0-9]+>", arg)
        if match:
            to_pop.append(i)
            matches.append(match.group())
        elif only_first_args:
            break
    if len(channels) != len(to_pop) and not only_first_args:
        logger.warning(f"Incorrect channel mention args for message {message}")
    to_pop.reverse()
    channel_ids = []
    for i, match in zip(to_pop, matches):
        if delete_channel_args:
            args.pop(i)
        channel_ids.append(int(match[2:-1]))
    if not channel_ids and message_channel_if_not_found:
        return [message.channel]
    return [message.guild.get_channel(ch_id) for ch_id in channel_ids[::-1]]


def infer_channels_from_message(message: Message, args: List[str]):
    return find_channel_mentions_in_message(message, args, message_channel_if_not_found=True)
