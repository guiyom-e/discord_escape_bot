from models.guilds import GuildDescription, AbstractGuildCollection


class GuildCollectionClass(AbstractGuildCollection):
    STANDARD = GuildDescription(
        name="The Guild",
        icon=None
    )


GuildCollection = GuildCollectionClass(path="configuration/game_manager/guilds")
