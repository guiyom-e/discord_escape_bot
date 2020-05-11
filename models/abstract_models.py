import json
from abc import abstractmethod
from copy import copy
from typing import List, Dict, ValuesView, ItemsView, Type, Any, Union

from discord import Forbidden, HTTPException, InvalidArgument, Guild

from constants import BOT
from helpers import TranslationDict
from logger import logger
from models.types import KnowInstances


# Abstract class. Must implement __init__ and from_dict
class SpecifiedDict(metaclass=KnowInstances):
    _updatable_keys = ["object_reference"]
    _export_keys = []

    @abstractmethod
    def __init__(self, key=None, **_kwargs):
        self._object_reference = None
        # Auto-generated order
        self._order_auto = len(self.__class__.instances)
        self._key = key
        if _kwargs:
            logger.warning(f"Invalid keyword arguments: {_kwargs}")

    def update(self, obj: 'SpecifiedDict'):
        wildcard = object()
        for key in self._updatable_keys:
            new_value = getattr(obj, key, wildcard)
            if new_value is not wildcard:
                setattr(self, key, new_value)

    @property
    def object_reference(self):
        return self._object_reference

    @object_reference.setter
    def object_reference(self, object_reference):
        self._object_reference = object_reference

    @property
    def key(self) -> str:
        return str(self._key).upper()

    @key.setter
    def key(self, value):
        self._key = value

    @property
    def order(self) -> int:
        return self._order_auto

    def copy(self) -> 'SpecifiedDict':
        new_obj = copy(self)
        new_obj.object_reference = None
        return new_obj

    # Methods to use this class as a kwargs dict:
    def keys(self) -> List[str]:  # only export not-None values
        return [key for key in self._export_keys if getattr(self, key, None) is not None]

    @classmethod
    @abstractmethod
    def from_dict(cls, dico) -> 'SpecifiedDict':
        raise NotImplementedError

    def to_dict(self, to_json=False) -> Dict[str, Any]:
        dico = {key: getattr(self, key) for key in self.keys()}
        if to_json and self._key:
            dico['key'] = self.key
        return dico

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} ref={self.object_reference} " \
               f"{' '.join([f'{k}={v}' for k, v in self.to_dict().items()])}>"


# Abstract class. Must implement __init__ and from_dict
class DiscordObjectDict(SpecifiedDict):
    """Abstract class representing a description of a Discord object or an object of this project.

    # Methods that may be created in subclasses:
    - generate_object: creates a new object and return it.
    - create_object: creates a new object, updates object_reference and returns whether the creation was successful.
    - get_instance: creates a new object, updates object_reference and return it.
    - update_object: updates object_reference with current description.
    - delete_object: deletes object_reference object if it exists and returns whether the deletion was successful.
    """

    @abstractmethod
    def __init__(self, key=None, **_kwargs):
        super().__init__(key=key, **_kwargs)

    # For legacy reason. TODO: refacto
    @property
    def value(self) -> 'DiscordObjectDict':
        return self

    def __getitem__(self, item):  # TODO: really ?
        logger.warning(f"This deprecated method is used in {self} for the key: {item}")
        return getattr(self, item)

    @classmethod
    @abstractmethod
    def from_dict(cls, dico) -> 'DiscordObjectDict':
        raise NotImplementedError

    def __repr__(self) -> str:
        ref = self.object_reference.id if self.object_reference else None
        return f"<{self.__class__.__name__} ref={ref} {' '.join([f'{k}={v}' for k, v in self.to_dict().items()])}>"


class SpecifiedDictCollection(TranslationDict):
    """Collection of SpecifiedDict objects"""
    _base_class: Type[SpecifiedDict] = SpecifiedDict

    def reset_object_references(self):
        for obj in self.values():
            obj.object_reference = None

    def _update(self, item_from_dict: Dict[str, _base_class]):
        # copy object_reference
        for key, specified_dict in item_from_dict.items():
            if key in self._data:  # if the key exists, update the object
                self._data[key].update(specified_dict)
            else:  # else, create it
                self._data[key] = specified_dict

    def load(self, versions=None, clear=True):
        super().load(versions, clear=clear)
        for key, dict_value in self.default_items():
            dict_value.key = key

    async def reload(self, versions=None, clear=True):  # to be overridden
        return self.load(versions=versions, clear=clear)

    def values(self) -> ValuesView[_base_class]:
        # WARN: non ordered values!
        return self.to_dict().values()

    def items(self) -> ItemsView[str, _base_class]:
        # WARN: non ordered items!
        return self.to_dict().items()

    @classmethod
    def item_from_dict(cls, dico: Dict[str, Union[_base_class, Dict[str, Any]]]):
        res = {}
        for key, value in dico.items():
            key = key.upper()
            if isinstance(value, cls._base_class):
                pass
            elif isinstance(value, dict):
                value = cls._base_class.from_dict(value)
            else:
                logger.error(f"Invalid type for item {(key, value)}")
                continue
            value.key = key
            res[key] = value
        return res

    # Export methods
    def to_list(self) -> List[_base_class]:
        return sorted(self.values(), key=lambda inst: inst.order)

    def to_str(self) -> str:
        return "\n".join([str(value) for value in self.values()])

    def to_dict(self) -> Dict[str, _base_class]:
        # WARN: non ordered dict!
        return {ele: self.get(ele)
                for ele in self.keys() if isinstance(self.get(ele, None), self._base_class)}

    @classmethod
    def _to_json_list(cls, ls):
        res = []
        for v in ls:
            if isinstance(v, (int, str, bool)):
                res.append(v)
            if isinstance(v, (bytes, bytearray)):
                res.append(v.hex())
            if isinstance(v, cls._base_class):
                res.append(cls.to_json_dict(v.to_dict(to_json=True)))
            if isinstance(v, (list, tuple, dict)):
                res.append(cls.to_json_dict(v))
        return res

    @classmethod
    def to_json_dict(cls, dico_or_list):
        if isinstance(dico_or_list, (list, tuple)):
            return cls._to_json_list(dico_or_list)
        res = {}
        for k, v in dico_or_list.items():
            if isinstance(v, (int, str, bool)):
                res[k] = v
            if isinstance(v, (bytes, bytearray)):
                res[k] = v.hex()
            if isinstance(v, cls._base_class):
                res[k] = cls.to_json_dict(v.to_dict(to_json=True))
            if isinstance(v, (list, tuple, dict)):
                res[k] = cls.to_json_dict(v)
        return res

    def to_json(self):
        return json.dumps(self.to_json_dict(self), ensure_ascii=False)

    # legacy (use getattr instead of getitem)
    def __getattribute__(self, item):
        if isinstance(item, str) and item.isupper():
            if item in super().__getattribute__("_data"):
                return super().__getattribute__("_data")[item]
            if item.upper() in super().__getattribute__("default_keys")():
                return super().__getattribute__(item.upper())
        return super().__getattribute__(item)

    @property
    def base_class(self):
        return self._base_class


async def reorder_items(descriptions: List[DiscordObjectDict], offset=0, reverse=False):
    to_reorder = descriptions[::-1 if reverse else 1]
    logger.info(f"Reordering items: {to_reorder}")
    for i, description in enumerate(to_reorder):
        if not description.object_reference:
            logger.warning(f"Object {description} has no reference! Cannot reorder item")
            continue
        try:
            await description.object_reference.edit(position=i + offset)
        except (Forbidden, HTTPException, InvalidArgument) as err:
            if getattr(description.object_reference, "managed", False):
                logger.debug(f"Cannot edit the object {description} because it is managed by another service.")
                continue
            logger.warning(f"Permission error while reordering {description} (#{i + offset}): {err}")
            return False
    return True


async def reorder_roles(role_descriptions: List[DiscordObjectDict], guild: Guild, reverse=False):
    # Workaround implementation in issue #2142 of discord.py 1.3.3
    to_reorder = role_descriptions[::-1 if reverse else 1]
    logger.info(f"Reordering roles: {to_reorder}")
    role_description_ids = [r_d.object_reference.id for r_d in to_reorder if r_d.object_reference]

    positions = []
    for role in guild.roles:
        if role.id in role_description_ids:
            continue

        if role == guild.me.top_role:
            positions.extend(role_description_ids)

        positions.append(role.id)

    payload = [{"id": r, "position": i} for i, r in enumerate(positions)]
    try:
        await BOT.http.move_role_position(guild.id, payload)
    except Exception as err:
        logger.warning(f"Error while reordering roles {role_descriptions}: {err}")
        return False
    return True
