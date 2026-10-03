"""Espace libre du disque qui contient les enregistrements.

L'autonomie est une estimation. Elle reprend la consommation observée en
1080p, 30 fps, codec mp4v : environ 131 Mo par minute.
"""

from __future__ import annotations

import shutil
from pathlib import Path


def free_bytes(path: Path) -> int:
    probe = path if path.exists() else path.parent
    return int(shutil.disk_usage(probe).free)


def format_free_space(nbytes: int) -> str:
    amount = max(0, int(nbytes))
    gigabytes = amount / (1024**3)
    if gigabytes >= 10:
        return f"{round(gigabytes)} Go"
    if gigabytes >= 1:
        return f"{gigabytes:.1f} Go".replace(".", ",")
    megabytes = amount // (1024**2)
    return f"{megabytes} Mo"


def format_byte_size(nbytes: int) -> str:
    amount = max(0, int(nbytes))
    gigabytes = amount / (1024**3)
    if gigabytes >= 10:
        return f"{round(gigabytes)} Go"
    if gigabytes >= 1:
        return f"{gigabytes:.1f} Go".replace(".", ",")
    megabytes = amount / (1024**2)
    if megabytes >= 10:
        return f"{round(megabytes)} Mo"
    if megabytes >= 1:
        return f"{megabytes:.1f} Mo".replace(".", ",")
    return f"{amount // 1024} Ko"


# 131 Mio par minute, mesure de référence du jalon 4 en 1080p / 30 fps / mp4v.
OBSERVED_BYTES_PER_MINUTE = 131 * 1024 * 1024


def autonomy_minutes(free: int, bytes_per_minute: int = OBSERVED_BYTES_PER_MINUTE) -> int:
    if free <= 0 or bytes_per_minute <= 0:
        return 0
    return int(free) // int(bytes_per_minute)


def format_autonomy(free: int, bytes_per_minute: int = OBSERVED_BYTES_PER_MINUTE) -> str:
    minutes = autonomy_minutes(free, bytes_per_minute)
    hours, remainder = divmod(minutes, 60)
    if hours:
        return f"environ {hours} h {remainder:02d}"
    return f"environ {minutes} min"


def autonomy_message(free: int) -> str:
    return (
        f"Espace libre : {format_free_space(free)}\n"
        f"Autonomie estimée : {format_autonomy(free)}"
    )


def disk_space_message(nbytes: int, warning_below: int) -> tuple[str, bool]:
    low = nbytes < warning_below
    text = f"Espace disponible : {format_free_space(nbytes)}"
    if low:
        text += " — attention, espace faible"
    return text, low
