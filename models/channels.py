from typing import Dict, Union, Optional, Any

import discord
from discord import (PermissionOverwrite, Member, Role, CategoryChannel, ChannelType, Guild, Forbidden, HTTPException,
                     InvalidArgument, TextChannel, VoiceChannel)
from discord.abc import GuildChannel

from helpers import format_channel
from logger import logger
from models.abstract_models import DiscordObjectDict, SpecifiedDictCollection
from models.permissions import PermissionOverwriteDescription
from models.roles import RoleDescription, AbstractRoleCollection

"""
Channel permissions
-------------------
By default:
- channel permissions are synced when created
- if overwrites, it overwrites the sync_permissions parameter.
- bug in discord.py v1.3.3: GuildChannel.edit seems to work with 'sync_permissions' only if 'position' is not defined. Patch done.
- bug in discord.py v1.3.3: CategoryChannel.edit does not work with 'overwrites' argument. Patch done.
"""


class ChannelDescription(DiscordObjectDict):
    """Describes a guild channel."""
    _updatable_keys = ["name", "_overwrites", "_category_description", "reason", "position", "topic",
                       "slowmode_delay", "nsfw", "bit_rate", "user_limit"]
    _export_keys = ["name", "overwrites", "category", "sync_permissions", "reason", "position", "topic",
                    "slowmode_delay", "nsfw"]

    def _update_description(self, kwargs):
        name = kwargs.pop("name", self.name)
        overwrites = kwargs.pop("overwrites", self._overwrites)
        category = kwargs.pop("category", self._category_description)
        reason = kwargs.pop("reason", self.reason)

        # Common attributes
        self.name: str = name.strip()
        self._overwrites = overwrites

        self._category_description: ChannelDescription = category  # not for CategoryChanel type
        self._category: Optional[CategoryChannel] = None
        self.reason: str = reason

        # Text attributes
        if self._channel_type is ChannelType.text:
            self.name = self.name.lower().replace(" ", "-")

        # Voice attributes
        if self._channel_type is ChannelType.voice:
            self.bit_rate: int = kwargs.pop("bit_rate", self.bit_rate)
            self.user_limit: int = kwargs.pop("user_limit", self.user_limit)

        # Channel attributes
        if self._channel_type in (ChannelType.voice, ChannelType.text):
            self.position: int = kwargs.pop("position", self.position)
            self.topic: str = kwargs.pop("topic", self.topic)
            self.slowmode_delay: int = kwargs.pop("slowmode_delay", self.slowmode_delay)  # <= 21600
            self.nsfw: bool = kwargs.pop("nsfw", self.nsfw)
            # self.sync_permissions: bool = sync_permissions  # Deprecated: sync_permissions is True by default

    def __init__(self, name,
                 channel_type: Union[int, str, ChannelType],
                 overwrites: Optional[Dict[RoleDescription, PermissionOverwriteDescription]] = None,
                 category: Optional['ChannelDescription'] = None,
                 position=0, topic=None, slowmode_delay=0, nsfw=False, bit_rate=None, user_limit=None,
                 reason=None, sync_permissions=None, **kwargs):
        """

        :param name: channel name
        :param channel_type: ChannelType
        :param overwrites:
        :param category:
        :param reason:
        :param position:
        :param topic:
        :param slowmode_delay:
        :param nsfw:
        :param bit_rate:
        :param user_limit:
        :param sync_permissions: DEPRECATED
        """
        super().__init__(**kwargs)

        self._channel_type: ChannelType = channel_type if isinstance(channel_type, ChannelType) \
            else ChannelType[channel_type] if isinstance(channel_type, str) else ChannelType(channel_type)

        # Common attributes
        self.name: str = ""
        self._overwrites: Dict[RoleDescription, PermissionOverwriteDescription] = {}
        self._category_description: ChannelDescription = None  # not for CategoryChanel type
        self._category: Optional[CategoryChannel] = None
        self.reason: str = ""
        # Text attributes
        if self._channel_type is ChannelType.text:
            self.name = self.name.lower().replace(" ", "-")
        # Voice attributes
        if self._channel_type is ChannelType.voice:
            self.bit_rate = -1
            self.user_limit = -1
        # Channel attributes
        if self._channel_type in (ChannelType.voice, ChannelType.text):
            self.position: int = -1
            self.topic: str = ""
            self.slowmode_delay: int = -1  # <= 21600
            self.nsfw: bool = None
            # self.sync_permissions: bool = sync_permissions  # Deprecated: sync_permissions is True by default
        kwargs.update(dict(name=name, overwrites=overwrites, category=category, reason=reason, position=position,
                           topic=topic, slowmode_delay=slowmode_delay, nsfw=nsfw, bit_rate=bit_rate,
                           user_limit=user_limit))
        self._update_description(kwargs)

    def __str__(self):
        return f"{self.name} ({self.category.name if self.category else 'NoCategory'}) " \
               f"[ref={self.object_reference.id if self.object_reference else 'NoRef'}]"

    # Properties
    @property
    def sync_permissions(self):
        # Permissions are always synced, unless overwrites is defined.
        if self._overwrites:
            return False
        return True

    @staticmethod
    def _format_overwrites(overwrites: Optional[Dict[RoleDescription, PermissionOverwriteDescription]],
                           none_is_empty=False) -> Optional[Dict[Union[Member, Role], PermissionOverwrite]]:
        if overwrites is None:
            if none_is_empty:  # None equivalent to no permissions (not the default behaviour)
                return {}
            return None
        new_overwrites = {}
        for role, permissions in overwrites.items():
            if isinstance(role, RoleDescription):
                role_obj = role.object_reference
                if not role_obj:
                    logger.debug(f"Role {role} not initialized!")
                    continue
            else:
                role_obj = role
            if isinstance(permissions, PermissionOverwriteDescription):
                permissions = PermissionOverwrite(**permissions.to_dict())
            new_overwrites.update({role_obj: permissions})
        return new_overwrites

    @staticmethod
    def _format_category_channel(category_channel: Optional['ChannelDescription']) -> Optional[CategoryChannel]:
        if category_channel is None:
            return None
        if isinstance(category_channel, CategoryChannel):
            return category_channel

        channel = category_channel.object_reference
        if channel is None:
            logger.debug(f"WARN: Category channel {category_channel} not initialized!")
            return None
        return channel

    @property
    def category_description(self):
        return self._category_description

    @category_description.setter
    def category_description(self, value):
        if not isinstance(value, ChannelDescription) and value is not None:
            logger.error(f"Bad value for category_description: {value}")
            return
        self._category_description = value

    @property
    def object_reference(self) -> Optional[Union[CategoryChannel, TextChannel, VoiceChannel, GuildChannel]]:
        return super().object_reference

    @object_reference.setter
    def object_reference(self, object_reference: Union[CategoryChannel, TextChannel, VoiceChannel, GuildChannel]):
        self._object_reference = object_reference

    @property
    def channel_type(self):
        return self._channel_type

    @property
    def category(self):
        return self._format_category_channel(self._category_description)

    @property
    def overwrites(self):
        return self._format_overwrites(self._overwrites)

    # Factories
    @classmethod
    def from_id(cls, guild: Guild, channel_id):
        return cls.from_channel(guild.get_role(channel_id))

    @classmethod
    def from_channel(cls, channel: Union[CategoryChannel, TextChannel, VoiceChannel, GuildChannel]):
        if channel is None:
            return None
        channel_descr = cls(name=channel.name,
                            channel_type=channel.type,
                            overwrites=channel.overwrites,
                            category=channel.category,
                            position=channel.position,
                            topic=getattr(channel, "topic", None),
                            slowmode_delay=getattr(channel, "slowmode_delay", None),
                            nsfw=getattr(channel, "nsfw", None),
                            user_limit=getattr(channel, "user_limit", None),
                            sync_permissions=channel.permissions_synced
                            )
        channel_descr.object_reference = channel
        return channel_descr

    @classmethod
    def from_dict(cls, dico: Dict[str, Any], category_collection: Optional['AbstractChannelCollection'] = None,
                  role_collection: Optional[AbstractRoleCollection] = None):
        if dico is None:
            return None

        # Overwrites
        overwrites = dico.get('overwrites', {})
        if not role_collection:
            if overwrites:
                logger.error(f"Impossible to add {overwrites}: no RoleCollection provided!")
            overwrites_dict = None
        else:
            overwrites_dict = {}
            for role_key, permission_dict in dico.get('overwrites', {}).items():
                role_descr = role_collection.get(role_key, default=None)
                if role_descr is None:
                    logger.error(f"Unknown Role key '{role_key}'! PermissionOverwrites cannot be set for this role.")
                    continue
                permission_descr = PermissionOverwriteDescription.from_dict(permission_dict)
                overwrites_dict[role_descr] = permission_descr

        # Channel type
        channel_type = dico['type']
        # 0: text, 2: voice, 4: category
        channel_type = ChannelType(channel_type) if isinstance(channel_type, int) else ChannelType[str(channel_type)]

        # Category
        category = dico.get('category', None)
        if not category_collection or not category:
            if category:
                logger.error(f"Impossible to add {category}: no ChannelCollection provided!")
            category = None
        else:
            category = category_collection.get(category, default=None)

        role_descr = cls(name=dico.get('name', 'new_channel'),
                         channel_type=channel_type,
                         overwrites=overwrites_dict,
                         category=category,
                         position=dico.get('position', 1),
                         topic=dico.get('topic', None),
                         slowmode_delay=dico.get('slowmode_delay', None),
                         nsfw=dico.get('nsfw', None),
                         user_limit=dico.get('user_limit', None),
                         sync_permissions=dico.get('sync_permissions', False)
                         )
        return role_descr

    # Export
    @staticmethod
    def _handle_category_overwrites(options):
        overwrites = options.get('overwrites', None)
        if overwrites:
            perms = []
            for target, perm in overwrites.items():
                if not isinstance(perm, PermissionOverwrite):
                    raise InvalidArgument('Expected PermissionOverwrite received {0.__name__}'.format(type(perm)))

                allow, deny = perm.pair()
                payload = {
                    'allow': allow.value,
                    'deny': deny.value,
                    'id': target.id
                }

                if isinstance(target, Role):
                    payload['type'] = 'role'
                else:
                    payload['type'] = 'member'

                perms.append(payload)
            options['permission_overwrites'] = perms

    def to_dict(self, update=False, to_json=False):
        dico = super().to_dict()
        if self.channel_type is ChannelType.category:
            dico.pop("category", None)
            dico.pop("sync_permissions", None)
        # Fix bug (overwrites not implemented for category channels) in discord.py 1.3.3
        if self.channel_type is ChannelType.category and update:
            self._handle_category_overwrites(dico)
        if to_json:
            dico['type'] = str(self.channel_type)
            dico['category'] = None if self.category_description is None \
                else getattr(self.category_description, "key", None)
            dico['key'] = self.key
            if self._overwrites:
                dico['overwrites'] = {role_descr.key: permissions.to_dict(to_json=True)
                                      for role_descr, permissions in self._overwrites.items()
                                      if role_descr.key}
        return dico

    # Comparisons
    def _compare_overwrites(self, ref_overwrites, errors, allowed_role_descriptions):
        allowed_role_descriptions = allowed_role_descriptions or None
        if not self._overwrites and self.category_description:
            descr_overwrites = self.category_description.overwrites
        else:
            descr_overwrites = self.overwrites
        descr_overwrites = descr_overwrites or {}
        for key, descr_permission in descr_overwrites.items():
            if key in ref_overwrites:
                ref_permission = ref_overwrites[key]
                if descr_permission.pair() != ref_permission.pair():
                    errors.append(f"Incorrect permissions for role {key} in channel {self}: "
                                  f"{descr_permission.pair()} != {ref_permission.pair()}")
            else:
                errors.append(f"Role not in overwrites of channel {self}: {key}")
        for key in ref_overwrites:
            if key not in descr_overwrites and key in [r.object_reference for r in allowed_role_descriptions]:
                errors.append(f"Extra role in overwrites of channel {self}: {key}")

    def compare_to_reference(self, reference, allowed_role_descriptions=None):
        allowed_role_descriptions = allowed_role_descriptions or []
        errors = []
        if reference.category != self.category:
            errors.append(f"Category {format_channel(self.category, pretty=True)} "
                          f"defined for channel `{self}` is not the one found: "
                          f"{format_channel(reference.category, pretty=True)}")
        wildcard_descr = object()
        wildcard_ref = object()
        for field in self._export_keys:
            if field in ("category", "reason", "sync_permissions", "position", "topic", "nsfw"):  # ignored fields
                continue

            descr_val = getattr(self, field, wildcard_descr)
            ref_val = getattr(reference, field, wildcard_ref)
            # if field == "nsfw":
            #     descr_val = bool(descr_val)
            #     ref_val = bool(ref_val)
            if field == "overwrites":
                self._compare_overwrites(ref_val, errors, allowed_role_descriptions)
                continue
            if field == "slowmode_delay":
                descr_val = 0 if descr_val in (wildcard_descr, None) else descr_val
                ref_val = 0 if ref_val is wildcard_ref else ref_val
            if descr_val != ref_val and not (descr_val is None and ref_val is None):
                logger.info(f"Differences in detail for field {field} of channel {self}:\n"
                            f"Description: {descr_val}\nRef: {ref_val}")
                errors.append(f"Reference and description of {self} have a different field: {field}")
        return errors

    def compare_to_object_reference(self, allowed_role_descriptions):
        reference = self.object_reference
        return self.compare_to_reference(reference, allowed_role_descriptions)

    def compare_to_real_reference(self, guild: Guild, allowed_role_descriptions):
        reference = guild.get_channel(self.object_reference.id)
        return self.compare_to_reference(reference, allowed_role_descriptions)

    def compare_object_and_real_references(self, guild: Guild):
        real_reference = guild.get_channel(self.object_reference.id)
        object_reference = self.object_reference
        errors = []
        wildcard_ref = object()
        for field in self._export_keys:
            if field in ("position",):  # ignored fields
                continue
            obj_val = getattr(object_reference, field, wildcard_ref)
            real_val = getattr(real_reference, field, wildcard_ref)
            if obj_val != real_val and not (obj_val is None and real_val is None):
                logger.info(f"Differences in detail for field {field} of channel {self}:\n"
                            f"object_reference: {obj_val}\nReal object: {real_val}")
                errors.append(f"References of {object_reference} have a different field: {field}")
        return errors

    def is_in_channel(self, other, strict=False):
        if isinstance(other, discord.Message):
            other = other.channel
        if other is None:
            return None
        if strict:
            if isinstance(other, (discord.abc.GuildChannel, discord.GroupChannel)):
                return self.object_reference is other
        else:
            if isinstance(other, (discord.abc.GuildChannel, discord.GroupChannel)):
                return self.name == getattr(other, "name", None)
        return self == other

    # Object management
    async def create_object(self, guild: Guild, raises_on_category_error=False) -> bool:
        logger.debug(f"Creating guild channel: {self}")
        # Handle the problem of a category that have been deleted before creation of this channel
        if self.category and not raises_on_category_error:
            if not guild.get_channel(self.category.id):
                logger.warning(f"Category {self.category.name} has been deleted! Setting it to None")
                self._category_description = None
        # Channel creation
        try:
            channel_type = self.channel_type
            if channel_type is ChannelType.text:
                channel_object = await guild.create_text_channel(**self.to_dict())
                await channel_object.edit(sync_permissions=self.to_dict().get('sync_permissions', False))
            elif channel_type is ChannelType.voice:
                channel_object = await guild.create_voice_channel(**self.to_dict())
                await channel_object.edit(sync_permissions=self.to_dict().get('sync_permissions', False))
            elif channel_type is ChannelType.category:
                channel_object = await guild.create_category_channel(**self.to_dict())
            else:
                logger.warning(f"Channel type '{channel_type}' is not supported! "
                               f"Channel {self} has not been created.")
                return False
            self.object_reference = channel_object
        except (Forbidden, HTTPException, InvalidArgument) as err:
            self.object_reference = None
            logger.warning(f"Failed to create channel '{self.name}': {err}")
            return False
        return True

    async def update_object(self, channel: Union[CategoryChannel, TextChannel, VoiceChannel, GuildChannel]) -> bool:
        """Update the channel with the elements of channel_description"""
        # WARN: ChannelDescription objects representing CategoryChannel must be assigned prior to other channels!
        # Handle the problem of a category that have been deleted before creation of this channel
        if self.category:
            if not channel.guild.get_channel(self.category.id):
                logger.warning(f"Category {self.category.name} has been deleted/is not in this guild! "
                               f"Setting it to the guild channel category: {channel.category}")
                self.category_description.object_reference = channel.category
        # Edit the channel
        self.object_reference = channel  # update reference
        try:
            await channel.edit(**self.to_dict(update=True))
            # patch a bug in discord.py v1.3.3 ?
            await channel.edit(sync_permissions=self.to_dict(update=True).get('sync_permissions', False))
        except (Forbidden, HTTPException, InvalidArgument) as err:
            logger.warning(f"Error while editing channel {channel}: {err}")
            return False
        else:
            return True


class AbstractChannelCollection(SpecifiedDictCollection):
    """Collection fo ChannelDescription objects"""
    _base_class = ChannelDescription
    _category_collection = None
    _role_collection = None

    async def reload(self, versions=None, clear=False):  # to be overridden
        self.load(versions=versions, clear=clear)
        logger.info(f"Updating channels {self.values()}: {versions}")
        for channel_description in self.values():
            channel_description: ChannelDescription
            if channel_description.object_reference:
                await channel_description.update_object(channel_description.object_reference)

    @classmethod
    def item_from_dict(cls, dico: Dict[str, Union[_base_class, Dict[str, Any]]]):
        res = {}
        for key, value in dico.items():
            key = key.upper()
            if isinstance(value, cls._base_class):
                pass
            elif isinstance(value, dict):
                value = cls._base_class.from_dict(value, category_collection=cls._category_collection,
                                                  role_collection=cls._role_collection)
            else:
                logger.error(f"Invalid type for item {(key, value)}")
                continue
            value.key = key
            res[key] = value
        return res
