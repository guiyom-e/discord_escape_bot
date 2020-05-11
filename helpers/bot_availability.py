import re

import discord
from discord import Permissions
import requests

from constants import WEBSITE, TOKEN_SITE, BOT
from logger import logger


def remove_bot_availability_on_website() -> bool:
    base_url = re.sub("/$", "", WEBSITE)
    api_path = "/api/availability"
    message = {"token": TOKEN_SITE}
    try:
        answer = requests.delete(base_url + api_path, json=message)
    except Exception as err:
        logger.error(f"Failed to send request to remove guild availability on website {base_url}: {err}")
        return False
    if 200 <= answer.status_code < 300:
        logger.info("Bot availability removed on website")
        return True
    else:
        logger.warning("Error while removing bot availability on website")
        return False


def add_bot_availability_on_website() -> bool:
    bot_invite_link = discord.utils.oauth_url(client_id=BOT.user.id, permissions=Permissions(8))
    logger.info(f"The bot is not in a guild! To invite it, use the following link: {bot_invite_link}")
    base_url = re.sub("/$", "", WEBSITE)
    api_path = "/api/availability"
    message = {"token": TOKEN_SITE}
    try:
        answer = requests.post(base_url + api_path, json=message)
    except Exception as err:
        logger.error(f"Failed to send request to remove guild availability on website {base_url}: {err}")
        return False
    if 200 <= answer.status_code < 300:
        logger.info("Bot availability added on website")
        return True
    else:
        logger.warning("Error while adding bot availability on website")
        return False
