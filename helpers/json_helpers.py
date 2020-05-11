import json
import os
from collections import OrderedDict
from threading import Lock
from typing import Optional, Union, List, Dict, Any

from constants import GAME_LANGUAGE
from logger import logger

LOCK = Lock()


def load_json(json_path):
    try:
        with open(json_path, encoding='utf-8', errors='ignore') as json_file:
            return json.loads(json_file.read(), object_pairs_hook=OrderedDict)
    except FileNotFoundError as err:
        logger.info(f"JSON file '{json_path}' not found: {err}")
        return {}
    except Exception as err:
        logger.error(f"Error while loading JSON file '{json_path}': {err}")
        logger.exception(err)
        return {}


class TranslationDict:
    _ext = ".json"

    def __init__(self, versions: Optional[Union[str, List[str]]] = None, path: str = ""):
        """

        :param versions: list of versions (str).
        The last versions in the list override the first ones if keys are identical.
        :param path: directory path to the JSON version files with the name "[version].json"
        where [version] is the version string.
        If the version file is incorrect or doesn't exist, the error is logged and ignored.
        """
        self._path = path
        versions = versions or GAME_LANGUAGE
        self._versions = [versions] if isinstance(versions, str) else versions or []
        self._data = {}
        self.load()

    def __getitem__(self, item: str):
        if item is None:
            logger.error(f"Item is None! Returning '_??_' value.")
            return "_??_"
        if item in self._data:
            return self._data[item]
        if item.upper() in self.default_keys():
            return getattr(self, item.upper())
        logger.warning(f"Unknown value for item {item}. Returning '_?_' value.")
        return "_?_"

    def get(self, item: str, default=None):
        if item is None:
            logger.error(f"Item is None! Returning defaut value {default}.")
            return default
        if item in self._data:
            return self._data[item]
        if item.upper() in self.default_keys():
            return getattr(self, item.upper())
        return default

    @property
    def data(self):
        return {k: self[k] for k in self.keys()}

    def default_keys(self):
        return [key for key in dir(self) if key.isupper()]

    def default_values(self):
        return [getattr(self, key) for key in self.default_keys()]

    def default_items(self):
        return [(key, getattr(self, key)) for key in self.default_keys()]

    def keys(self) -> List[str]:
        return [k for k in self.default_keys() if k not in self._data.keys()] + list(self._data.keys())

    @classmethod
    def item_from_dict(cls, dico: Dict[str, Any]):
        return {key.upper(): value for key, value in dico.items()}

    def _load(self, json_path):
        json_dict = load_json(json_path)
        return self.item_from_dict(json_dict)

    def _update(self, item_from_dict):
        self._data.update(item_from_dict)

    def load(self, versions=None, clear=True):
        original_keys = set(self._data.keys())
        new_keys = set()
        if versions is None:
            versions = self._versions
        versions = versions or GAME_LANGUAGE
        if isinstance(versions, str):
            versions = [versions]
        for version in versions:
            version_loaded = self._load(os.path.join(self._path, version + self._ext))
            new_keys.update(version_loaded.keys())
            self._update(version_loaded)
        if clear:
            self._versions = versions
        else:
            self._versions.extend(versions)
        if clear:
            for key in original_keys - new_keys:
                self._data.pop(key)

    def load_from_dict(self, dico, clear=True):
        with LOCK:
            if clear:
                self._data.clear()
            self._data.update(dico)

    @classmethod
    def from_dict(cls, dico):
        res = cls()
        res.load_from_dict(dico, clear=True)
        return res

    def __repr__(self):
        return f"<{self.__class__.__name__} path={self._path} lang={self._versions} message='{self.data}'>"

    def __str__(self):
        return f"<{self.__class__.__name__} path={self._path} lang={self._versions} message='{self.data}'>"
