from enum import Enum
from typing import Optional

import unidecode


# TODO: use precise text detection
class TextAnswer(Enum):
    EXACT = 0
    CORRECT = 1
    INCORRECT = 2
    FORBIDDEN = 3
    ALMOST_CASE = 4
    ALMOST_NOT_ENOUGH = 5
    CONTAINS = 6


class TextAnalysisOptions(Enum):
    CASE_SENSITIVE = 0
    STRICT_EQUAL = 1  # strict equal (including accent)
    AND = 2  # default is OR
    STRICT_ACCENTS = 3  # "Accent sensitive". If STRICT_EQUAL in options, the check is always "accent sensitive".


# By default, the check is case insensitive, "accent insensitive"
# and one answer in possible_answers is sufficient to return True.
def check_answer(message_content, possible_answers, forbidden_answers=None, options=None) -> bool:
    if check_answer_and_return_it(message_content, possible_answers, forbidden_answers, options) is None:
        return False
    return True


def check_answer_and_return_it(message_content, possible_answers,
                               forbidden_answers=None, options=None) -> Optional[str]:
    if isinstance(possible_answers, str):
        possible_answers = [possible_answers]
    result = None
    if options is None:
        options = []
    if TextAnalysisOptions.STRICT_ACCENTS not in options and TextAnalysisOptions.STRICT_EQUAL not in options:
        message_content = unidecode.unidecode(message_content)
    if forbidden_answers:
        forbidden = check_answer(message_content, forbidden_answers)  # default options
        if forbidden:  # forbidden word found!
            return None
    for possible_answer in possible_answers:
        if TextAnalysisOptions.CASE_SENSITIVE not in options:
            possible_answer = possible_answer.lower()
            message_content = message_content.lower()
        if TextAnalysisOptions.STRICT_EQUAL in options:
            if possible_answer == message_content:
                result = possible_answer
            elif TextAnalysisOptions.AND in options:
                return None
        else:
            if TextAnalysisOptions.STRICT_ACCENTS not in options:
                possible_answer = unidecode.unidecode(possible_answer)
            if possible_answer in message_content:
                result = possible_answer
            elif TextAnalysisOptions.AND in options:
                return None
    return result
