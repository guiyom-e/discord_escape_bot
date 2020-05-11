import asyncio

from game_models.abstract_filtered_listener import AbstractFilteredListener
from helpers.discord_helpers import return_
from logger import logger


class AbstractMiniGame(AbstractFilteredListener):
    """Subclass of AbstractFilteredListener describing a game.

    Two main features are added:
    - on_victory and on_helped_victory methods
    - simple_mode attribute

    Victory feature:
    ----------------

    Default schemes:
    1) A user terminates successfully the game.
    2) `on_victory` (final) is called.
    3) `on_victory` calls `_on_victory` method (to be overridden, do nothing by default).
    4) `on_victory` calls `stop` method.

    1) The game master triggers an "help victory".
    2) `on_helped_victory` (final, no args) is called.
    3) if the game is active (`active` attr is True),
       `_on_helped_victory` is called (to be overridden, calls `_on_victory` by default).
    4) `on_helped_victory` calls `stop` method.

    Simple mode feature:
    --------------------

    By default, a game has two modes: standard and simple (standard by default).
    To define the game as simple, set simple_mode to True.
    To define the game as standard, set simple_mode to False. (default)
    To precise that the game has only a unique standard mode, set simple_mode to None.
    """

    def __init__(self, **kwargs):
        self._simple_mode = kwargs.pop("simple_mode", False)
        super().__init__(**kwargs)
        self.__lock_victory = asyncio.Lock()

    @property
    def simple_mode(self):
        return self._simple_mode

    @simple_mode.setter
    def simple_mode(self, value):
        self._simple_mode = bool(value)
        logger.info(f"Changing {self._name} simple mode to {self._simple_mode}")

    def __repr__(self):
        return f"**Mini-game {self.__class__.__name__}**\n{self._description}"

    async def _on_victory(self, *args, **kwargs):
        pass

    async def on_victory(self, *args, **kwargs):  # final
        if self.__lock_victory.locked():
            logger.debug(f"Victory lock already acquired for listener {self.name}")
            return
        logger.debug(f"Acquiring victory lock for listener {self.name}")
        async with self.__lock_victory:
            await return_(self._on_victory(*args, **kwargs))
            logger.info(f"Victory for game {self.__class__.__name__}")
            await self.stop()
        logger.debug(f"Victory lock released for listener {self.name}")

    async def _on_helped_victory(self):
        return await return_(self._on_victory())

    async def on_helped_victory(self):  # to be overridden or called with super
        if self.__lock_victory.locked():
            logger.debug(f"Victory lock already acquired for listener {self.name}")
            return
        logger.debug(f"Acquiring victory lock for listener {self.name}")
        async with self.__lock_victory:
            if self.active:
                await return_(self._on_helped_victory())
            await self.stop()
        logger.debug(f"Victory lock released for listener {self.name}")
