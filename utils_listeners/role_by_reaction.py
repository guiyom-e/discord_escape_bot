from typing import Dict, Tuple, Union, List, Collection

from discord import Reaction, User, Member, Message, Role, Forbidden

from logger import logger
from models import RoleDescription
from utils_listeners.function_by_reaction import ReactionMenuManager, MenuOptions


# TODO: handle permission errors on reaction removal


class RoleMenuOptions(MenuOptions):
    def __init__(self, remove_role_on_reaction_removal=True, max_users_with_role: int = None, **kwargs):
        super().__init__(**kwargs)
        self.max_users_with_role = max_users_with_role  # maximum number of users that can get the role(s)
        self.remove_role_on_reaction_removal = remove_role_on_reaction_removal


async def check_max_users_with_role(role_descriptions: Collection[RoleDescription], max_users_with_role):
    if max_users_with_role is None:
        return True
    for role_descr in role_descriptions:
        members = role_descr.object_reference.members
        # Check if the maximum number of user with a role is reached
        if max_users_with_role <= len(members):
            return False
    return True


MenuType = Dict[str, List[RoleDescription]]


class RoleByReactionManager(ReactionMenuManager):
    _menus: Dict[int, Tuple[MenuType, RoleMenuOptions, Dict[User, Reaction]]]

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

        self._menus.update({message.id: (menu, options, {})})
        await message.clear_reactions()
        await self._add_emojis_with_retries(message, menu.keys())

    async def advanced_reaction_add(self, reaction: Reaction, user: Union[Member, User], role_menu: MenuType,
                                    options: RoleMenuOptions, users_who_reacted: Dict[User, Reaction]) -> bool:
        if not await self._base_reaction_add_checks(reaction, user, options, users_who_reacted):
            return False

        role_descriptions = role_menu[reaction.emoji]
        # Check if the maximum number of users with the roles have been reached
        if not await check_max_users_with_role(role_descriptions, options.max_users_with_role):
            logger.debug(f"Refused roles {role_descriptions} to {user} "
                         f"because max_users_with_role reached for at least one role")
            if options.update_reactions and not all(r_d.object_reference in user.roles for r_d in role_descriptions):
                await reaction.remove(user)  # manage_messages required
            return False
        return True

    async def execute_action_on_add(self, reaction: Reaction, user: Union[Member, User], role_menu: MenuType,
                                    options: MenuOptions, users_who_reacted: Dict[User, Reaction]):
        role_descriptions = role_menu[reaction.emoji]
        try:
            await user.add_roles(*(role_descr.object_reference for role_descr in role_descriptions))
        except Forbidden as err:
            logger.warning(f"Impossible to add roles: {err}")
            if options.update_reactions:
                await reaction.remove(user)
        users_who_reacted[user] = reaction

    async def advanced_reaction_remove(self, reaction: Reaction, user: Union[Member, User], role_menu: MenuType,
                                       options: RoleMenuOptions, users_who_reacted: Dict[User, Reaction]):
        role_descriptions = role_menu[reaction.emoji]
        if options.remove_role_on_reaction_removal:
            try:
                await user.remove_roles(*(role_descr.object_reference for role_descr in role_descriptions))
            except Forbidden as err:
                logger.warning(f"Impossible to remove roles: {err}")
            logger.debug(f"Removed roles {role_descriptions} from {user} because of reaction removal")
