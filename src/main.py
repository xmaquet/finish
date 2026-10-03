"""Point d'entrée de Finish."""

import logging
import sys
from pathlib import Path


def _ensure_src_on_path() -> None:
    src_dir = Path(__file__).resolve().parent
    src_str = str(src_dir)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)


_ensure_src_on_path()

from logging_setup import setup_logging  # noqa: E402
from version import VERSION  # noqa: E402


def main() -> int:
    setup_logging()
    logger = logging.getLogger("finish")
    try:
        from PySide6.QtWidgets import QApplication

        from ui.main_window import MainWindow

        from ui.branding import logo_icon

        application = QApplication(sys.argv)
        application.setApplicationName("Finish")
        application.setApplicationVersion(VERSION)
        application.setWindowIcon(logo_icon())
        window = MainWindow()
        window.show()
        return application.exec()
    finally:
        logger.info("Application stopped")


if __name__ == "__main__":
    sys.exit(main())
