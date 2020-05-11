from typing import Optional, Union, Dict, Any

import discord
from discord import Permissions, Colour, Guild, Role, Forbidden, HTTPException, InvalidArgument, NotFound

from helpers import user_to_member
from logger import logger
from models.abstract_models import DiscordObjectDict, SpecifiedDictCollection
from models.permissions import PermissionDescription


class RoleDescription(DiscordObjectDict):
    _updatable_keys = ["name", "permissions", "colour", "hoist", "mentionable", "reason", "position"]
    _export_keys = ["name", "permissions", "colour", "hoist", "mentionable", "reason", "position"]

    def __init__(self, name="new_role", permissions=None, colour=None, hoist=False,
                 mentionable=False, reason=None, position=1, **kwargs):
        super().__init__(**kwargs)
        self.name: str = name
        if isinstance(permissions, PermissionDescription):
            permissions = Permissions(**permissions.to_dict())
        self.permissions: Permissions = permissions or Permissions()
        self.colour: Colour = colour or Colour.default()
        self.hoist: bool = hoist
        self.mentionable: bool = mentionable
        self.reason: str = reason
        self.position: int = position  # only when editing

    # Properties
    @property
    def object_reference(self) -> Optional[Role]:
        return super().object_reference

    @object_reference.setter
    def object_reference(self, object_reference: Role):
        self._object_reference = object_reference

    # Factories
    @classmethod
    def from_id(cls, guild: Guild, role_id):
        return cls.from_role(guild.get_role(role_id))

    @classmethod
    def from_role(cls, role: Role):
        if role is None:
            return None
        role_descr = cls(name=role.name, permissions=role.permissions, colour=role.colour, hoist=role.hoist,
                         mentionable=role.mentionable, position=role.position)
        role_descr.object_reference = role
        return role_descr

    @classmethod
    def from_dict(cls, dico: Dict[str, Any]):
        if dico is None:
            return None
        # Colour
        colour = dico.get("colour", "default")
        colour = Colour.from_rgb(*colour) if isinstance(colour, (tuple, list)) else getattr(Colour, str(colour))()

        # Permissions
        permissions = PermissionDescription.from_dict(dico.get("permissions", 0))

        role_descr = cls(name=dico.get('name', 'new_role'),
                         permissions=permissions,
                         colour=colour,
                         hoist=dico.get('hoist', False),
                         mentionable=dico.get('mentionable', False),
                         position=dico.get('position', 1)
                         )
        return role_descr

    # Exports
    def to_dict(self, create=False, to_json=False):
        dico = super().to_dict()
        if create:
            dico.pop("position", None)
        if to_json:
            dico['key'] = self.key
        return dico

    # Comparisons
    def compare_to_reference(self, reference):
        errors = []
        wildcard_descr = object()
        wildcard_ref = object()
        for field in self._export_keys:
            if field in ("reason", "position"):
                continue
            descr_val = getattr(self, field, wildcard_descr)
            ref_val = getattr(reference, field, wildcard_ref)
            if descr_val != ref_val and not (descr_val is None and ref_val is None):
                logger.info(f"Differences in detail for field {field} of role {self}:\n"
                            f"Description: {descr_val}\nRef: {ref_val}")
                errors.append(f"Reference and description of {self} have a different field: {field}")
        return errors

    def compare_to_object_reference(self):
        reference = self.object_reference
        return self.compare_to_reference(reference)

    def compare_to_real_reference(self, guild: Guild):
        reference = guild.get_channel(self.object_reference.id)
        return self.compare_to_reference(reference)

    def compare_object_and_real_references(self, guild: Guild):
        real_reference = guild.get_role(self.object_reference.id)
        object_reference = self.object_reference
        errors = []
        wildcard_ref = object()
        for field in self._export_keys:
            # WARN: ignore position as there are some issues with position edit but with no important impact.
            # See issue #2142 of discord.py
            if field == "position":
                continue
            obj_val = getattr(object_reference, field, wildcard_ref)
            real_val = getattr(real_reference, field, wildcard_ref)
            if obj_val != real_val and not (obj_val is None and real_val is None):
                logger.info(f"Differences in detail for field {field} of role {self}:\n"
                            f"object_reference: {obj_val}\nReal object: {real_val}")
                errors.append(f"References of {object_reference} have a different field: {field}")
        return errors

    def has_the_role(self, other: Union[discord.User, discord.Member, discord.Role, 'RoleDescription', str],
                     guild=None, strict=False) -> Optional[bool]:
        """Returns whether other contains, is or has the role"""
        if isinstance(other, discord.User):
            other = user_to_member(guild, other)
        if other is None:
            return None
        if strict:  # equality of ids
            if isinstance(other, discord.Member):
                return self.object_reference in (role for role in other.roles)
            if isinstance(other, discord.Role):
                return self.object_reference == other
        else:  # equality in description name
            if isinstance(other, discord.Member):
                return self.name in (role.name for role in other.roles)
            if isinstance(other, discord.Role):
                return self.name == other.name
        return self.name == other

    # Role management
    async def create_object(self, guild: Guild):
        # You must have the manage_roles permission to do this.
        if isinstance(self, DefaultRoleDescription):
            logger.debug("Default role (@everyone) set!")
            self.object_reference = guild.default_role
        else:
            logger.debug(f"Creating guild role: {self}")
            self.object_reference = await guild.create_role(**self.to_dict(create=True))

    async def update_object(self, role: Role) -> bool:
        # Edit the role
        self.object_reference = role  # update reference
        try:
            await role.edit(**self.to_dict())
        except Forbidden as err:
            logger.error(f"Impossible to update role {role}! "
                         f"Ensure bot role is higher than this one (#{role.position})! Error: {err} ")
            self.object_reference = None
            return False
        except NotFound as err:
            self.object_reference = None
            logger.error(f"Error while editing role {role} (Not found, maybe it was deleted ?): {err}")
            return False
        except (HTTPException, InvalidArgument) as err:
            logger.error(f"Error while editing role {role}: {err}")
            if "Missing Permissions" in err.text:
                self.object_reference = None
            # keep object_reference as the error is probably not critical
            return False
        else:
            return True


class AbstractRoleCollection(SpecifiedDictCollection):
    _base_class = RoleDescription

    async def reload(self, versions=None, clear=True):  # to be overridden
        self.load(versions=versions, clear=clear)
        logger.info(f"Updating roles {self.values()}: {versions}")
        for role_description in self.values():
            role_description: RoleDescription
            if role_description.object_reference:
                await role_description.update_object(role_description.object_reference)

    @classmethod
    def item_from_dict(cls, dico):
        res = {}
        for key, value in dico.items():
            key = key.upper()
            if isinstance(value, cls._base_class):
                pass
            elif not isinstance(value, dict):
                logger.error(f"Invalid type for item {(key, value)}")
                continue
            elif key == "DEFAULT":  # default role (@everyone)
                value = DefaultRoleDescription.from_dict(value)
            else:
                value = cls._base_class.from_dict(value)
            value.key = key
            res[key] = value
        return res


class DefaultRoleDescription(RoleDescription):
    def __init__(self, **kwargs):
        kwargs.pop("position", None)
        kwargs.pop("name", None)
        super().__init__(name="@everyone", **kwargs)

    def to_dict(self, **kwargs):
        dico = super().to_dict(**kwargs)
        dico.pop("position", None)
        return dico
