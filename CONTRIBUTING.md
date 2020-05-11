# Contributing

You can create an issue and a pull request to contribute.
It is recommended to first contact the maintainer.

## Development conventions
Every contribution should follow these guidelines in order to be accepted:

General:
- do not expose secrets such as ids or tokens. Use the .env file.
- language: English is the norm for coding, but French is recommended for the game play part

Python:
- respect PEP8 conventions
- use Python annotations if the type is not explicit, at least for important functions
- separate text linked to game play from code
- all the variables specific to the game should be in `configuration/`
