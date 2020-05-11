import sys

if __name__ == '__main__':
    sys.path.insert(0, "..")
import discord
from discord import Message

from logger import logger
from helpers import TranslationDict, send_dm_message
from game_models import AbstractMiniGame
from default_collections import GeneralMessages, ChannelCollection, RoleCollection, Emojis


class Messages(TranslationDict):
    INTRO = "Default message with a string to format: {format_your_custom_text_here}"


MESSAGES = Messages(path="configuration/minigames/sample")


async def welcome_general_message(channel):
    reception_channel = ChannelCollection.SUPPORT.value.object_reference
    master_mention = RoleCollection.MASTER.value.object_reference.mention
    await channel.send(
        GeneralMessages["WELCOME"].format(master=master_mention, channel=reception_channel.mention),
        file=discord.File(GeneralMessages["WELCOME_FILE"])
    )


async def handle_dm_message_error(reason, user: discord.user.User, origin_channel=None):
    logger.info(f"Impossible to send DM message to {user.name} (id: {user.id}). Reason: {reason}")
    if origin_channel:
        bot_mention = RoleCollection.BOT.value.object_reference.mention
        await origin_channel.send(
            GeneralMessages["DM_MESSAGES_ERROR"].format(user_mention=user.mention, bot_mention=bot_mention),
            file=discord.File(GeneralMessages["DM_MESSAGES_ERROR_FILE"])
        )


async def welcome_dm_message(user: discord.user.User, origin_channel=None):
    message = GeneralMessages["DM_MESSAGE_WELCOME"]
    await send_dm_message(user, message, origin_channel, callback_on_forbidden_error=handle_dm_message_error)


class SampleMiniGame(AbstractMiniGame):
    _default_messages = MESSAGES

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def access_a_translation_key(self, key, value_to_format):
        return self._messages[key].format(format_your_custom_text_here=value_to_format)

    async def on_message(self, message: Message):
        await message.add_reaction(Emojis.thumbsup)
        await welcome_dm_message(message.author, message.channel)
        if message.content.startswith("init"):
            await welcome_general_message(message.channel)


if __name__ == '__main__':
    import os

    if os.path.basename(os.getcwd()) == "minigames":
        os.chdir("..")
    print(SampleMiniGame().access_a_translation_key("INTRO", "Hello!"))
