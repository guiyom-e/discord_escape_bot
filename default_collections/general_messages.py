from helpers.json_helpers import TranslationDict


class GeneralMessagesClass(TranslationDict):
    # Default values (overridden if a translation is loaded)
    WELCOME = "Bonjour et bienvenue au château de Moulinsart !\n" \
              "Pour commencer, rejoins une équipe en sélectionnant un des numéros ci-dessous !\n" \
              "Si tu as besoin d'aide, tu peux appeler mon majordome {master} dans {channel} !"

    WELCOME_FILE = "files/placeholder.png"

    DM_MESSAGE_WELCOME = "Bienvenue à Moulinsart {user} !"

    DM_MESSAGES_ERROR = "{user_mention} pourrais-tu changer tes paramètres pour que " \
                        "je puisse t'envoyer un message personnel ? " \
                        "Quand ça sera fait, envoie-moi un petit message personnel (à {bot_mention}) !\n" \
                        "Pour changer tes paramètres clique sur la petite roue en bas, puis, dans l'onglet " \
                        "`Confidentialité & Sécurité`, coche la case 'Autoriser les messages privés en provenance " \
                        "des membres du serveur' (voir l'image en-dessous)"

    DM_MESSAGES_ERROR_FILE = "files/param_privacy_discord.png"

    INVITE_MESSAGE = "Hey ! J'ai trouvé des places pour une visite gratuite du château de Moulinsart " \
                     "(oui le château de Tintin !) On peut pas le visiter en vrai à cause du confinement, " \
                     "mais on peut le voir via nos écrans ici : {link}"

    GOOD_ANSWERS = [
        "Correct !",
        "Ouiiii",
        "Exactement !",
        "Tout à fait !",
        '''Comme dirais Dupont: "Je dirais même plus, c'est exact !"''',
        "Oui, c'est ça !"
    ]

    BAD_ANSWERS = [
        "Incorrect !",
        "Nooooon",
        "Raté !",
        "Pas du tout !",
        '''Comme dirais Dupond: "Je dirais même plus, c'est inexact !"''',
        "Non, c'est pas ça !"
    ]

    ALREADY_SAID = [
        "Oui, tu l'as déjà dit !",
        "Merci, je sais !",
        "Effectivement, ça n'a pas changé...",
        "D'accord, et ?",
        "C'est pas nouveau !",
        "Oui, je suis déjà au courant 😉"
    ]


GeneralMessages = GeneralMessagesClass(path="configuration/general_messages")
