from enum import Enum
from typing import Optional, List, Union


class VersionDescription:
    def __init__(self, versions: Optional[Union[str, List[str]]], emoji: str, name: str, description: str = "",
                 credits: str = ""):
        self.versions = versions
        self.emoji = emoji
        self.name = name
        self.description = description
        self.credits = credits


class VersionsEnum(Enum):

    def __str__(self):
        return f"{self.emoji}: **{self.display_name}** {self.description}\n" \
               f"`code: {self.versions}`{self.credits and f' *Crédits {self.credits}*'}"

    @property
    def emoji(self):
        return self.value.emoji

    @property
    def versions(self):
        return self.value.versions

    @property
    def version(self):
        """alias to 'versions' property"""
        return self.versions

    @property
    def display_name(self):
        return self.value.name

    @property
    def description(self):
        return self.value.description

    @property
    def credits(self):
        return self.value.credits

    # Class methods
    @classmethod
    def to_emoji_dict(cls):
        return {ele.emoji: ele.value for ele in cls if ele.versions is not None}

    @classmethod
    def to_list(cls):
        return [ele for ele in cls if ele.versions is not None]

    @classmethod
    def to_str(cls):
        return "\n".join([str(enum_inst) for enum_inst in cls if enum_inst.versions is not None])

    # D = ("🇩", None)
    # E = ("🇪", None)
    # F = ("🇫", None)
    # G = ("🇬", None)
    # H = ("🇭", None)
    # I = ("🇮", None)
    FR = VersionDescription("fr", emoji="⭕", name="Version française vierge",
                            description="Version pour développeurs et testeurs")
    NONE = VersionDescription("", emoji="🚫", name="Default version",
                              description="For test purposes only")
