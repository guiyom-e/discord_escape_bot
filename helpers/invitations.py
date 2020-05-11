import re

import requests
from discord import TextChannel, HTTPException
from discord.abc import GuildChannel

from constants import WEBSITE, TOKEN_SITE
from default_collections import GeneralMessages
from logger import logger


async def delete_invite(origin_channel: TextChannel = None):
    base_url = re.sub("/$", "", WEBSITE)
    api_path = "/api/invite"
    message = {"token": TOKEN_SITE}
    try:
        answer = requests.delete(base_url + api_path, json=message)
    except Exception as err:
        logger.error(f"Failed to send request to remove guild availability on website {base_url}: {err}")
        if origin_channel:
            await origin_channel.send("Failed to delete invite link from website")
        return False
    if 200 <= answer.status_code < 300:
        logger.info(f"Invite successful deleted on website {base_url}")
        if origin_channel:
            await origin_channel.send("Invite link deleted from website")
    else:
        logger.warning(f"Error while posting invite deletion on website {base_url}")
        if origin_channel:
            await origin_channel.send("Failed to delete invite link from website")


async def post_invite_link(link, origin_channel: TextChannel = None):
    base_url = re.sub("/$", "", WEBSITE)
    api_path = "/api/invite"
    message = {"token": TOKEN_SITE, "link": str(link)}
    try:
        answer = requests.post(base_url + api_path, json=message)
    except Exception as err:
        logger.error(f"Failed to send request to remove guild availability on website {base_url}: {err}")
        if origin_channel:
            await origin_channel.send("Failed to post invite link on website")
        return False
    if 200 <= answer.status_code < 300:
        logger.info(f"Invite successful on website {base_url}")
        if origin_channel:
            await origin_channel.send("Invite link has been added to website")
    else:
        logger.warning(f"Error while posting new invite link on website {base_url}")
        if origin_channel:
            await origin_channel.send("Failed to post invite link on website")


async def create_invite(channel: GuildChannel, origin_channel: TextChannel, **kwargs):
    if channel is None:
        logger.warning("Cannot create invite, because channel is None!")
        return
    website = kwargs.pop("website", False)
    try:
        invite = await channel.create_invite(**kwargs)
    except HTTPException as err:
        logger.warning(f"Cannot create invite: {err}")
        return False
    if origin_channel:
        await origin_channel.send(GeneralMessages["INVITE_MESSAGE"].format(link=invite))
    if website:
        await post_invite_link(invite.url, origin_channel)
