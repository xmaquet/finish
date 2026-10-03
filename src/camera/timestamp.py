"""Heure locale affichée dans l'image, à la milliseconde."""

from datetime import datetime

from config import TIMESTAMP_FORMAT


def format_timestamp(moment: datetime) -> str:
    """Formate l'heure locale. Les microsecondes sont tronquées à trois chiffres."""
    milliseconds = moment.microsecond // 1000
    return moment.strftime(TIMESTAMP_FORMAT) + f".{milliseconds:03d}"
