import enum


class Event(enum.Enum):
    MESSAGE = "on_message"
    READY = "on_ready"
    CONNECT = "on_connect"
    DISCONNECT = "on_disconnect"
    MEMBER_JOIN = "on_member_join"
    MEMBER_REMOVE = "on_member_remove"
    TYPING = "on_typing"
    MESSAGE_EDIT = "on_message_edit"
    REACTION_ADD = "on_reaction_add"
    REACTION_REMOVE = "on_reaction_remove"
    RAW_REACTION_ADD = "on_raw_reaction_add"
    RAW_REACTION_REMOVE = "on_raw_reaction_remove"
    REACTION_CLEAR = "on_reaction_clear"
    MEMBER_UPDATE = "on_member_update"
    MEMBER_BAN = "on_member_ban"
    MEMBER_UNBAN = "on_member_unban"
    VOICE_STATE_UPDATE = "on_voice_state_update"
