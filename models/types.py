import enum
from collections import defaultdict
from enum import Enum
from typing import Optional, List, Dict, Type, Union

from discord import Guild

from logger import logger


class CustomEnum(enum.Enum):
    def __str__(self):
        return str(self.value)

    @classmethod
    def to_list(cls):
        return [enum_inst.value for enum_inst in cls]

    @classmethod
    def to_str(cls):
        return "\n".join([str(enum_inst) for enum_inst in cls])

    @classmethod
    def to_dict(cls):
        return {ele.name: ele.value for ele in cls}


class KnowInstances(type):
    _instances = defaultdict(list)

    def __call__(cls, *args, **kwargs):
        new_inst = super(KnowInstances, cls).__call__(*args, **kwargs)
        cls._instances[cls].append(new_inst)
        return new_inst

    @property
    def instances(cls):
        return cls._instances[cls]


class Singleton(KnowInstances):
    """Metaclass that authorize only one instance of a class."""

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls].append(super(Singleton, cls).__call__(*args, **kwargs))
        return cls._instances[cls][0]


class AbstractGuildListener:
    """Base abstract class for listeners in a guild.

    A listener (=object which is instance of this class or subclass) is a class that can react on Discord events.
    A listener is similar to a Discord CoG, but less restricted and maybe less optimised.
    """
    _instances: Dict[int, Dict[Type['AbstractGuildListener'],
                               List['AbstractGuildListener']]] = defaultdict(lambda: defaultdict(list))

    def __init__(self, key=None):
        self._guild: Optional[Guild] = None
        # Auto-generated order
        self._order_auto = len(self._instances)
        self._key = key
        self._saved_dict = {}

    def set(self, guild: Union[Guild, 'GuildWrapper']) -> 'AbstractGuildListener':
        """Set a guild"""
        if self in self._instances[guild.id][self.__class__]:
            if self._guild != guild:
                logger.error(f"Changing listener guild once set is not allowed!")
            return self
        self._guild = guild
        self._instances[guild.id][self.__class__].append(self)
        return self

    @classmethod
    def reset_guild(cls, guild_ref: Union[int, Guild]):
        """Reset ALL listeners of the guild."""
        if isinstance(guild_ref, Guild):
            guild_ref = guild_ref.id
        _instances = cls._instances.pop(guild_ref, None)
        # for listener_class, listener_instances in _instances.items():
        #     for listener in listener_instances:
        #         listener._guild = None
        logger.info(f"Listeners of guild {guild_ref} have been removed.")

    @classmethod
    def instances(cls, guild):
        # WARN: can be a security issue (or a feature!): listener in other guilds are accessible directly
        return cls._instances[guild.id][cls]

    @property
    def guild(self):
        if not self._guild:
            logger.error(f"No guild set for listener {self.__class__.__name__} {self}")
        return self._guild


class GuildSingleton(AbstractGuildListener):
    """Metaclass that authorize only one instance of a class per guild."""

    @classmethod
    def get(cls, guild):
        # WARN: can be a security issue (or a feature!): listener in other guilds are accessible directly
        if guild.id not in cls._instances or cls not in cls._instances[guild.id]:
            new_inst = cls()
            new_inst.set(guild)
            cls._instances[guild.id][cls].append(new_inst)
        return cls._instances[guild.id][cls][0]

    def set(self, guild: Guild) -> 'AbstractGuildListener':
        if not len(self._instances[guild.id][self.__class__]):
            super().set(guild)
        else:
            logger.debug(f"{self.__class__.__name__} can have only one instance")
        return self._instances[guild.id][self.__class__][0]


class ControlEmojiEnum(Enum):
    def __str__(self):
        return f"{self.emoji}: {self.method}"

    @property
    def emoji(self):
        return self.value[0]

    @property
    def method(self):
        return self.value[1]

    @classmethod
    def to_dict(cls):
        return {ele.name: ele.emoji for ele in cls}

    @classmethod
    def to_emoji_dict(cls):
        return {ele.emoji: ele.method for ele in cls}

    @classmethod
    def to_list(cls):
        return [(ele.emoji, ele.method) for ele in cls]

    @classmethod
    def to_str(cls):
        return "\n".join([str(enum_inst) for enum_inst in cls if enum_inst.method])
