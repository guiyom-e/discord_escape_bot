import asyncio
from typing import List, Union

from discord import Role, Guild, Forbidden, NotFound, HTTPException

from logger import logger
from models import RoleDescription, DefaultRoleDescription
from models.abstract_models import reorder_roles
from models.guilds import GuildWrapper

LOCK = asyncio.Lock()


async def create_roles(guild: Union[Guild, GuildWrapper], role_descriptions: List[RoleDescription]):
    # You must have the manage_roles permission to do this.
    for role_description in role_descriptions:
        await role_description.create_object(guild)


async def delete_roles(guild: Union[Guild, GuildWrapper], reason=None):
    # You must have the manage_roles permission to do this.
    for role in guild.roles:
        try:
            await role.delete(reason=reason)
        except (NotFound, HTTPException) as err:
            logger.debug(f"Cannot delete role {role}: {err}")


def clear_role_descriptions(role_descriptions: List[RoleDescription]):
    for role_description in role_descriptions:
        role_description.object_reference = None


async def edit_roles(old_roles: List[Role], new_roles_descriptions: List[RoleDescription]):
    # You must have the manage_roles permission to do this.
    for role, role_description in zip(old_roles, new_roles_descriptions):
        role_description.object_reference = role  # update reference
        await role.edit(**role_description.to_dict())


async def update_roles(guild: Union[Guild, GuildWrapper], role_descriptions: List[RoleDescription],
                       delete_old=False, key="name", reorder=True, clear_references=True) -> bool:
    return await fetch_roles(guild, role_descriptions, key=key, clear_references=clear_references,
                             update=True, create=True, delete_old=delete_old, reorder=reorder)


async def fetch_roles(guild: Union[Guild, GuildWrapper], role_descriptions: List[RoleDescription],
                      key="name", clear_references=True,
                      update=False, create=False, delete_old=False, reorder=False
                      ) -> bool:
    """If the server is already configured, it is just necessary to retrieve Role object references"""
    # WARN: role_descriptions must be a sorted list from highest role to lowest.
    # WARN: if multiple roles have the same key, they will be attributed in the order they appear in guild.roles
    async with LOCK:  # Lock role_descriptions  # todo: lock not working: check threading doc
        roles_ok = True
        if clear_references:  # clear pre-existing object references
            clear_role_descriptions(role_descriptions)
        # Get all manageable roles (i.e. lower than bot role). The first element of this list is the highest role.
        guild_roles = [role for role in guild.roles[::-1] if role < guild.me.top_role]
        logger.debug(f"BEFORE FETCH ROLES: "
                     f"Current top role for bot: {guild.me.top_role}(#{guild.me.top_role.position})\n"
                     f"Options: clear_ref: {clear_references}; update: {update}; delete_old: {delete_old}\n"
                     f"Manageable guild roles: {[f'{role} (#{role.position})' for role in guild_roles]}")
        for role_description in role_descriptions:
            # if the object reference already exists.
            if role_description.object_reference and update:
                if await role_description.update_object(role_description.object_reference):
                    continue

            if isinstance(role_description, DefaultRoleDescription):  # Role @everyone
                role_description.object_reference = guild.default_role
                if update:
                    await role_description.update_object(guild.default_role)
                continue
            r_d_value = getattr(role_description, key)
            ind_to_pop = None
            for i, role in enumerate(guild_roles):
                if getattr(role, key) == r_d_value:
                    ind_to_pop = i
                    role_description.object_reference = role
                    break  # WARN: the first role with a matching key is used
            if ind_to_pop:  # remove role already attributed
                role = guild_roles.pop(ind_to_pop)
                if update:
                    await role_description.update_object(role)
            if role_description.object_reference is None:
                if create:
                    await role_description.create_object(guild)
                else:
                    logger.info(f"Role {role_description} doesn't exist in the guild")
                    roles_ok = False
        if roles_ok:
            logger.info(f"Roles {'updated' if update else 'fetched'} successfully: {role_descriptions}")
        else:
            logger.warning(f"Roles {'updated' if update else 'fetched'} with errors: {role_descriptions}")
        if reorder:
            roles_to_order = [r_d for r_d in role_descriptions if not isinstance(r_d, DefaultRoleDescription)]
            if not await reorder_roles(roles_to_order, guild, reverse=True):  # start at 1 (0 is DefaultRole)
                roles_ok = False
                logger.info("Roles reordered with errors")
            else:
                logger.info("Roles reordered successfully")
        if delete_old:
            references = [ch_d.object_reference for ch_d in role_descriptions]
            for role in guild_roles:
                if role not in references:
                    try:
                        await role.delete(reason="fetch_roles: delete_old arg is True")
                    except Forbidden as err:
                        logger.info(f"Can not delete role {role}(permission denied): {err}")
                    except Exception as err:
                        logger.warning(f"Can not delete role {role}: {err}")
        logger.debug(f"AFTER FETCH ROLES: All guild roles: {[f'{role} (#{role.position})' for role in guild.roles]}")
        return roles_ok
