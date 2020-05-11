from game_models.listener_collection import ListenerCollection


class MinigamesCollectionClass(ListenerCollection):
    """Collection of minigames"""
    # JEUX INTRODUCTIFS
    # INTRO = ListenerDescription(
    #     order=0,
    #     game_type="INTRO",
    #     name="Introduction du jeu",
    #     description="Jeu n°0 pour introduire l'escape game dans la chaîne #bienvenue, "
    #                 "donner le rôle Visiteur et répartir les équipes.\n"
    #                 "*Mode simple:* les équipes sont faites par les maîtres du jeu qui doivent changer "
    #                 "les rôles manuellement.\n"
    #                 "**À démarrer manuellement.**",
    #     auto_start=False,
    #     simple_mode=False,
    # )


MinigameCollection = MinigamesCollectionClass(path="configuration/game_manager/minigames")
