"""Liste simple des caméras. L'index OpenCV reste le choix technique."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass

import cv2

from config import CAMERA_INDEX, PREFER_DIRECTSHOW


@dataclass(frozen=True)
class CameraChoice:
    index: int
    label: str


def default_choices() -> list[CameraChoice]:
    return [CameraChoice(CAMERA_INDEX, f"Caméra {CAMERA_INDEX}")]


def detect_cameras(limit: int = 4) -> list[CameraChoice]:
    """Ouvre brièvement les premiers index. Les noms Windows sont indicatifs."""
    names = _friendly_names()
    found: list[CameraChoice] = []
    api = cv2.CAP_DSHOW if sys.platform == "win32" and PREFER_DIRECTSHOW else cv2.CAP_ANY
    for index in range(max(1, limit)):
        capture = cv2.VideoCapture(index, api)
        opened = capture.isOpened()
        capture.release()
        if not opened:
            continue
        found.append(CameraChoice(index, f"Caméra {index}"))
    if len(names) == len(found) and names:
        found = [
            CameraChoice(choice.index, f"Caméra {choice.index} — {name}")
            for choice, name in zip(found, names, strict=True)
        ]
    return found


def _friendly_names() -> list[str]:
    if sys.platform != "win32":
        return []
    command = (
        "Get-PnpDevice -Class Camera,Image -Status OK | "
        "Select-Object -ExpandProperty FriendlyName"
    )
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]
