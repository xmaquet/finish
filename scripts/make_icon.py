"""Fabrique une icône Windows à partir de finish.png, sans modifier le logo source."""

from __future__ import annotations

import struct
import sys
from pathlib import Path


def png_to_ico(png_path: Path, ico_path: Path) -> None:
    data = png_path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit(f"Pas un PNG : {png_path}")
    width, height = struct.unpack(">II", data[16:24])
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack(
        "<BBBBHHII",
        width if width < 256 else 0,
        height if height < 256 else 0,
        0,
        0,
        1,
        32,
        len(data),
        22,
    )
    ico_path.parent.mkdir(parents=True, exist_ok=True)
    ico_path.write_bytes(header + entry + data)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    png_to_ico(root / "finish.png", root / "build" / "finish.ico")
