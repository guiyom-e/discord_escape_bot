import functools
from typing import Type, List, Optional, Union

from discord import Guild

from game_models import AbstractListener
from helpers import TranslationDict
from logger import logger
from models import GuildWrapper, CustomEnum
from models.abstract_models import DiscordObjectDict, SpecifiedDict, SpecifiedDictCollection


def warn_if_no_guild(method):
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        if self._guild is None:
            logger.error(f"Guild is not set for method {method} ({wrapper.__name__}) for {self}!")
        return method(self, *args, **kwargs)

    return wrapper


class ListenerDescription(SpecifiedDict):
    _listener_enum = None  # Enum of all possible listener classes
    _updatable_keys = ["_game_type", "_order", "_init_kwargs"]

    def _update_description(self, kwargs):
        self._game_type = kwargs.pop("game_type", self._game_type)
        self._order = kwargs.pop("order", self._order)
        messages = kwargs.pop("messages", None)
        if isinstance(messages, TranslationDict):
            pass
        elif isinstance(messages, dict):  # messages dictionary
            messages = TranslationDict.from_dict(messages)
        elif isinstance(messages, str):  # path. the default version is used
            messages = TranslationDict(path=messages)
        elif isinstance(messages, (list, tuple)):  # list of versions. The path must be included in versions.
            messages = TranslationDict(versions=messages)
        self._init_kwargs.update(kwargs)
        if messages:
            self._init_kwargs['messages'] = messages

    def __init__(self, game_type, name="", description="", auto_start=False, show_in_listener_manager=True,
                 messages=None, key=None, order=None, **kwargs):
        self._game_type = ""
        self._order = -1
        self._init_kwargs = {}
        kwargs.update({"game_type": game_type, "order": order, "name": name, "description": description,
                       "auto_start": auto_start, "show_in_listener_manager": show_in_listener_manager,
                       "messages": messages})
        self._update_description(kwargs)
        super().__init__(key=key)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} ref={getattr(self.object_reference, 'name', None)}>"

    @classmethod
    def set_listener_enum(cls, listener_enum):  # todo: better way ?
        cls._listener_enum = listener_enum

    # Properties
    @property
    def object_reference(self) -> Optional[AbstractListener]:
        return super().object_reference

    @object_reference.setter
    def object_reference(self, object_reference: AbstractListener):
        self._object_reference = object_reference

    @property
    def order(self) -> int:
        return self._order or self._order_auto

    # Factories
    @classmethod
    def from_dict(cls, dico):
        return cls(**dico)

    def generate_object(self, guild: Union[GuildWrapper, Guild]):
        """Returns a new object defined by the description of this class instance"""
        if not self._listener_enum:
            logger.error(f"No listener enum defined for {self}!")
            return None
        return self._listener_enum[self._game_type].value(**self._init_kwargs).set(guild)

    def get_instance(self, guild):
        """Get a new object defined by the description of this class instance"""
        self.object_reference = self.generate_object(guild)  # todo: handle multiple guilds
        return self.object_reference


class ListenerCollection(SpecifiedDictCollection):
    _base_class: Type[DiscordObjectDict] = ListenerDescription

    def __init__(self, versions: Optional[Union[str, List[str]]] = None, path: str = ""):
        super().__init__(versions=versions, path=path)
        self._guild = None

    @staticmethod
    def set_listener_enum(listener_enum: CustomEnum):
        ListenerDescription.set_listener_enum(listener_enum)

    def get_guild_instances(self, guild: GuildWrapper):
        # TODO
        return [listener_description.get_instance(guild) for listener_description in self.to_list()]
