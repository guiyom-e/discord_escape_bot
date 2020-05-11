Explanations of the game structure and configuration.
# Game structure
## Roles
The roles must be defined in `configuration/game_manager/roles/`.
They are defined in a JSON file.

All default roles are defined in the following order (order counts in Discord!):

- `DEV`: role of developers.
  - Should have admin rights. Should be above `BOT` role.
- `BOT`: role of the main bot.
  - Must have admin rights.
- `SINGER` (optional): role of singer bots. Must have admin rights. 
  - Used in minigames:
    - `ask_words`
- `MASTER`: role of game masters.
  - Should have all permissions (except admin).
- `CHARACTER1` (optional): role for character n°1.
  - Should have team permissions.
  - By default, it is used in minigames:
    - `enigmas`
  - By default, can see the channels:
    - `ROOM1`
- `CHARACTER2` (optional): role for character n°2.
  - Should have team permissions.
  - By default, it is used in minigames:
    - `ask_words`
  - By default, can see the channels:
    - `ROOM2`
    - `ROOM2_VOICE`
- `CHARACTER3` (optional): role for character n°3.
  - Should have team permissions.
  - By default, it is used in minigames:
    - `offices_game`
  - By default, can see the channels:
    - `ROOM3`
- `CHARACTER4` (optional): role for character n°4.
  - Should have team permissions.
  - By default, it is used in minigames:
    - `offices_game`
  - By default, can see the channels:
    - `ROOM4_VOICE`
- `TEAM1` / `TEAM2` / `TEAM3` (optional): roles for different teams.
  - Should have team permissions.
  - By default, they are used in minigames:
    - `count_everyone`
    - `find_the_recipe`
    - `attic_game`
    - `map_game`
    - `chest_game`
  - By default, can see all the channels in categories `TEAM1` / `TEAM2` / `TEAM3`
- `VISITOR`: role of a player.
  - Should have the permissions:
    - `change nickname`
    - `view channels`
    - `read message history`
    - `connect`
  - By default, they are used in minigames:
    - `count_everyone`
    - `find_the_recipe`
    - `attic_game`
    - `map_game`
    - `chest_game`
  - By default, can see all the channels in categories `TEAM1` / `TEAM2` / `TEAM3`
- `DEFAULT`: correspond to the role `@everyone`
  - It is recommended to grant at least the the permission `use_voice_activation` for a better experience.
  - Must remain the last role in the enum!

Team permissions are the following by default:
- Recommended: `change_nickname`, `view_channel`, `send_messages`, `connect`, 
`speak`, `use_voice_activation`, `read_message_history`.
- Optional (by default): `create_instant_invite`, `attach_files`, `mention_everyone`, `add_reactions`.
- Optional (not by default): `embed_links`, `stream`.
- Not recommended: other permissions are not recommended as they grant too much rights.

Default roles are used in administration tools and default minigames. Therefore:
- It is possible to edit default roles (permissions changes are however not recommended).
- It is not recommended to delete default roles.
- It is possible to add new roles, that must be written after the `BOT` role in order to be controllable by the bot.

## Channels
The channels must be defined in `configuration/game_manager/category_channels` for categories 
and `configuration/game_manager/channels` for text and voice channels in a JSON file.

### Category channels
Default categories are the following:

- `WELCOME` (optional): first category that should contain visible channels
- `DEV`: category reserved for development (roles `DEV` and `BOT`)
- `MASTER`: category reserved for game masters (roles `MASTER` and `BOT`)
- `SPECIAL` (optional): category recommended for specific channels linked to character roles
- `TEAM1` / `TEAM2` / `TEAM3` (optional): categories for teams (roles `TEAM1` / `TEAM2` / `TEAM3`)

Default categories structure the game. Therefore:
- It is possible to edit default categories (permissions changes are however not recommended).
- It is possible to add new categories.

### Channels
Default channels are almost all used as default channel in a mini-game. Therefore:
- It is possible to edit default channels (permissions changes are however not recommended).
- It is not recommended to delete default channels, 
unless you remove the associated mini-game or change its default channel
- It is possible to add new channels.
- Some channels are used by administration tools and should not be removed:
  - `WELCOME`: (for everyone) default channel for invitation link
  - `LOG`: (for `DEV`) logs returned by the logger are sent to this channel through a webhook
  - `MEMO`: (for `MASTER`) default channel where tips or instructions are send to game master 
  while a mini-game is initialized or running
  - `COMMANDS`: (for `MASTER`) channel to send master commands.
  - `EVENTS`: (for `DEV` and `MASTER`) information are given by the administration tools and administration commands can be written.
  - `BOARD`: (for `MASTER`) board with all minigames that can be controlled with Discord reactions

## Bots and webhook
Bots and webhook have a name and an avatar that are defined in `configuration/game_manager/characters/` in a JSON file.
There should be only one character of type 'bot'.

## Emojis
Default emojis are defined in `configuration/emojis.py` in the enum `Emojis`. All emojis must be different.

## Versions
All versions (or translations)
are stored in a directory corresponding to a minigame and under the filename patter `[NAME_OF_THE_TRANSLATION].json`.

To develop a new minigame compatible with versions, the code to write is, 
assuming a translation is available in `configuration/my_minigame/`:
```python
from helpers import TranslationDict
from game_models import AbstractMiniGame

class Messages(TranslationDict):
    INTRO = "Default message with a string to format: {format_your_custom_text_here}"

MESSAGES = Messages(path="configuration/my_minigame")


class MyMiniGame(AbstractMiniGame):
    _default_messages = MESSAGES

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def access_a_translation_key(self, key, value_to_format):
        return self._messages[key].format(format_your_custom_text_here=value_to_format)

print(MyMiniGame().access_a_translation_key("INTRO", "Hello!"))
```
The class `Messages` is the default translation, used if no translation is found in `configuration/my_minigame/`.
The classes attributes names are the same as the JSON keys that should be present in the translation.
If no correct translation exists, the attributes values are used, 
if a correct translation is found, the translation is used.
Note that defining the `Messages` class is not mandatory, but recommended for an easier game development 
(separation of code and translation, easy way to know which keys to create when writing a translation, ...) 
and to avoid errors in the case a translation is not formatted correctly.


## Server configuration
The guild properties (name and avatar) are defined in `configuration/game_manager/guilds/` in a JSON file.
The key used by default is `STANDARD`. There is no built-in function to use other keys.

### External bots
A bot with the role `SINGER` is necessary for the game `AskWords` and is recommended 
to play ambiance songs during the game.

The bot [Octave](https://top.gg/bot/octave) is an example of a Discord bot that can play music

## Game configuration
In `game_configuration/game_manager/minigames/`, it is possible to configure the minigames in multiple ways:
- Choose to include or not a minigame
- Add a name and a description to help game masters link the minigames to the translations
- Choose the channels, roles and members that can interact with a minigame
- Configure whether a minigame should start automatically
- Configure custom minigame options

It is not possible to configure utils to avoid incorrect configurations.

### Default game play [SPOILER]
With the default roles, channels and permissions, the game play should be as follows:
1) `IntroductionGame` in `WELCOME` channel. The game master can speak to players in `SUPPORT_VOICE` channel. 
During the "game", players take the role `VISITOR` and then choose a team and get one of the `TEAM` roles.
*The game master should activate the first step of `IntroductionGame` with an emoji reminded in `COMMANDS` channel.*
2) By team, in each `TEAM` category channel, the same channels and games are present.
    1) `CountEveryone` in `PARK` channels. When game is over, the next game is started automatically.
    *The game master should activate this game for each channel in `BOARD` channel.*
    2) `FindTheRecipe` in `KITCHEN` channels. When game is over, the next game is started automatically.
    3) `AtticGame` in `ATTIC` channels. Two objects have two be found. Each object starts the two following minigames.
    4) `MapGame` in `MAP_ROOM` channels. Uses an external enigma.
    5) `ChestGame` in `CHEST_ROOM` channels. Needs the completion of `MapGame` to be completed.
    When game is over, a role menu appears: each team player must choose a `CHARACTER` role and will a specific enigma
3) Depending on the role chosen at the end of `ChestGame`, players can play one of these games:
    1) `EnigmasGame` in `ROOM1` for roles `CHARACTER1`.
    *The game master should activate this game for the channel in `BOARD` channel.*
    2) `AskWords` in `ROOM2` and `ROOM2_VOICE` for roles `CHARACTER2`.
    *The game master should activate this game for the channel in `BOARD` channel.*
    3) `OfficesGame` in `ROOM3` for role `CHARACTER3`. This game is a cooperation game with `CHARACTER4`.
    4) `OfficesGame` in `ROOM4_VOICE` for role `CHARACTER4`. This game is a cooperation game with `CHARACTER3`.
4) Each of the three minigames should deliver a clue to write in `MAIN_ROOM` where `EndGame` is running.
When every clue has been sent, the game should deliver a new clue to be sent in `MAIN_ROOM` again. 
Once this last clue has been sent, the permissions of `RESTRICTED_ROOM` are synced with `WELCOME` category,
so each `VISITOR` can connect and each player with a team can speak (everyone normally). 
The game master can use the singer bot to play a victory song. Then, it is possible to debrief the game there.


Game play scheme:
```    
WELCOME CATEGORY
IntroductionGame (WELCOME)
 |    TEAM CATEGORY                                                    
 └──> CountEveryone (PARK)                                       
       └──> FindTheRecipe (KITCHEN)                              
            └──> AtticGame (ATTIC)                               
                 └──> MapGame (MAP_ROOM) ---------               
                 └──> ChestGame (CHEST_ROOM)   <-˩ code               
                      |                                          
                      |    SPECIAL CATEGORY                         
                      └──> EnigmasGame (ROOM1/ROOM1_VOICE) -----│ emoji
                      └──> AskWordsGame (ROOM2/ROOM2_VOICE) ----│ emoji
                      └──> OfficesGame (ROOM3/ROOM4_VOICE) -----│ emoji
WELCOME CATEGORY                                                |
EndGame (MAIN_ROOM/RESTRICTED_ROOM)   <-------------------------˩
```