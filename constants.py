# -*- coding: utf-8 -*-
import ast
import os

from discord.ext.commands import Bot
from dotenv import load_dotenv

from logger import logger

_DOT_ENV_PATH = ".env"
try:
    if os.path.exists(_DOT_ENV_PATH):
        # Load dotenv
        load_dotenv(dotenv_path=_DOT_ENV_PATH, encoding="utf-8")

    DEBUG_MODE = bool(os.getenv('DEBUG_MODE', False))
    logger.info("Debug mode activated" if DEBUG_MODE else "Production mode activated")
    GAME_LANGUAGE = ast.literal_eval(os.getenv('GAME_LANGUAGE', None))  # string or list of strings
    assert GAME_LANGUAGE is None or isinstance(GAME_LANGUAGE, (str, list))
    AWAKE_REFRESH_PERIOD = int(os.getenv('AWAKE_REFRESH_PERIOD', 50 * 60))
    WEBSITE = os.getenv('WEBSITE', None)
    MAX_GUILDS = int(os.getenv('MAX_GUILDS', 1))
    MAX_PENDING_GUILDS = int(os.getenv('MAX_PENDING_GUILDS', 5))
    GAME_LINK = os.getenv("GAME_LINK", "")
    _TOKEN = os.getenv('DISCORD_TOKEN')
    TOKEN_SITE = os.getenv('TOKEN_SITE')
    SONG_PATH = os.getenv("SONG_PATH", "files/_songs/")
    VERBOSE = bool(os.getenv("VERBOSE", True))
    CLIENT_ID = int(os.getenv("CLIENT_ID", None))
    PASSWORD_BOT_INVITE = os.getenv("PASSWORD_BOT_INVITE", None)
    PASSWORD_REMOVE_BOT = os.getenv("PASSWORD_REMOVE_BOT", None)
    PASSWORD_KICK_BOT = os.getenv("PASSWORD_KICK_BOT", None)
except (KeyError, ValueError) as err:
    logger.error("Failed to load environment variables. Program will terminate.")
    logger.exception(err)
    exit(1)
except AssertionError as err:
    logger.exception(err)
    exit(1)
else:
    if MAX_GUILDS < 1:
        logger.error(f"Maximum number of guilds set ({MAX_GUILDS}) is invalid; it must be strictly positive. "
                     f"Program will terminate.")
        exit(2)
    if MAX_GUILDS > 1:
        logger.error(f"More than one guild is not supported yet!")
        exit(3)
    logger.info(f"Environment variables:\nGAME_LANGUAGE: {GAME_LANGUAGE}"
                f"\nVERBOSE: {VERBOSE}\nDEBUG_MODE: {DEBUG_MODE}")


class CustomBot(Bot):
    def __repr__(self):
        return f"<Bot display_name='{self.user.display_name}'>"


BOT = CustomBot(command_prefix="$")
