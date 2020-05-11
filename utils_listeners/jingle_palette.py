from typing import Dict, Tuple, Union, List

from discord import Reaction, User, Member, Message, Forbidden, NotFound, RawReactionActionEvent, HTTPException

from game_models.abstract_listener import reconstitute_reaction_and_user
from game_models.abstract_utils import AbstractUtils
from helpers import SoundTools
from logger import logger
from models import RoleDescription
from models.types import GuildSingleton


class JinglePaletteOptions:
    def __init__(self,
                 required_roles: List[RoleDescription] = None,
                 ignored_roles: List[RoleDescription] = None,
                 stop_jingle_on_reaction_removal=False,
                 update_reactions=True,
                 auto_remove=True,
                 suppress_embed=True
                 ):
        self.required_roles: List[RoleDescription] = required_roles
        self.ignored_roles: List[RoleDescription] = ignored_roles
        self.update_reactions = update_reactions  # remove reaction if operation failed
        self.stop_jingle_on_reaction_removal = stop_jingle_on_reaction_removal
        self.auto_remove = auto_remove
        self.suppress_embed = suppress_embed


async def has_allowed_role(user, reaction, options):
    # First checks required roles, then ignored roles
    if options.required_roles:  # Only one role among all required_roles is necessary to allow the user
        for role in user.roles:
            if role in (role_desc.object_reference for role_desc in options.required_roles):
                return True
        logger.debug(f"User {user} does not have the required roles")
        if options.update_reactions:
            await reaction.remove(user)
        return False
    if options.ignored_roles:  # Only one role among all ignored_roles is sufficient to ignore the user
        for role in user.roles:
            if role in (role_desc.object_reference for role_desc in options.ignored_roles):
                logger.debug(f"Ignored role {role} for this role menu")
                return False
    return True


class JinglePaletteManager(GuildSingleton, AbstractUtils):
    def __init__(self, **kwargs):
        self._stop_emoji = kwargs.pop("stop_emoji", "⏹️")
        self._pause_emoji = kwargs.pop("pause_emoji", "⏸")
        super().__init__(**kwargs)
        # Dictionary: {message_id: ({emoji: link or local_song_path, ...}, JinglePaletteOptions, display_message_id)}
        self._palette_menu: Dict[int, Tuple[Dict[str, str], JinglePaletteOptions, int]] = {}
        self._sound_tools: SoundTools = None

    def _init(self) -> bool:
        self._sound_tools = SoundTools.get(self.guild)
        return True

    def get_menu(self, message_id: int, default=None):
        return self._palette_menu.get(message_id, default)

    async def add(self, message: Message, menu: Dict[str, str], options: JinglePaletteOptions = None):
        options = options or JinglePaletteOptions()
        display_message = await message.channel.send(f"⏲ ️🎵 Loading Jingle palette...")
        self._palette_menu.update({message.id: (menu, options, display_message.id)})
        await message.clear_reactions()

        # Remove stop emoji if it exists in the menu
        if self._stop_emoji in menu:
            logger.warning(f"Stop emoji {self._stop_emoji} cannot be a key for a jingle!")
            menu.pop(self._stop_emoji)
        # Remove pause emoji if it exists in the menu
        if self._pause_emoji in menu:
            logger.warning(f"Pause emoji {self._stop_emoji} cannot be a key for a jingle!")
            menu.pop(self._pause_emoji)

        # Suppress embed
        if options.suppress_embed:
            await message.edit(suppress=True)
        # Add reactions
        try:
            await message.add_reaction(self._pause_emoji)
            await message.add_reaction(self._stop_emoji)
            for emoji in menu:
                await message.add_reaction(emoji)
        except (NotFound, HTTPException) as err:
            logger.error(f"Error while creating jingle palette. Maybe invalid emoji ? Original error: {err}")
            await message.clear_reactions()
            await display_message.edit(content="❌ Jingle palette loading failed! "
                                               "Check arguments (invalid syntax/emoji ?).")
        else:
            logger.info("Jingle palette created")
            await display_message.edit(content="🎵 Jingle palette ready!")

    async def on_raw_reaction_add(self, payload: RawReactionActionEvent):
        # Avoid that a disconnection breaks on_reaction_remove
        reaction, user = await reconstitute_reaction_and_user(payload)
        return await self.reaction_add(reaction, user) if reaction else None

    async def on_raw_reaction_remove(self, payload: RawReactionActionEvent):
        # Avoid that a disconnection breaks on_reaction_remove
        reaction, user = await reconstitute_reaction_and_user(payload)
        return await self.reaction_remove(reaction, user) if reaction else None

    async def _fetch_message(self, reaction: Reaction, message_id: int):
        try:
            message = await reaction.message.channel.fetch_message(message_id)
        except (NotFound, Forbidden, HTTPException) as err:
            logger.warning(f"Display message doesn't exist anymore!")
            message = None
        return message

    async def reaction_add(self, reaction: Reaction, user: Union[Member, User]):
        if not await super().on_reaction_add(reaction, user):
            return
        if user.bot:
            return
        if reaction.message.id not in self._palette_menu:
            return
        jingle_menu, options, display_message_id = self._palette_menu[reaction.message.id]

        # Check if ignored/required role
        if not await has_allowed_role(user, reaction, options):
            return

        display_message = await self._fetch_message(reaction, display_message_id)

        # Stop emoji
        if reaction.emoji == self._stop_emoji:
            if await self._sound_tools.stop():
                if display_message:
                    await display_message.edit(content="⏹ Jingle stopped!")
            else:
                logger.warning("Failed to stop jingle!")
                if display_message:
                    await display_message.edit(content="❌⏹ Failed to stop jingle!")
            if options.auto_remove:
                await reaction.remove(user)
            return

        # Pause emoji
        if reaction.emoji == self._pause_emoji:
            if not self._sound_tools.is_playing():
                # Nothing to pause and no error to raise
                if options.auto_remove:
                    await reaction.remove(user)
                return
            if await self._sound_tools.pause():
                if display_message:
                    await display_message.edit(content=f"⏸️ Jingle paused: {self._sound_tools.last_source_path}")
            else:
                logger.warning("Failed to pause jingle!")
                if display_message:
                    await display_message.edit(content="❌⏸️ Failed to pause jingle / Nothing to pause!")
            return

        # Jingle emojis
        if reaction.emoji not in jingle_menu:
            return
        logger.debug("New allowed reaction received")

        # Check if the user is connected to a voice channel
        voice_channel = user.voice.channel if user.voice else None
        if not voice_channel:
            logger.warning(f"Cannot play jingle: user {user} is not in a voice channel!")
            if display_message:
                await display_message.edit(content=f"❌ Cannot play, you are not in a voice channel!")
            return

            # Finally, play the jingle
        link = jingle_menu[reaction.emoji]
        if await self._sound_tools.play(voice_channel, link, force=True):
            if display_message:
                await display_message.edit(content=f"▶️ Playing {link}")
        else:
            logger.warning("Failed to play jingle!")
            if display_message:
                await display_message.edit(content=f"❌▶️ Failed to play {link}")
        if options.auto_remove:
            await reaction.remove(user)

    async def reaction_remove(self, reaction: Reaction, user: Union[Member, User]):
        if not await super().on_reaction_remove(reaction, user):
            return
        if user.bot:
            return
        if reaction.message.id not in self._palette_menu:
            return

        jingle_menu, options, display_message_id = self._palette_menu[reaction.message.id]

        # Check if ignored/required role
        if not await has_allowed_role(user, reaction, options):
            return

        display_message = await self._fetch_message(reaction, display_message_id)

        # Pause emoji
        if reaction.emoji == self._pause_emoji:
            if not self._sound_tools.is_paused():
                # nothing to pause
                return
            if await self._sound_tools.resume():
                if display_message:
                    await display_message.edit(content=f"⏯️ Jingle resumed: {self._sound_tools.last_source_path}")
            else:
                logger.warning("Failed to resume jingle or nothing to resume!")
                if display_message:
                    await display_message.edit(content=f"❌⏯️ Failed to resume jingle / Nothing to resume!")
            return

        if reaction.emoji not in jingle_menu:
            return

        if options.stop_jingle_on_reaction_removal:
            if await self._sound_tools.pause():
                await display_message.edit(content=f"Jingle paused!")
            else:
                logger.warning("Failed to pause jingle or nothing to pause!")
                await display_message.edit(content=f"Failed to pause jingle!")
