import asyncio
import os
from collections import defaultdict
from enum import Enum
from typing import Dict

import discord
from discord import TextChannel, File, User

from default_collections import ChannelCollection, RoleCollection
from default_collections.game_collection import MinigameCollection
from functions.text_analysis import check_answer
from game_models.abstract_channel_mini_game import ChannelGameStatus, ChannelGameStatuses, TextChannelMiniGame
from bot_management.listener_utils import start_next_minigame
from helpers.json_helpers import TranslationDict
from logger import logger

"""
    Standard mode : battery or 1 candle + 1 fire
    Simple mode: 1 battery or 1 candle or 1 fire
"""


class Messages(TranslationDict):  # Minimal message dict, to be overridden in JSON translations
    INTRO = "Welcome, start with {start_emoji}."
    START_EMOJI = "🔦"
    MASTER = "To show standard images (MASTER): {emoji}; to show special image: {emoji_special}; All objects: {objects}"
    FILES_PATH = "files/attic/"
    WHAT_DO_YOU_SEE = "What do you see ?"
    CANDLE_TIP = "Light the candle !"
    FIRE_TIP = "Light something !"
    SPECIAL = "You found a bag. Light it to show what's inside."
    ALREADY_FOUND = "Already found"
    IN_TOTAL = "in total"
    PER_PERSON = "per person"
    LATE_USER_JOINED = "You joined too late: cannot use objects"
    NO_MORE_CANDLE = "No more candle. {todo_next}"
    NO_MORE_MATCHES = "No more matches. {todo_next}"
    NO_MORE_BATTERY = "No more battery. {todo_next}"
    CALL_MASTER = "Call MASTER if needed"
    OTHER_HAVE = "Other may have ?"
    OTHER_OBJECTS = "Other objects to light ?"
    EXTINCTION_BATTERY = "Flashlight with no more battery"
    EXTINCTION_CANDLE = "Candle completely consumed"
    MAP_FOUND = "Map found, to show it, use {map_channel_mention}"
    CHEST_FOUND = "Chest found, to show it use {chest_channel_mention}"
    VICTORY = "Nothing else interesting to look for"
    HELPED_VICTORY = "Ok, I help !"
    OBJECTS_TO_FIND = {"🔦": [("flashlight",), "This is the flashlight of the beginning"],
                       "🔋": [("battery",), "Batteries: {nb_batteries} {max_uses_type}! Use 🔋 to reload flashlight"],
                       "🔥": [("match",), "Matches: {nb_matches} {max_uses_type}! Use 🔥 to use them"],
                       "🕯️": [("candle",), "Candles: {nb_candles} {max_uses_type}! Use 🕯 to use them"],
                       "🗺️": [("map",), "A map ! Use 🗺 to see it"],
                       "🔒": [("chest", "trunk"), "A chest! Use 🔒 to examine it"],
                       "👜": [("bag", "satchel"), "A bag! Use 👜 to see what's inside (light also required)"],
                       }


MESSAGES = Messages(path="configuration/minigames/attic_game")


class AbstractActions:
    @classmethod
    def to_dict(cls):
        return {attr: value for attr, value in vars(cls).items() if not attr.startswith("_")}


class GameActions(AbstractActions):
    handbag = "👜"
    map = "🗺️"
    chest = "🔒"


class LightActions(AbstractActions):
    flashlight = "🔦"
    battery = "🔋"
    candle = "🕯️"
    fire = "🔥"


class LightType(Enum):
    flashlight = "nb_batteries"
    candle = "nb_candles"
    fire = "nb_matches"  # level SIMPLE only


class MaxUsesType(Enum):
    GLOBAL = 0  # mas uses are defined globally
    INDIVIDUAL_EXACT = 1  # mas uses is defined per person
    INDIVIDUAL_PROPORTIONAL = 2  # max uses is distributed proportionally per person (WARN: special euclidean division!)


class AtticGameChannelStatus(ChannelGameStatus):
    def __init__(self, channel):
        super().__init__(channel)
        self.members = defaultdict(int)
        self.objects_found = {}
        self.light_actions = {}  # actions to show an attic image
        self.actions_done = {}  # actions to progress in game
        self.files_sent = 0  # index of the next image to send
        self.files_special_sent = 0  # index of the next special image to send
        self.current_light = LightType.flashlight
        self.special = False

    def clear(self):
        super().clear()
        self.members.clear()
        master_role = self._data.get("master_role", RoleCollection.MASTER.value)
        self.members.update({member: 0 for member in self._channel.members if
                             not member.bot and not master_role.has_the_role(member)})
        self.objects_found.clear()
        self.objects_found.update({key: False for key in self.data.get("objects", [])})
        self.objects_found[LightActions.flashlight] = True  # the only object found at the beginning
        self.light_actions.clear()
        self.light_actions.update({emoji: self.members.copy() for emoji in LightActions.to_dict().values()})
        self.actions_done.clear()
        self.actions_done.update({emoji: False for emoji in GameActions.to_dict().values()})
        self.files_sent = 0
        self.files_special_sent = 0
        self.current_light = LightType.flashlight
        self.special = False


class AtticGame(TextChannelMiniGame):
    _default_messages = MESSAGES

    def __init__(self, **kwargs):
        self._image_remaining_duration = kwargs.pop("image_remaining_duration", 10)
        self._interval_between_messages = kwargs.pop("interval_between_messages", 15)
        self._max_use_flashlight = kwargs.pop("max_use_flashlight", 4)
        self._max_use_candle = kwargs.pop("max_use_candle", 3)
        self._max_use_matches = kwargs.pop("max_use_matches", 3)
        self._master_role_description = RoleCollection.get(kwargs.pop("master_role_description", "MASTER"))
        self._map_channel_description = ChannelCollection.get(kwargs.pop("map_channel_description", "MAP_ROOM1"))
        self._map_channel_minigame_d = MinigameCollection.get(kwargs.pop("map_channel_minigame", "MAP"))
        self._map_channel_minigame_simple_d = MinigameCollection.get(kwargs.pop("map_channel_minigame_simple", "MAP2"))
        self._chest_channel_description = ChannelCollection.get(kwargs.pop("chest_channel_description", "CHEST_ROOM1"))
        self._chest_channel_minigame_d = MinigameCollection.get(kwargs.pop("chest_channel_minigame", "CHEST"))
        self._max_uses_type = MaxUsesType[kwargs.pop("max_uses_type", "GLOBAL")]
        super().__init__(**kwargs)
        self._channels = ChannelGameStatuses(AtticGameChannelStatus)

    async def _init_channel(self, channel) -> bool:
        if not isinstance(channel, TextChannel):
            logger.warning(f"Channel {channel} is not a text channel")
            return False
        self._channels[channel].set_data(objects=self._messages["OBJECTS_TO_FIND"])
        if not (set(LightActions.to_dict().values()) | set(GameActions.to_dict().values())
                <= set(self._channels[channel].data["objects"])):
            logger.error(f"Bad keys for data! data must contains at least all LightActions and GameActions emojis"
                         f" as keys. Data keys are: {set(self._channels[channel].data['objects'])}")
            return False
        if not await super()._init_channel(channel):
            return False
        formatted_objects = "\n" + "\n".join([f"{key}: {value[0]}"
                                              for key, value in self._messages["OBJECTS_TO_FIND"].items()])
        await self._master_channel_description.object_reference.send(
            self._messages["MASTER"].format(emoji=LightActions.flashlight, emoji_special=LightActions.candle,
                                            objects=formatted_objects))
        await channel.edit(slowmode_delay=self._interval_between_messages)
        await channel.send(self._messages["INTRO"].format(start_emoji=self._messages["START_EMOJI"]))
        return True

    async def _on_channel_helped_victory(self, channel):
        await channel.send(self._messages["HELPED_VICTORY"])
        await self.on_map_found(channel)
        await self.on_chest_found(channel)
        return await self._on_channel_victory(channel)

    async def on_map_found(self, channel):
        # Auto-detection of the next channel, in the same category
        if self._simple_mode:
            map_channel = await start_next_minigame(channel, self._map_channel_description,
                                                    self._map_channel_minigame_simple_d)
        else:
            map_channel = await start_next_minigame(channel, self._map_channel_description,
                                                    self._map_channel_minigame_d)
        if map_channel is None:
            return
        await map_channel.edit(sync_permissions=True)
        await channel.send(self._messages["MAP_FOUND"].format(map_channel_mention=map_channel.mention))

    async def on_chest_found(self, channel):
        # Auto-detection of the next channel, in the same category
        chest_channel = await start_next_minigame(channel, self._chest_channel_description,
                                                  self._chest_channel_minigame_d)
        if chest_channel is None:
            return
        await chest_channel.edit(sync_permissions=True)
        await channel.send(self._messages["CHEST_FOUND"].format(chest_channel_mention=chest_channel.mention))

    async def _on_channel_victory(self, channel):
        await channel.send(self._messages["VICTORY"])

    def _find_file(self, filename, special):
        filename = str(filename) + ".png"
        filename = "special" + filename if special else filename
        return os.path.join(self._messages["FILES_PATH"], filename)

    async def _send_next_image(self, channel):
        special = self._channels[channel].special
        self._channels[channel].special = False

        current_file = self._channels[channel].files_special_sent if special else self._channels[channel].files_sent
        path = self._find_file(current_file, special)
        if not os.path.isfile(path):
            path = self._find_file(0, special)  # at least file 0.png and special0.png must exist !
            current_file = 0
        if not os.path.isfile(path):
            err_msg = f"File not found error: {path}. Please ensure at least '0.png' and 'special.png' " \
                      f"exist in {self._messages['FILES_PATH']} directory!"
            logger.error(err_msg)
            await self._master_channel_description.object_reference.send(err_msg)
        msg = await channel.send(self._messages["WHAT_DO_YOU_SEE"], file=File(path))
        if special:
            self._channels[channel].files_special_sent = current_file + 1
            # if special, it means the map can be found, so the bag is at least virtually found.
            # This is important in the case a MASTER user choose to show the special image
            # and in the same time the bag has not been found yet.
            self._channels[channel].objects_found[GameActions.handbag] = True
        else:
            self._channels[channel].files_sent = current_file + 1
        await msg.delete(delay=self._image_remaining_duration)
        await asyncio.sleep(max(self._image_remaining_duration - 1, 0))
        if self._channels[channel].current_light == LightType.flashlight:
            await channel.send(self._messages["EXTINCTION_BATTERY"])
        else:  # light type is candle
            await channel.send(self._messages["EXTINCTION_CANDLE"])

    def _get_maximum_from_light_type(self, light_type: LightType):
        if light_type is LightType.candle:
            return self._max_use_candle
        if light_type is LightType.fire:
            return self._max_use_matches
        if light_type is LightType.flashlight:  # batteries
            return self._max_use_flashlight

    def _get_max_uses(self, light_type: LightType, nb_users):
        if self._max_uses_type is MaxUsesType.GLOBAL:
            return self._get_maximum_from_light_type(light_type)
        if self._max_uses_type is MaxUsesType.INDIVIDUAL_EXACT:
            return self._get_maximum_from_light_type(light_type)
        if self._max_uses_type is MaxUsesType.INDIVIDUAL_PROPORTIONAL:
            # Proportional, but round to the superior value (to avoid null/too small values).
            # E.g.: max=2, nb_users=3 -> max_pers_person=1
            # E.g.: max=5, nb_users=2 -> max_pers_person=3
            # Math assertion behind:  max/nb_users <= max_pers_person < (max/nb_users) + 1
            if not nb_users:
                return 1
            return (self._get_maximum_from_light_type(light_type) + nb_users - 1) // nb_users

    def _format_max_uses(self, channel):
        res = {light_type.value: self._get_max_uses(light_type, len(self._channels[channel].members))
               for light_type in LightType}
        max_uses_type = self._messages["IN_TOTAL"] if self._max_uses_type is MaxUsesType.GLOBAL \
            else self._messages["PER_PERSON"]
        res.update({"max_uses_type": max_uses_type})
        return res

    def _format_to_do_next(self, channel, light_type: LightType):
        todo_next = self._messages["OTHER_OBJECTS"] if self._max_uses_type is MaxUsesType.GLOBAL \
            else self._messages["OTHER_HAVE"]
        # todo: more precise message on what to do next (call master, ask someone else, use another object).
        return todo_next

    def _is_ge_than_max_uses(self, max_uses_dict: Dict[User, int], light_type: LightType, user: User):
        if self._max_uses_type is MaxUsesType.GLOBAL:
            current_uses = sum(v for v in max_uses_dict.values())
        elif self._max_uses_type is MaxUsesType.INDIVIDUAL_EXACT:
            current_uses = max_uses_dict[user]
        elif self._max_uses_type is MaxUsesType.INDIVIDUAL_PROPORTIONAL:
            current_uses = max_uses_dict[user]
        else:
            current_uses = 0
            logger.error(f"Invalid MaxUsesType: {self._max_uses_type}")
        nb_users = len(max_uses_dict) or 1
        return current_uses >= self._get_max_uses(light_type, nb_users)

    async def _analyze_message(self, message: discord.Message):
        if not self._active or not self._channels[message.channel].active:
            return

        if message.author.bot:
            return

        channel = message.channel

        # Help from master
        if self._master_role_description.has_the_role(message.author):
            if message.content == LightActions.flashlight:  # Flashlight for normal images
                await self._send_next_image(message.channel)
            elif message.content == LightActions.candle:  # Candle for special images
                self._channels[channel].special = True
                await self._send_next_image(message.channel)

        for key, has_been_found in self._channels[channel].objects_found.items():
            words_to_find, answer = self._channels[channel].data["objects"][key]
            if check_answer(message.content, words_to_find):
                if has_been_found:
                    if self._simple_mode:
                        await channel.send(self._messages["ALREADY_FOUND"])
                    continue
                if key == GameActions.map and not self._channels[channel].objects_found[GameActions.handbag]:
                    continue  # handbag must be found before the map

                await channel.send(answer.format(**self._format_max_uses(channel)))
                self._channels[channel].objects_found[key] = True

        if len(message.content) > 2:  # only emojis (length 1 or 2) are actions
            return

            # Check LightActions emojis
        for key, _count_light_actions in self._channels[channel].light_actions.items():
            if message.content != key:
                continue
            if not self._channels[channel].objects_found[key]:
                continue
            if not self._master_role_description.has_the_role(message.author) \
                    and message.author not in self._channels[channel].members:
                # user joined the channel too late ! The count of objects cannot be done
                # because members are initialized at channel game start.
                await channel.send(self._messages["LATE_USER_JOINED"].format(user_mention=message.author.display_name))
                return
            # Only one use of flashlight, at the beginning (after, only the battery emoji can make it light up again)
            if key == LightActions.flashlight and not sum(self._channels[channel].light_actions[key].values()):
                self._channels[channel].current_light = LightType.flashlight
                self._channels[channel].light_actions[key][message.author] += 1
                await self._send_next_image(channel)
                break

            # Candle + matches (fire) together / level STANDARD
            candle_uses = self._channels[channel].light_actions[LightActions.candle]
            fire_uses = self._channels[channel].light_actions[LightActions.fire]
            # Check that the number of use is under the limit
            if not self._simple_mode and key in (LightActions.candle, LightActions.fire):
                if (key == LightActions.candle
                        and self._is_ge_than_max_uses(fire_uses, LightType.candle, message.author)):
                    await channel.send(self._messages["NO_MORE_CANDLE"].format(
                        todo_next=self._format_to_do_next(channel, LightType.candle)))
                    break
                if (key == LightActions.fire
                        and self._is_ge_than_max_uses(candle_uses, LightType.fire, message.author)):
                    await channel.send(self._messages["NO_MORE_MATCHES"].format(
                        todo_next=self._format_to_do_next(channel, LightType.candle)))
                    break
                # Check that both candle and fire have been sent
                self._channels[channel].light_actions[key][message.author] += 1
                nb_candle_uses = sum(candle_uses.values())
                nb_fire_uses = sum(fire_uses.values())
                if ((key == LightActions.candle and nb_candle_uses < nb_fire_uses)
                        or (key == LightActions.fire and nb_candle_uses > nb_fire_uses)):
                    self._channels[channel].current_light = LightType.candle
                    await self._send_next_image(channel)
                else:
                    # register the action, but do nothing (wait for the second emoji)
                    if candle_uses and not fire_uses:  # first use of an emoji candle
                        await channel.send(self._messages["CANDLE_TIP"])
                    elif not candle_uses and fire_uses:  # first use of an emoji candle
                        await channel.send(self._messages["FIRE_TIP"])
                break

            # Candle / level SIMPLE
            if self._simple_mode and key == LightActions.candle:
                if self._is_ge_than_max_uses(candle_uses, LightType.candle, message.author):
                    await channel.send(self._messages["NO_MORE_CANDLE"].format(
                        todo_next=self._format_to_do_next(channel, LightType.candle)))
                    break
                self._channels[channel].light_actions[key][message.author] += 1
                self._channels[channel].current_light = LightType.candle
                await self._send_next_image(channel)

            # Fire / level SIMPLE
            if self._simple_mode and key == LightActions.fire:
                if self._is_ge_than_max_uses(fire_uses, LightType.fire, message.author):
                    await channel.send(self._messages["NO_MORE_MATCHES"].format(
                        todo_next=self._format_to_do_next(channel, LightType.fire)))
                    break
                self._channels[channel].light_actions[key][message.author] += 1
                self._channels[channel].current_light = LightType.fire
                await self._send_next_image(channel)

            # Battery (+ flashlight already present) / levels SIMPLE, STANDARD
            battery_uses = self._channels[channel].light_actions[LightActions.battery]
            if key == LightActions.battery:
                if self._is_ge_than_max_uses(battery_uses, LightType.flashlight, message.author):
                    await channel.send(self._messages["NO_MORE_BATTERY"].format(
                        todo_next=self._format_to_do_next(channel, LightType.flashlight)))
                    break
                self._channels[channel].light_actions[key][message.author] += 1
                self._channels[channel].current_light = LightType.flashlight
                await self._send_next_image(channel)

        # Check GameActions emojis
        for key, has_been_done in self._channels[channel].actions_done.items():
            if message.content != key:
                continue
            if has_been_done or not self._channels[channel].objects_found[key]:
                continue
            self._channels[channel].actions_done[key] = True
            if key == GameActions.handbag:
                self._channels[channel].special = True
                await channel.send(self._messages["SPECIAL"])
            elif key == GameActions.map:
                await self.on_map_found(message.channel)
            elif key == GameActions.chest:
                await self.on_chest_found(message.channel)

        # Check victory: chest and map found
        if (self._channels[channel].actions_done[GameActions.map]
                and self._channels[channel].actions_done[GameActions.chest]):
            await self.on_channel_victory(channel)
