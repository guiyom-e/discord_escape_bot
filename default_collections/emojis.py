class Emojis:
    """Easy way to get emojis"""
    key2 = "🗝️"
    thumbsup = "👍"
    tired_face = "😫"
    fork_and_knife = "🍴"
    anchor = "⚓"
    interrobang = "⁉"
    face_with_symbols_over_mouth = "🤬"
    name_badge = "📛"
    mag = "🔍"
    mag_right = "🔎"
    european_castle = "🏰"
    lock = "🔒"
    pen_ballpoint = "🖊"
    ok_hand = "👌"
    red_circle = "🔴"
    blue_circle = "🔵"
    white_circle = "⚪"
    sunflower = "🌻"


_emojis = [getattr(Emojis, key) for key in dir(Emojis) if not key.startswith("_")]
assert len(_emojis) == len(set(_emojis))  # ensure emojis are unique (and therefore can be used as keys)
