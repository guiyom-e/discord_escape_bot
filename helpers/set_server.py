from discord import Guild, HTTPException

from default_collections import (RoleCollection, ChannelCollection, CategoryChannelCollection, CharacterCollection,
                                 GuildCollection)
from helpers.set_channels import update_channels
from helpers.set_roles import update_roles
from logger import logger
from models.characters import CharacterType


async def update_guild_roles(guild: Guild, delete_old=False, clear_references=True) -> bool:
    logger.info("Doing: update server roles")
    upd_ok = await update_roles(guild, RoleCollection.to_list(), delete_old=delete_old,
                                clear_references=clear_references)
    logger.info(f"Done{'' if upd_ok else ' with errors'}: update server roles")
    return upd_ok


async def update_guild_channels(guild: Guild, delete_old=False, clear_references=True) -> bool:
    logger.info("Doing: update server channels")
    upd_ok = await update_channels(guild, CategoryChannelCollection.to_list() + ChannelCollection.to_list(),
                                   delete_old=delete_old, clear_references=clear_references)
    logger.info(f"Done{'' if upd_ok else ' with errors'}: update server channels")
    return upd_ok


async def update_guild_properties(guild: Guild) -> bool:
    # Requires manage_webhooks permissions.
    logger.info("Doing: update webhooks and bot")
    guild_webhooks = await guild.webhooks()
    for character in CharacterCollection.to_list():
        # Update bot
        if character.character_type is CharacterType.bot:
            try:
                await character.update_object(guild.me)
            except HTTPException as err:
                logger.error(f"Impossible to update bot {character}: {err}")
            continue
        # Update webhooks
        character.object_reference.clear()  # special object_reference for characters
        for guild_webhook in guild_webhooks:
            if character.name == guild_webhook.name:
                if guild_webhook.channel_id:
                    channel = guild.get_channel(guild_webhook.channel_id)
                else:
                    channel = None
                try:
                    await character.update_object(guild_webhook, channel)
                except HTTPException as err:
                    logger.error(f"Impossible to update webhook {character}: {err}")
                continue
    logger.info(f"Done: update webhooks and bot")
    logger.info(f"Doing: update guild")
    try:
        await guild.edit(**GuildCollection.STANDARD.to_dict())
    except Exception as err:
        logger.error(f"Failed to update guild {GuildCollection.STANDARD}: {err}")
    logger.info(f"Done: update guild")
    return True
