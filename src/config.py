"""Constantes de Finish. Modifier ce fichier pour adapter le poste."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CAMERA_INDEX = 0
PREFER_DIRECTSHOW = True
CAPTURE_BUFFER_SIZE = 1

MAX_BUFFER_SECONDS = 30

REQUESTED_WIDTH = 1920
REQUESTED_HEIGHT = 1080
REQUESTED_FPS = 30

JPEG_QUALITY = 80

RECORDING_CODEC = "mp4v"
RECORDING_QUEUE_MAX_FRAMES = 30
RECORDING_STOP_TIMEOUT_SECONDS = 15.0

# Avertissement seulement. L'enregistrement n'est pas bloqué par ce seuil.
DISK_FREE_WARNING_BYTES = 10 * 1024**3

DEFAULT_COURSE_NAME = "Course"
MAX_COURSE_SLUG_LENGTH = 48

LOGO_PATH = PROJECT_ROOT / "finish.png"
RECORDINGS_DIR = PROJECT_ROOT / "recordings"
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "finish.log"

# Le cahier des charges cite %f (microsecondes). L'affichage suit l'exemple
# à trois chiffres : 03/10/2026 10:42:17.533. Voir docs/DECISIONS.md, D6.
TIMESTAMP_FORMAT = "%d/%m/%Y %H:%M:%S"

FPS_WINDOW_SECONDS = 1.0
FPS_LOG_INTERVAL_SECONDS = 30.0
DISPLAY_INTERVAL_MS = 33
CAMERA_STOP_TIMEOUT_SECONDS = 5.0


def ensure_directories() -> None:
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
