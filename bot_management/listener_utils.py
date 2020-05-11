from typing import Tuple, Optional

from discord import TextChannel, Guild
from discord.abc import GuildChannel

from bot_management.guild_manager import GuildManager
from game_models import AbstractListener, ChannelMiniGame, AbstractMiniGame, AbstractUtils
from game_models.listener_collection import ListenerDescription
from helpers import format_channel, long_send
from helpers.commands_helpers import infer_channels_from_message
from helpers.discord_helpers import find_other_channel_in_same_category
from logger import logger
from models import ChannelDescription


def get_listener_from_args(guild, args, listener_type=AbstractListener) -> Tuple[int, Optional[AbstractListener]]:
    if not args:
        return -1, None
    guild_wrapper = GuildManager().get_guild(guild)
    try:
        listener_id = int(args[0])
    except (TypeError, ValueError, IndexError):
        return -1, None
    args.pop(0)  # remove the argument
    if 0 <= listener_id < len(guild_wrapper.listeners):
        listener = guild_wrapper.listeners[listener_id]
        if isinstance(listener, listener_type):
            return listener_id, listener
    return -1, None


async def start_channel_game(message, args):
    game_id, minigame = get_listener_from_args(message.guild, args, listener_type=ChannelMiniGame)
    if minigame:
        minigame: ChannelMiniGame
        channels = infer_channels_from_message(message, args)
        for channel in channels:
            await minigame.start_channel(channel)
            await message.channel.send(f"Starting game #{game_id} ({minigame.name}) "
                                       f"in channel {format_channel(channel)}")


async def stop_channel_game(message, args):
    game_id, minigame = get_listener_from_args(message.guild, args, listener_type=ChannelMiniGame)
    if minigame:
        minigame: ChannelMiniGame
        channels = infer_channels_from_message(message, args)
        for channel in channels:
            await minigame.stop_channel(channel)
            await message.channel.send(f"Stopping game #{game_id} ({minigame.name}) "
                                       f"in channel {format_channel(channel)}")


async def reset_channel_game(message, args):
    game_id, minigame = get_listener_from_args(message.guild, args, listener_type=ChannelMiniGame)
    if minigame:
        minigame: ChannelMiniGame
        channels = infer_channels_from_message(message, args)
        for channel in channels:
            minigame.channels[channel].reset()
            await message.channel.send(f"Resetting game #{game_id} ({minigame.name}) "
                                       f"in channel {format_channel(channel)}")


async def force_channel_victory(message, args):
    game_id, minigame = get_listener_from_args(message.guild, args, listener_type=ChannelMiniGame)
    if minigame:
        minigame: ChannelMiniGame
        channels = infer_channels_from_message(message, args)
        for channel in channels:
            await minigame.on_channel_helped_victory(channel)
            await message.channel.send(f"Forcing victory in game #{game_id} ({minigame.name}) "
                                       f"in channel {format_channel(channel)}")


async def stop_listener(message, args, listener_type=AbstractListener):
    listener_id, listener = get_listener_from_args(message.guild, args, listener_type=listener_type)
    if listener:
        await listener.stop()
        await message.channel.send(f"Stopping #{listener_id}: {listener.name}")


async def start_listener(message, args, listener_type=AbstractListener):
    game_id, listener = get_listener_from_args(message.guild, args, listener_type=listener_type)
    if listener:
        await listener.start()
        await message.channel.send(f"Starting #{game_id}: {listener.name}")


async def reload_listener_messages(message, args):
    game_id, listener = get_listener_from_args(message.guild, args, listener_type=AbstractListener)
    if "--update" in args:
        args.remove("--update")
        clear = False
    else:
        clear = True
    versions = args or None
    if listener:
        listener.reload(versions=versions, clear=clear)
        await message.channel.send(f"Reloading messages of #{game_id} to {versions if versions else 'default'}"
                                   f"{'' if clear else ' (update)'}: {listener.name}")


async def change_version(channel, versions, clear=True):
    await GuildManager().change_guild_version(channel.guild, versions, clear, origin_channel=None)


async def force_victory(message, args):
    game_id, minigame = get_listener_from_args(message.guild, args, listener_type=AbstractMiniGame)
    if minigame:
        minigame: AbstractMiniGame
        await minigame.on_helped_victory()
        await message.channel.send(f"Forcing victory in game #{game_id}: {minigame.name}")


async def game_board(channel: TextChannel):
    guild_wrapper = GuildManager().get_guild(channel.guild)
    await guild_wrapper.listener_manager.show_listeners(channel, AbstractMiniGame)


async def admin_board(channel: TextChannel):
    guild_wrapper = GuildManager().get_guild(channel.guild)
    await guild_wrapper.listener_manager.show_listeners(channel, AbstractUtils)


async def control_panel(guild: Guild):
    guild_wrapper = GuildManager().get_guild(guild)
    await guild_wrapper.listener_manager.show_control_panel(guild)


async def show_listeners_list(channel, listener_type=AbstractListener):
    guild_wrapper = GuildManager().get_guild(channel.guild)
    res = "- "
    res += "\n- ".join([f"{i if i > 9 else f'0{i}'}: {listener.name} ({listener.description[:50]}...)"
                        for i, listener in enumerate(guild_wrapper.listeners) if isinstance(listener, listener_type)])
    await long_send(channel, f"Mini-games allowed [type {listener_type.__name__}]:\n{res}")


async def start_next_minigame(origin_channel: GuildChannel, next_channel_description: ChannelDescription,
                              next_minigame_description: ListenerDescription) -> Optional[GuildChannel]:
    if origin_channel is None or next_channel_description is None or next_minigame_description is None:
        logger.debug("No next minigame to start !")
        return None
    # Auto-detection of the next channel, in the same category
    next_channel = find_other_channel_in_same_category(origin_channel.category, next_channel_description.name)
    if not next_channel:
        logger.error(f"Impossible to find the channel with description {next_channel_description} "
                     f"in the same category")
        return None
    next_minigame = next_minigame_description.object_reference
    if not next_minigame or not isinstance(next_minigame, ChannelMiniGame):
        logger.warning(f"Invalid minigame {next_minigame.name} for description {next_minigame_description}! "
                       f"A ChannelMiniGame is necessary!")
        return None
    if not next_minigame.instances(next_channel.guild):
        logger.warning(f"No {next_minigame_description} running: impossible to start it automatically !")
    logger.debug(f"'Next' mini-game {next_minigame_description} starting in channel {next_channel}...")
    for mini_game in next_minigame.instances(next_channel.guild):
        await mini_game.start()
        await mini_game.start_channel(next_channel)
        logger.debug(f"'Next' mini-game instance {next_minigame_description} started in channel {next_channel}")
    return next_channel
