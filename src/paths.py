"""Emplacements des fichiers de Finish.

En développement, les vidéos restent dans le dossier du projet, là où sont
déjà les archives. Une fois empaqueté, les vidéos vont dans Documents, et
les préférences comme les journaux dans le profil local. Rien d'utile n'est
écrit à côté de Finish.exe : ce dossier peut être en lecture seule.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from config import PROJECT_ROOT


def is_packaged() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    if is_packaged():
        return Path(getattr(sys, "_MEIPASS"))
    return PROJECT_ROOT


def backdrop_path() -> Path:
    bundled = resource_root() / "arrivee.png"
    if bundled.is_file():
        return bundled
    return PROJECT_ROOT / "arrivee.png"


def logo_path() -> Path:
    bundled = resource_root() / "finish.png"
    if bundled.is_file():
        return bundled
    return PROJECT_ROOT / "finish.png"


def user_data_dir() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / "Finish"
    return Path.home() / "Finish"


def preferences_path() -> Path:
    return user_data_dir() / "preferences.json"


def logs_dir() -> Path:
    return user_data_dir() / "logs"


def log_file() -> Path:
    return logs_dir() / "finish.log"


def default_recordings_dir() -> Path:
    if is_packaged():
        return Path.home() / "Documents" / "Finish" / "recordings"
    return PROJECT_ROOT / "recordings"


def ensure_runtime_directories() -> None:
    user_data_dir().mkdir(parents=True, exist_ok=True)
    logs_dir().mkdir(parents=True, exist_ok=True)
    default_recordings_dir().mkdir(parents=True, exist_ok=True)
