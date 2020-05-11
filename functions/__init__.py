"""
Functional package, independent from Discord.
"""

from functions.commands_analysis import is_key_in_args, get_number_in_args
from functions.text_analysis import check_answer, check_answer_and_return_it

__all__ = [
    'is_key_in_args',
    'get_number_in_args',

    'check_answer',
    'check_answer_and_return_it',
]
