import asyncio
import functools

import discord
from flask import Flask, render_template, redirect, request

from constants import GAME_LINK, _TOKEN, TOKEN_SITE, CLIENT_ID, PASSWORD_BOT_INVITE
from helpers.json_helpers import TranslationDict
from logger import logger

app = Flask(__name__)

MESSAGES = TranslationDict(path="configuration/minigames/map_game/")


class Config:
    game_link = GAME_LINK
    client_id = CLIENT_ID
    bot_available = None  # None: bot starting / False: not available / True: available


# TODO: not working:
def async_action(f):
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))

    return wrapped


# TODO: not working
async def _check_invite_link():
    client = discord.Client()
    try:
        await client.connect()
        await client.login(token=_TOKEN)
        invite = await client.fetch_invite(Config.game_link)
    except (discord.NotFound, discord.HTTPException) as err:
        logger.debug(f"Invalid link {Config.game_link}. Error: {err}")
        return False
    else:
        logger.debug(f"Valid link {Config.game_link}. Invite: {invite}")
        return True
    finally:
        await client.close()


# A welcome message to test our server
@app.route('/')
def index():
    is_link_valid = Config.game_link.startswith("https://discord")  # todo: replace by a discord check (issue: async)
    game_link = Config.game_link if is_link_valid else "#"
    bot_invite_path = "/bot_invite" if Config.bot_available else "/" if Config.bot_available is None else "#"
    logger.info(f"Get request to /. Returning index.html rendered: "
                f"game link={game_link}, bot_invite_path={bot_invite_path}")
    return render_template("index.html", game_link=game_link, bot_invite_path=bot_invite_path)


# An invite link for the bot
@app.route('/bot_invite', methods=['GET'])
def bot_invite_page():
    logger.info(f"Get request to /bot_invite. Current bot availability: {Config.bot_available}")
    return render_template("bot_invite.html")


@app.route('/api/bot_invite', methods=['POST'])
def bot_invite():
    code = request.json.get("code", None)
    if code != PASSWORD_BOT_INVITE:
        return {"ok": False}, 401

    if not Config.client_id:
        return {"ok": False}, 400

    invite_link = f"https://discord.com/oauth2/authorize?client_id={Config.client_id}&scope=bot&permissions=8"
    logger.info(f"Returning bot invite link: {invite_link}")
    return {"ok": True, "link": invite_link}, 200


@app.route('/api/invite', methods=['POST', 'DELETE'])
def invite():
    token_site = request.json.get("token", None)
    if token_site != TOKEN_SITE:
        return {"ok": False}, 401

    # DELETE METHOD
    if request.method == "DELETE":
        logger.info(f"Invite link {Config.game_link} deleted.")
        Config.game_link = ""
        return {"ok": True, "mode": "delete"}, 200

    # POST method
    new_game_link = request.json.get("link", None)
    if new_game_link and new_game_link.startswith("https://discord."):
        Config.game_link = new_game_link
        logger.info(f"Invitation link updated to {new_game_link}")
        return {"ok": True, "mode": "create"}, 200
    return {"ok": False}, 400


@app.route('/api/availability', methods=['POST', 'DELETE'])
def change_availability():
    token_site = request.json.get("token", None)
    if token_site != TOKEN_SITE:
        return {"ok": False}, 401

    # DELETE METHOD
    if request.method == "DELETE":
        Config.bot_available = False
        return {"ok": True, "mode": "remove"}, 200

    # POST method
    if request.method == "POST":
        Config.bot_available = True
        return {"ok": True, "mode": "add"}, 200
    return {"ok": False}, 400


@app.route('/map/<code>')
def map_route(code):
    if code != MESSAGES["MAP_CODE"]:
        return render_template("error_code.html",
                               message=MESSAGES["ERROR_MESSAGE"].format(code=code),
                               title=MESSAGES["ERROR_TITLE"])
    map_url = f"{MESSAGES['REAL_LINK_PREFIX']}{code}"
    return redirect(map_url)


if __name__ == '__main__':
    # Threaded option to enable multiple instances for multiple user access support
    loop = asyncio.get_event_loop()
    app.run(threaded=True, port=5000)
