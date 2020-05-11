from minigames import *
from models import CustomEnum
from utils_listeners import *


class ListenerClassEnum(CustomEnum):
    @classmethod
    def get(cls, name, default=None):
        try:
            return cls[name]
        except KeyError:
            return default


class ListenersEnum(ListenerClassEnum):
    INTRO = IntroductionGame
    COUNT_EVERYONE = CountEveryone
    FIND_THE_RECIPE = FindTheRecipe
    ATTIC = AtticGame
    MAP = MapGame
    CHEST = ChestGame
    ENIGMAS = EnigmasGame
    MAP_ENIGMAS = MapEnigmasGame
    ASK_WORDS = AskWordsGame
    OFFICES = OfficesGame
    CONCLUSION = EndGame
    CONCLUSION_DAEMON = CongratulationsGame
    STORY_TELLING = StoryTelling
    ISLAND_TOOLS = IslandTools
    MINE_TOOLS = MineTools
    MINE_MESSAGES = MineMessages


class UtilsEnum(ListenerClassEnum):
    ADMIN_GUILD = DebugFunctions
    ADMIN_GAME = GameUtils
    MUSIC = MusicTools
