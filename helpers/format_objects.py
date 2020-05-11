from typing import Union

from discord import Member, User, Message
from discord.abc import GuildChannel, PrivateChannel


def format_channel(channel, pretty=False):
    if channel is None or not isinstance(channel, (GuildChannel, PrivateChannel)):
        return "None"
    if pretty:
        return f"{getattr(channel, 'mention', 'UnknownChannel')} ({getattr(channel, 'category', 'NoCategory')})"
    res = f"<{channel.__class__.__name__} id={channel.id} name={getattr(channel, 'name', 'NotAGuildChannel!')} " \
          f"category={getattr(channel, 'category', 'NoCategory')}>"
    return res


def format_member(member: Union[Member, User]):
    res = f"<{member.__class__.__name__} id={member.id} status={getattr(member, 'status', 'Unknown')} "
    res += f"complete_name={member.name}#{member.discriminator} nick={getattr(member, 'nick', 'NotInAGuild!')}>"
    return res


def format_message(message: Message, shorten_size=-1, short=True):
    if short:
        return f"<{message.__class__.__name__} id={message.id} '{message.content[:shorten_size]}'>"
    res = f"<{message.__class__.__name__} id={message.id} channel={format_channel(message.channel)}\n"
    res += f"author={format_member(message.author)}\ncontent={message.content[:shorten_size]}\n>"
    return res


def format_role(role):
    return f"{role.__repr__()} (#{role.position})"


def format_list(ls):
    res = ""
    for ele in ls:
        res += f"{ele}\n"
    return res


def format_dict(dico):
    res = ""
    for k, v in dico.items():
        res += f"{k}: {v}\n"
    return res


def get_guild_info(bot, guild):
    return f'Bot {bot.user} is connected to the following guilds: {bot.guilds}\nActive guild: {guild}'


def get_members_info(guild):
    members = '\n - '.join(
        [f"{member.name} AKA {member.display_name} ({member.id})[{member.roles}]" for member in
         guild.members])
    return f'Guild Members:\n - {members}'


def get_roles_info(guild):
    roles = '\n * '.join([format_role(role) for role in guild.roles])
    return f"Available roles:\n * {roles}"


def get_channels_info(guild):
    channels = '\n > '.join([format_channel(channel) for channel in guild.channels])
    return f"Guild channels:\n > {channels}"
