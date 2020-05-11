from collections import defaultdict
from enum import Enum
from typing import Optional, Union

from discord import Webhook, TextChannel, RequestsWebhookAdapter, Guild, ClientUser, Member, User
from discord.abc import GuildChannel

from constants import BOT
from logger import logger
from models.abstract_models import SpecifiedDictCollection, DiscordObjectDict
from models.guilds import GuildWrapper


class CharacterType(Enum):
    bot = 0
    webhook = 1


class CharacterDescription(DiscordObjectDict):
    """Describes a bot or a webhook.

    WARN: object_reference is not used in this description.
    """
    _updatable_keys = ["name", "avatar"]
    _export_keys = ["name", "avatar"]
    _is_async = False  # DO NOT CHANGE

    def __init__(self, character_type: Union[CharacterType, int, str] = CharacterType.webhook,
                 name="Bot", avatar: Optional[Union[str, bytes, bytearray]] = None, **kwargs):
        super().__init__(**kwargs)
        self.character_type: CharacterType = character_type if isinstance(character_type, CharacterType) \
            else CharacterType(character_type) if isinstance(character_type, int) \
            else CharacterType[str(character_type)]
        self.name: str = name
        if isinstance(avatar, (bytes, bytearray)) or avatar is None:
            self.avatar: Optional[bytearray] = avatar
        else:
            self.avatar: bytearray = bytearray.fromhex(str(avatar))
        self._object_reference = defaultdict(None)
        self._bot_avatar_hash = None

    @property
    def object_reference(self):
        return self._object_reference

    @object_reference.setter
    def object_reference(self, value):
        if value is None:
            self._object_reference.clear()
        else:
            logger.error(f"Object reference of {self} is a dictionary! Cannot set {value}")

    @property
    def webhook_name(self):
        return self.name

    def spread(self):
        return self.to_dict()

    @classmethod
    def from_dict(cls, dico):
        return cls(**dico)

    # Implement recommended methods in DiscordObjectDict doc
    async def update_object(self, obj: Union[Webhook, ClientUser], channel=None) -> bool:
        if channel:
            self.object_reference[channel] = obj
        if isinstance(obj, Webhook):
            await obj.edit(name=self.name, avatar=self.avatar)
        elif isinstance(obj, (ClientUser, Member, User)):
            if isinstance(obj, (User, Member)) and BOT.user == obj:
                obj = BOT.user
            else:
                logger.error(f"The user {obj} must be the bot itself!")
                return False
            if obj.name == self.name and obj.avatar == self._bot_avatar_hash:
                logger.info("Bot user already up-to-date!")
            else:
                await obj.edit(username=self.name, avatar=self.avatar)
                self._bot_avatar_hash = obj.avatar
                logger.info("Bot user updated!")
        else:
            logger.error(f"Invalid character object {obj}")
            return False
        return True

    async def generate_object(self, channel: TextChannel) -> Optional[Webhook]:
        if not isinstance(channel, TextChannel):
            logger.error(f"Channel {channel} is not a TextChannel!")
            return None
        webhook = await channel.create_webhook(name=self.name, avatar=self.avatar)
        if not self._is_async:
            # necessary to get the correct adapter (not async)
            return Webhook.partial(webhook.id, webhook.token, adapter=RequestsWebhookAdapter())
        return webhook

    async def create_object(self, channel: TextChannel):
        self.object_reference[channel] = await self.generate_object(channel)
        return True

    async def _get_webhook_instance(self, channel: TextChannel) -> Optional[Webhook]:
        if not isinstance(channel, TextChannel):
            logger.error(f"Channel {channel} is not a TextChannel!")
            return None
        if channel in self.object_reference:
            webhook = self.object_reference[channel]
            if not self._is_async:
                # necessary to get the correct adapter (not async)
                return Webhook.partial(webhook.id, webhook.token, adapter=RequestsWebhookAdapter())
            return webhook
        webhooks = await channel.webhooks()
        matching_webhooks = [webhook for webhook in webhooks if webhook.name == self.name]
        if len(matching_webhooks) > 1:
            logger.warning(f"More than 1 webhook in channel {channel} with name {self.name}: {webhooks}. "
                           f"The first one will be used.")
        if not matching_webhooks:
            return await self.generate_object(channel)
        # else
        webhook = matching_webhooks[0]
        await self.update_object(webhook, channel)
        if not self._is_async:
            # necessary to get the correct adapter (not async)
            return Webhook.partial(webhook.id, webhook.token, adapter=RequestsWebhookAdapter())
        return webhook

    async def _get_bot_member_instance(self, guild: Union[GuildChannel, Guild]) -> Optional[ClientUser]:
        if isinstance(guild, GuildChannel):
            guild = guild.guild
        if not isinstance(guild, (Guild, GuildWrapper)):
            logger.error(f"Guild {guild} is not a Guild!")
            return None
        member: ClientUser = guild.me
        await self.update_object(member)
        return member

    async def get_instance(self, reference: Union[TextChannel, Guild]):
        if self.character_type is CharacterType.webhook:
            return await self._get_webhook_instance(reference)
        elif self.character_type is CharacterType.bot:
            return await self._get_bot_member_instance(reference)


class AbstracterCharacterCollection(SpecifiedDictCollection):
    _base_class = CharacterDescription
