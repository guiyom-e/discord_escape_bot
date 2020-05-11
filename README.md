Escape bot is a project of virtual escape game through a Discord bot.
It can use external resources that are not in this repo.

# Installation

- Install Python 3.6+
- On Linux, you may install the following packages (with `apt`) to allow voice support:
  - `libffi-dev` (or `libffi-devel` on some systems)
  - `python-dev`
- Install requirements (`cd discord_bot_python && pip install -r requirements.txt`).
- Copy `.env.default` to `.env` and complete it with your server token, guild id and name.

# How to contribute to the project ?

See [CONTRIBUTING](CONTRIBUTING.md)

# Game structure and configuration

See [ESCAPE.md](ESCAPE.md)

# Game master recommendations

See [Recommandations](recommandations_maitre_du_jeu.md) (french)

# Games available

See [Games](configuration/GAMES.md)

# Discord bot

## Start the bot

````bash
python bot.py
````

## Exit codes

- 0: No issue
- 1: Environment variables could not be loaded
- 2: The maximum number of guilds is less than 1
- 3: Support for multiple guilds is not available yet

## Structure

```
|- bot_management/        -> classes aimed to manage listeners
|- configuration/         -> server configuration and bot messages
|  |- subfolder/          -> folder of translations
|- files/                 -> static files that can be used by the bot
|- flask_server/          -> minimalist flask server, independant from the rest of the project
|  |- static/
|  |- templates/
|  |- app.py              -> main file to start the server
|- functions/             -> functions used in the game play, using the configuration
|- game_configuration/    -> configuration of minig-games and utils to run
|- game_models/           -> model classes describing mini-games (listeners) and game managers
|- helpers/               -> functions independant of the game
|- minigames/             -> independant mini-game listeners to events, using the configuration
|- models/                -> model classes describing Discord objects
|- utils_listeners        -> independant uilitary listeners
|- .env.default           -> .env template
|- .gitignore
|- bot.py                 -> main file to run to start the bot
|- constants.py           -> constants necessary to run the bot. Loads some environment variables.
|- logger.py              -> project logger
|- Procfile               -> used for deployment
|- README.md
|- requirements.txt
```

# Website

This website is a showcase site that is not aimed to be developed. Otherwise, another project should be created.

## Start the server

````bash
gunicorn flask_server.app:app
````

# Deployment
Heroku is used to deploy the app.

