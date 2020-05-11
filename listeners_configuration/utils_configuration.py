from typing import List

from constants import VERBOSE
from models import AbstractGuildListener
from utils_listeners import *

UTILS = [
    # MODULES POUR LES MAÎTRES DU JEU ET DÉVELOPPEURS
    # Outils de debug et outils avancés de maître du jeu
    DebugFunctions(name="Outils d'administration",
                   description="Commandes commençant par `>` pour le debogage, obtenir des informations, "
                               "réinitialiser le jeu, etc.\n`>help` pour connaître les commandes.",
                   prefix=">",
                   auto_start=True,
                   verbose=VERBOSE,
                   allowed_roles=["DEV"],
                   log_webhook_description="LOG",
                   events_channel_description="EVENTS",
                   ),

    # Outils de gestion du jeu
    GameUtils(name="Outils de jeu",
              description="Commandes commençant par `!` pour une administration rapide et efficace du jeu, "
                          "pour parler à la place du bot, etc.\n`!help` pour connaître les commandes.",
              prefix="!",
              auto_start=True,
              verbose=VERBOSE,
              allowed_roles=["MASTER", "DEV"]),

    # Outils de musique
    MusicTools(name="Outil musique de base",
               description="Commandes commençant par `&` pour lire de la musique locale ou venant de YoutTube."
                           "\n`&help` pour connaître les commandes.",
               prefix="&",
               auto_start=True,
               verbose=VERBOSE,
               allowed_roles=["MASTER", "DEV"]),

    # Role manager avec réactions par émoticônes. Démarre automatiquement par défaut: ne pas le désactiver!
    RoleByReactionManager(description="Système d'auto-attribution des rôles par réaction. Ne pas désactiver !",
                          auto_start=True, show_in_listener_manager=False),

    # Jingle palette
    JinglePaletteManager(description="Jingle palette", auto_start=True, show_in_listener_manager=False)
]


class UtilsList:
    _listeners_list: List[AbstractGuildListener] = UTILS

    def __init__(self, guild):
        self._listeners = [ele.set(guild) for ele in self._listeners_list]

    def __iter__(self):
        for listener in self._listeners:
            yield listener
