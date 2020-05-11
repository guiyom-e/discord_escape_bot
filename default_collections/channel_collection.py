from discord import ChannelType

from default_collections.role_collection import RoleCollection
from models import AbstractChannelCollection, ChannelDescription, PermissionOverwriteDescription


########################################
# ## DEFAULT CHANNELS CONFIGURATION ## #
########################################


class CategoryChannelCollectionClass(AbstractChannelCollection):
    _base_class = ChannelDescription
    _category_collection = None
    _role_collection = RoleCollection

    DEV = ChannelDescription(
        name="Developers",
        channel_type=ChannelType.category,
        overwrites={
            RoleCollection.DEV: PermissionOverwriteDescription(view_channel=True),
            RoleCollection.BOT: PermissionOverwriteDescription(view_channel=True),
            RoleCollection.DEFAULT: PermissionOverwriteDescription(view_channel=False),
        },
    )

    MASTER = ChannelDescription(
        name="Game masters",
        channel_type=ChannelType.category,
        overwrites={
            RoleCollection.BOT: PermissionOverwriteDescription(view_channel=True),
            RoleCollection.DEV: PermissionOverwriteDescription(view_channel=True),
            RoleCollection.MASTER: PermissionOverwriteDescription(view_channel=True),
            RoleCollection.DEFAULT: PermissionOverwriteDescription(view_channel=False),
        },
    )


CategoryChannelCollection = CategoryChannelCollectionClass(path="configuration/game_manager/category_channels")


class ChannelCollectionClass(AbstractChannelCollection):
    _base_class = ChannelDescription
    _category_collection = CategoryChannelCollection
    _role_collection = RoleCollection

    WELCOME = ChannelDescription(
        name="Welcome",
        topic="Welcome!",
        channel_type=ChannelType.text,
    )
    # Dev category
    TEST = ChannelDescription(
        name="test",
        topic="Test channel for developers",
        channel_type=ChannelType.text,
        sync_permissions=True,
        category=CategoryChannelCollection.DEV,
    )
    EVENTS = ChannelDescription(
        name="commands-dev",
        topic="Commands for devs",
        channel_type=ChannelType.text,
        sync_permissions=True,
        category=CategoryChannelCollection.DEV,
    )
    LOG = ChannelDescription(
        name="logs",
        topic="Log channel",
        channel_type=ChannelType.text,
        sync_permissions=True,
        overwrites={
            RoleCollection.DEV: PermissionOverwriteDescription(view_channel=True),
            RoleCollection.BOT: PermissionOverwriteDescription(view_channel=True),
            RoleCollection.MASTER: PermissionOverwriteDescription(view_channel=True, send_messages=False),
            RoleCollection.DEFAULT: PermissionOverwriteDescription(view_channel=False),
        },
        category=CategoryChannelCollection.DEV,
    )
    TEST_VOICE = ChannelDescription(
        name="test_voice",
        channel_type=ChannelType.voice,
        sync_permissions=True,
        category=CategoryChannelCollection.DEV,
    )

    # Game master category
    MASTER = ChannelDescription(
        name="game-masters",
        topic="Channel for game masters",
        channel_type=ChannelType.text,
        sync_permissions=True,
        category=CategoryChannelCollection.MASTER,
    )
    COMMANDS = ChannelDescription(
        name="commands",
        topic="Commands for game masters",
        channel_type=ChannelType.text,
        sync_permissions=True,
        category=CategoryChannelCollection.MASTER,
    )
    BOARD = ChannelDescription(
        name="board",
        topic="Control panel and game board",
        channel_type=ChannelType.text,
        overwrites={
            RoleCollection.DEV: PermissionOverwriteDescription(view_channel=True),
            RoleCollection.MASTER: PermissionOverwriteDescription(view_channel=True, send_messages=False),
            RoleCollection.DEFAULT: PermissionOverwriteDescription(view_channel=False),
        },
        category=CategoryChannelCollection.MASTER,
    )
    MEMO = ChannelDescription(
        name="memo",
        channel_type=ChannelType.text,
        topic="Memo channel",
        sync_permissions=True,
        category=CategoryChannelCollection.MASTER,
    )
    MUSIC = ChannelDescription(
        name="music",
        topic="Control of the music",
        channel_type=ChannelType.text,
        sync_permissions=True,
        category=CategoryChannelCollection.MASTER,
    )
    MASTER_VOICE = ChannelDescription(
        name="Game masters",
        channel_type=ChannelType.voice,
        topic="Game masters voice channel",
        sync_permissions=True,
        category=CategoryChannelCollection.MASTER,
    )


ChannelCollection = ChannelCollectionClass(path="configuration/game_manager/channels")

if __name__ == '__main__':
    print(CategoryChannelCollection.to_json())
    print(ChannelCollection.to_json())
