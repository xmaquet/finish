"""Lecture du code fourcc renvoyé par OpenCV."""


def fourcc_to_string(value: float) -> str:
    try:
        code = int(value)
    except (TypeError, ValueError, OverflowError):
        return "n/a"
    if code <= 0:
        return "n/a"
    characters = [chr((code >> (8 * index)) & 0xFF) for index in range(4)]
    text = "".join(characters)
    if not text.isprintable():
        return "n/a"
    return text
