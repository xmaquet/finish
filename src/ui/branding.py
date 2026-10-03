"""Logo FINISH. Le fichier source finish.png n'est pas modifié."""

from __future__ import annotations

import logging

from PySide6.QtGui import QIcon, QPixmap

from paths import logo_path

logger = logging.getLogger("finish.ui")

_pixmap: QPixmap | None = None
_loaded = False


def logo_pixmap() -> QPixmap | None:
    global _loaded, _pixmap
    if _loaded:
        return _pixmap
    _loaded = True
    path = logo_path()
    if not path.is_file():
        logger.warning("Logo file missing path=%s", path)
        return None
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        logger.warning("Logo file unreadable path=%s", path)
        return None
    _pixmap = pixmap
    return _pixmap


def logo_icon() -> QIcon:
    pixmap = logo_pixmap()
    if pixmap is None:
        return QIcon()
    return QIcon(pixmap)
