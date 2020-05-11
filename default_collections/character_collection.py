from models import AbstracterCharacterCollection, CharacterDescription
from models.characters import CharacterType


class CharacterCollectionClass(AbstracterCharacterCollection):
    MAIN = CharacterDescription(character_type=CharacterType.bot, name="Main character", avatar=None)
    LOG = CharacterDescription(character_type=CharacterType.webhook, name="Log bot")
    CHARACTER1 = CharacterDescription(character_type=CharacterType.webhook, name="Character 1")
    CHARACTER2 = CharacterDescription(character_type=CharacterType.webhook, name="Character 2")
    CHARACTER3 = CharacterDescription(character_type=CharacterType.webhook, name="Character 3")


CharacterCollection = CharacterCollectionClass(path="configuration/game_manager/characters")

if __name__ == '__main__':
    print(CharacterCollection.to_json())
