"""Journaux tournants. finish.log, puis .1 et .2. Les plus anciens sont écartés."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from paths import ensure_runtime_directories, log_file
from version import VERSION

LOG_MAX_BYTES = 1_048_576
LOG_BACKUP_COUNT = 2

_configured = False


def setup_logging() -> None:
    global _configured
    if _configured:
        return
    ensure_runtime_directories()
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    if sys.stderr is not None:
        stream = logging.StreamHandler()
        stream.setFormatter(formatter)
        root.addHandler(stream)
    rotating = RotatingFileHandler(
        log_file(),
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    rotating.setFormatter(formatter)
    root.addHandler(rotating)
    _configured = True
    logging.getLogger("finish").info("Application started version=%s", VERSION)
