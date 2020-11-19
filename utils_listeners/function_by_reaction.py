from typing import Dict, Tuple, Union, List, Callable, Awaitable, Iterable
import asyncio

from discord import Reaction, User, Member, Message, Forbidden, NotFound, RawReactionActionEvent, HTTPException

from game_models.abstract_listener import reconstitute_reaction_and_user
from game_models.abstract_utils import AbstractUtils
from helpers import return_
from helpers.discord_helpers import try_to_remove_reaction
from logger import logger
from models import RoleDescription
from models.types import GuildSingleton


class MenuOptions:
    def __init__(self,
                 required_roles: List[RoleDescription] = None,
                 ignored_roles: List[RoleDescription] = None,
                 max_users_per_reaction: int = None,
                 max_number_of_reactions_per_user: int = None,
                 remove_reaction_after_action=False,
                 allow_role_change=True,
                 update_reactions=True,
                 include_user_as_kwarg=False,
                 ):
        self.required_roles = required_roles
        self.ignored_roles = ignored_roles
        self.max_users_per_reaction = max_users_per_reaction
        self.max_number_of_reactions_per_user = max_number_of_reactions_per_user
        self.remove_reaction_after_action = remove_reaction_after_action
        self.update_reactions = update_reactions  # remove reaction if role(s) not granted
        self.allow_role_change = allow_role_change
        self.include_user_as_kwarg = include_user_as_kwarg


async def count_user_reactions(reactions: List[Reaction], user: Union[User, Member]):
    count_reactions = 0
    for msg_reaction in reactions:
        users = await msg_reaction.users().flatten()
        if user in users:
            count_reactions += 1
    return count_reactions


async def has_allowed_role(user: Member, reaction: Reaction, options: MenuOptions):
    # First checks required roles, then ignored roles
    if options.required_roles:  # Only one role among all required_roles is necessary to allow the user
        for role in user.roles:
            if role in (role_desc.object_reference for role_desc in options.required_roles):
                return True
        logger.debug(f"User {user} does not have the required roles")
        if options.update_reactions:
            await try_to_remove_reaction(reaction, user)
        return False
    if options.ignored_roles:  # Only one role among all ignored_roles is sufficient to ignore the user
        for role in user.roles:
            if role in (role_desc.object_reference for role_desc in options.ignored_roles):
                logger.debug(f"Ignored role {role} for this role menu")
                return False
    return True


CallableOrAwaitable = Union[Callable, Awaitable]
MenuType = Dict[str, CallableOrAwaitable]


class ReactionMenuManager(GuildSingleton, AbstractUtils):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._menus: Dict[int, Tuple[MenuType, MenuOptions, Dict[User, Reaction]]] = {}

    def get_menu(self, message_id: int, default=None):
        return self._menus.get(message_id, default)

    def change_option(self, message_id: int, **kwargs):
        options = self._menus.get(message_id)[1]
        for key, value in kwargs.items():
            setattr(options, key, value)
        logger.info(f"Menu options changed: {kwargs}")

    @staticmethod
    async def _add_emojis(message: Message, emojis: Iterable[str]):
        try:
            for emoji in emojis:
                await message.add_reaction(emoji)
        except NotFound as err:
            logger.error(f"Error while creating reaction menu. Maybe invalid emoji ? Original error: {err}")
            await message.clear_reactions()
            return True
        except HTTPException as err:
            logger.error(f"Error while creating reaction menu. Maybe rate limited ? Original error: {err}")
            logger.exception(err)
            await message.clear_reactions()
            return False
        else:
            logger.info("Reaction menu created")
            return True

    async def _add_emojis_with_retries(self, message: Message, emojis: Iterable[str]):
        has_been_sent = False
        retries = 0
        while not has_been_sent and retries < 2:
            if retries:
                logger.info(f"Retrying to send emojis... [{emojis}]")
                await asyncio.sleep(0.2)
            has_been_sent = await self._add_emojis(message, emojis)
            retries += 1

    async def add(self, message: Message, menu: MenuType, options: MenuOptions = None):
        options = options or MenuOptions()
        self._menus.update({message.id: (menu, options, {})})
        await message.clear_reactions()
        await self._add_emojis_with_retries(message, menu.keys())

    async def on_raw_reaction_add(self, payload: RawReactionActionEvent):
        # Avoid that a disconnection breaks on_reaction_remove
        reaction, user = await reconstitute_reaction_and_user(payload)
        return await self._reaction_add(reaction, user) if reaction else None

    async def on_raw_reaction_remove(self, payload: RawReactionActionEvent):
        # Avoid that a disconnection breaks on_reaction_remove
        reaction, user = await reconstitute_reaction_and_user(payload)
        return await self._reaction_remove(reaction, user) if reaction else None

    async def _base_reaction_add_checks(self, reaction: Reaction, user: Union[Member, User],
                                        options: MenuOptions, users_who_reacted: Dict[User, Reaction]) -> bool:
        # Check if ignored/required role
        if not await has_allowed_role(user, reaction, options):
            return False

        # Check if allow_change
        if not options.allow_role_change and user in users_who_reacted:
            logger.debug(f"User {user} already chose an action and parameters do not allow to change!")
            if reaction != users_who_reacted[user]:  # the user has not reacted with this emoji last time
                if options.update_reactions:
                    await try_to_remove_reaction(reaction, user)
                return False

        # Check if max number of reactions per user reached
        if options.max_number_of_reactions_per_user is not None:
            nb_current_reactions = await count_user_reactions(reaction.message.reactions, user)
            if nb_current_reactions > options.max_number_of_reactions_per_user:
                logger.debug(f"Too much reactions already! Max allowed: {options.max_number_of_reactions_per_user}")
                if options.update_reactions:
                    await try_to_remove_reaction(reaction, user)
                return False

        # Check if max number of reactions per reaction reached
        # TODO: add a lock to handle simultaneous clicks on a reaction
        if options.max_users_per_reaction is not None:
            current_users = await reaction.users().flatten()
            if len(current_users) - 1 > options.max_users_per_reaction:
                logger.debug(
                    f"Too much users already reacted with this reaction ! Max allowed: {options.max_users_per_reaction}")
                if options.update_reactions:
                    await try_to_remove_reaction(reaction, user)
                return False

        return True

    async def advanced_reaction_add(self, reaction: Reaction, user: Union[Member, User], role_menu: MenuType,
                                    options: MenuOptions, users_who_reacted: Dict[User, Reaction]) -> bool:
        return await self._base_reaction_add_checks(reaction, user, options, users_who_reacted)

    async def execute_action_on_add(self, reaction: Reaction, user: Union[Member, User], role_menu: MenuType,
                                    options: MenuOptions, users_who_reacted: Dict[User, Reaction]):
        action = role_menu[reaction.emoji]
        try:
            if options.include_user_as_kwarg:
                await return_(action(user=user))
            else:
                await return_(action())
        except Forbidden as err:
            logger.warning(f"Impossible to execute action {reaction.emoji} {action}: {err}")
            if options.update_reactions:
                await try_to_remove_reaction(reaction, user)
        users_who_reacted[user] = reaction

    async def after_action(self, reaction, user, options):
        # remove reaction after action
        if options.remove_reaction_after_action:
            await try_to_remove_reaction(reaction, user)

    async def _reaction_add(self, reaction: Reaction, user: Union[Member, User]):
        if not await super().on_reaction_add(reaction, user):
            return
        if user.bot:
            return
        if reaction.message.id not in self._menus:
            return
        role_menu, options, users_who_reacted = self._menus[reaction.message.id]
        if reaction.emoji not in role_menu:
            return
        logger.debug("New allowed reaction received")

        if not await self.advanced_reaction_add(reaction, user, role_menu, options, users_who_reacted):
            return

        # Finally execute the action
        await self.execute_action_on_add(reaction, user, role_menu, options, users_who_reacted)

        await self.after_action(reaction, user, options)

    async def advanced_reaction_remove(self, reaction: Reaction, user: Union[Member, User], role_menu: MenuType,
                                       options: MenuOptions, users_who_reacted: Dict[User, Reaction]):
        pass

    async def _reaction_remove(self, reaction: Reaction, user: Union[Member, User]):
        if not await super().on_reaction_remove(reaction, user):
            return
        if user.bot:
            return
        if reaction.message.id not in self._menus:
            return
        role_menu, options, users_who_reacted = self._menus[reaction.message.id]
        if reaction.emoji not in role_menu:
            return

        await self.advanced_reaction_remove(reaction, user, role_menu, options, users_who_reacted)
