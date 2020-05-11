from discord import Permissions, Colour

from models import PermissionDescription, RoleDescription, AbstractRoleCollection, DefaultRoleDescription

####################################
# ## DEFAULT ROLE CONFIGURATION ## #
####################################

team_permissions = PermissionDescription(
    create_instant_invite=True,
    change_nickname=True,
    view_channel=True,
    send_messages=True,
    send_tts_messages=True,
    read_message_history=True,
    embed_links=True,
    attach_files=True,
    mention_everyone=True,
    add_reactions=True,
    connect=True,
    speak=True,
    use_voice_activation=True,
)


class RoleCollectionClass(AbstractRoleCollection):
    """Enum of roles in the correct order (last ones have a lower position)"""
    # Bot role
    BOT = RoleDescription(
        name="Bot",
        permissions=Permissions(8),  # admin right
        colour=Colour.green(),
        mentionable=True,
    )

    # Developer
    DEV = RoleDescription(
        name="Admin",
        permissions=Permissions.all(),  # all rights
        colour=Colour.dark_red(),
    )

    # Game master
    MASTER = RoleDescription(
        name="Game master",
        permissions=Permissions(2147483127),  # all rights except admin
        colour=Colour.dark_red(),
        mentionable=True,
    )

    # Visitor, base role
    VISITOR = RoleDescription(
        name="Player",
        permissions=Permissions(68224000),  # change nickname, view channels, read message history, connect
        colour=Colour.red(),
    )

    DEFAULT = DefaultRoleDescription(permissions=Permissions(use_voice_activation=True))


RoleCollection = RoleCollectionClass(path="configuration/game_manager/roles")

if __name__ == '__main__':
    print(RoleCollection.to_json())
