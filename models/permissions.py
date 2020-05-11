from typing import Dict, Union, Optional

from models.abstract_models import DiscordObjectDict


class PermissionDescription(DiscordObjectDict):
    """Describes a Permission object"""
    _export_keys = ["administrator", "view_audit_log", "manage_guild", "manage_roles", "manage_channels",
                    "kick_members", "ban_members", "create_instant_invite", "change_nickname", "manage_nicknames",
                    "manage_emojis", "manage_webhooks", "view_channel", "send_messages", "send_tts_messages",
                    "manage_messages", "embed_links", "attach_files", "read_message_history",
                    "mention_everyone", "use_external_emojis", "add_reactions", "view_guild_insights",
                    "connect", "speak", "mute_members", "deafen_members", "move_members",
                    "use_voice_activation", "priority_speaker", "stream"]

    # noinspection PyUnusedLocal
    def __init__(self,
                 permissions: int = None,
                 administrator=None,
                 view_audit_log=None,
                 manage_guild=None,
                 manage_roles=None,
                 manage_channels=None,
                 kick_members=None,
                 ban_members=None,
                 create_instant_invite=None,
                 change_nickname=None,
                 manage_nicknames=None,
                 manage_emojis=None,
                 manage_webhooks=None,
                 view_channel=None,

                 send_messages=None,
                 send_tts_messages=None,
                 manage_messages=None,
                 embed_links=None,
                 attach_files=None,
                 read_message_history=None,
                 mention_everyone=None,
                 use_external_emojis=None,
                 add_reactions=None,

                 view_guild_insights=None,

                 connect=None,
                 speak=None,
                 mute_members=None,
                 deafen_members=None,
                 move_members=None,
                 use_voice_activation=None,
                 priority_speaker=None,
                 stream=None,
                 **kwargs
                 ):
        super().__init__(**kwargs)
        for key, value in vars().items():
            if key in self._export_keys:
                setattr(self, key, value)
        self._permissions = permissions

    @property
    def permissions(self):
        return self._permissions

    def keys(self):
        if self._permissions is not None:
            return ["permissions"]
        return [key for key in self._export_keys if getattr(self, key) is not None]

    def copy(self):
        return self.__class__(self._permissions, **self.to_dict())

    @classmethod
    def from_dict(cls, dico: Union[int, Dict[str, Optional[bool]]]):
        if isinstance(dico, int):
            return cls(dico)
        return cls(**dico)


class PermissionOverwriteDescription(PermissionDescription):
    """Describes a PermissionOverwrite object"""
    def keys(self):
        return [key for key in self._export_keys]  # Include None values in result
