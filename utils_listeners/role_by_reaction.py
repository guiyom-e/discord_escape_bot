from typing import Dict, Tuple, Union, List, Collection

from discord import Reaction, User, Member, Message, Role, Forbidden, NotFound, RawReactionActionEvent, HTTPException

from game_models.abstract_listener import reconstitute_reaction_and_user
from game_models.abstract_utils import AbstractUtils
from logger import logger
from models import RoleDescription
from models.types import GuildSingleton


# TODO: handle permission errors on reaction removal

class RoleMenuOptions:
    def __init__(self,
                 required_roles: List[RoleDescription] = None,
                 ignored_roles: List[RoleDescription] = None,
                 max_users_with_role: int = None,
                 max_number_of_reactions_per_user: int = None,
                 remove_role_on_reaction_removal=True,
                 allow_role_change=True,
                 update_reactions=True,
                 ):
        self.required_roles = required_roles
        self.ignored_roles = ignored_roles
        self.max_users_with_role = max_users_with_role  # maximum number of users that can get the role(s)
        self.max_number_of_reactions_per_user = max_number_of_reactions_per_user
        self.remove_role_on_reaction_removal = remove_role_on_reaction_removal
        self.update_reactions = update_reactions  # remove reaction if role(s) not granted
        self.allow_role_change = allow_role_change


async def count_user_reactions(reactions: List[Reaction], user: Union[User, Member]):
    count_reactions = 0
    for msg_reaction in reactions:
        users = await msg_reaction.users().flatten()
        if user in users:
            count_reactions += 1
    return count_reactions


async def has_allowed_role(user: Member, reaction: Reaction, options: RoleMenuOptions):
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


async def check_max_users_with_role(role_descriptions: Collection[RoleDescription], max_users_with_role):
    if max_users_with_role is None:
        return True
    for role_descr in role_descriptions:
        members = role_descr.object_reference.members
        # Check if the maximum number of user with a role is reached
        if max_users_with_role <= len(members):
            return False
    return True


class RoleByReactionManager(GuildSingleton, AbstractUtils):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._role_menus: Dict[int, Tuple[Dict[str, List[RoleDescription]], RoleMenuOptions, Dict[User, Reaction]]] = {}

    def get_menu(self, message_id: int, default=None):
        return self._role_menus.get(message_id, default)

    async def add(self, message: Message, menu: Dict[str, List[Union[RoleDescription, Role]]],
                  options: RoleMenuOptions = None):
        options = options or RoleMenuOptions()
        # Handle both types Role and RoleDescription: Role is converted to RoleDescription
        for emoji, role_descriptions in menu.items():
            if isinstance(role_descriptions, (RoleDescription, Role)):  # error in input args is corrected
                logger.warning("Bad arg: menu values must be a list of RoleDescription or Role ! Auto-correcting...")
                role_descriptions = [role_descriptions]
                menu[emoji] = role_descriptions
            for i, role_descr in enumerate(role_descriptions):
                if isinstance(role_descr, Role):
                    role_descriptions[i] = RoleDescription.from_role(role_descr)
        self._role_menus.update({message.id: (menu, options, {})})
        await message.clear_reactions()
        try:
            for emoji in menu:
                await message.add_reaction(emoji)
        except (NotFound, HTTPException) as err:
            logger.error(f"Error while creating role menu. Maybe invalid emoji ? Original error: {err}")
            await message.clear_reactions()
        else:
            logger.info("Role menu created")

    async def on_raw_reaction_add(self, payload: RawReactionActionEvent):
        # Avoid that a disconnection breaks on_reaction_remove
        reaction, user = await reconstitute_reaction_and_user(payload)
        return await self.reaction_add(reaction, user) if reaction else None

    async def on_raw_reaction_remove(self, payload: RawReactionActionEvent):
        # Avoid that a disconnection breaks on_reaction_remove
        reaction, user = await reconstitute_reaction_and_user(payload)
        return await self.reaction_remove(reaction, user) if reaction else None

    async def reaction_add(self, reaction: Reaction, user: Union[Member, User]):
        if not await super().on_reaction_add(reaction, user):
            return
        if user.bot:
            return
        if reaction.message.id not in self._role_menus:
            return
        role_menu, options, users_who_reacted = self._role_menus[reaction.message.id]
        if reaction.emoji not in role_menu:
            return
        logger.debug("New allowed reaction received")

        # Check if ignored/required role
        if not await has_allowed_role(user, reaction, options):
            return

        # Check if allow_change
        if not options.allow_role_change and user in users_who_reacted:
            logger.debug(f"User {user} already chose a role and parameters do not allow to change!")
            if reaction != users_who_reacted[user]:  # the user has not reacted with this emoji last time
                if options.update_reactions:
                    await reaction.remove(user)
                return

        # Check if max number of reactions reached
        if options.max_number_of_reactions_per_user is not None:
            nb_current_reactions = await count_user_reactions(reaction.message.reactions, user)
            if nb_current_reactions > options.max_number_of_reactions_per_user:
                logger.debug(f"Too much reactions already! Max allowed: {options.max_number_of_reactions_per_user}")
                if options.update_reactions:
                    await reaction.remove(user)
                return

        role_descriptions = role_menu[reaction.emoji]
        # Check if the maximum number of users with the roles have been reached
        if not await check_max_users_with_role(role_descriptions, options.max_users_with_role):
            logger.debug(f"Refused roles {role_descriptions} to {user} "
                         f"because max_users_with_role reached for at least one role")
            if options.update_reactions and not all(r_d.object_reference in user.roles for r_d in role_descriptions):
                await reaction.remove(user)  # manage_messages required
            return

        # Finally, grant the roles
        try:
            await user.add_roles(*(role_descr.object_reference for role_descr in role_descriptions))
        except Forbidden as err:
            logger.warning(f"Impossible to add roles: {err}")
            if options.update_reactions:
                await reaction.remove(user)
        users_who_reacted[user] = reaction

    async def reaction_remove(self, reaction: Reaction, user: Union[Member, User]):
        if not await super().on_reaction_remove(reaction, user):
            return
        if user.bot:
            return
        if reaction.message.id not in self._role_menus:
            return
        role_menu, options, _users_who_reacted = self._role_menus[reaction.message.id]
        if reaction.emoji not in role_menu:
            return
        role_descriptions = role_menu[reaction.emoji]
        if options.remove_role_on_reaction_removal:
            try:
                await user.remove_roles(*(role_descr.object_reference for role_descr in role_descriptions))
            except Forbidden as err:
                logger.warning(f"Impossible to remove roles: {err}")
            logger.debug(f"Removed roles {role_descriptions} from {user} because of reaction removal")
