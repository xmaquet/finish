"""Liste simple des caméras. L'index OpenCV reste le choix technique."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import cv2

from config import CAMERA_INDEX, PREFER_DIRECTSHOW

_DIRECTSHOW_NAMES = r"""
$source = @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;

[ComImport, Guid("55272A00-42CB-11CE-8135-00AA004BB851"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
interface IPropertyBag {
    [PreserveSig]
    int Read([MarshalAs(UnmanagedType.LPWStr)] string name, out object value, IntPtr errorLog);
    [PreserveSig]
    int Write([MarshalAs(UnmanagedType.LPWStr)] string name, ref object value);
}

public static class FinishDShowNames {
    [ComImport, Guid("29840822-5B84-11D0-BD3B-00A0C911CE86"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface ICreateDevEnum {
        [PreserveSig]
        int CreateClassEnumerator([In] ref Guid type, out IEnumMoniker enumMoniker, [In] int flags);
    }

    [DllImport("ole32.dll")]
    static extern int CoCreateInstance(ref Guid clsid, IntPtr outer, uint context, ref Guid iid, [MarshalAs(UnmanagedType.IUnknown)] out object punk);

    public static string[] Names() {
        var category = new Guid("860BB310-5D01-11d0-BD3B-00A0C911CE86");
        var clsid = new Guid("62BE5D10-60EB-11d0-BD3B-00A0C911CE86");
        var iid = new Guid("29840822-5B84-11D0-BD3B-00A0C911CE86");
        object punk;
        int hr = CoCreateInstance(ref clsid, IntPtr.Zero, 1, ref iid, out punk);
        if (hr != 0) return new string[0];
        var dev = (ICreateDevEnum)punk;
        IEnumMoniker enumerator;
        hr = dev.CreateClassEnumerator(ref category, out enumerator, 0);
        var names = new List<string>();
        if (hr != 0 || enumerator == null) return names.ToArray();
        var monikers = new IMoniker[1];
        while (enumerator.Next(1, monikers, IntPtr.Zero) == 0) {
            Guid bagId = typeof(IPropertyBag).GUID;
            object bagObj = null;
            monikers[0].BindToStorage(null, null, ref bagId, out bagObj);
            var bag = (IPropertyBag)bagObj;
            object name;
            bag.Read("FriendlyName", out name, IntPtr.Zero);
            names.Add(Convert.ToString(name));
        }
        return names.ToArray();
    }
}
'@
Add-Type -TypeDefinition $source
[FinishDShowNames]::Names()
"""


@dataclass(frozen=True)
class CameraChoice:
    index: int
    label: str


def default_choices() -> list[CameraChoice]:
    return [CameraChoice(CAMERA_INDEX, f"Caméra {CAMERA_INDEX}")]


def assign_camera_labels(indexes: list[int], names: list[str]) -> list[CameraChoice]:
    """Associe les noms DirectShow aux index ouverts, dans le même ordre.

    La liste PnP contient aussi la caméra infrarouge, qui n'est pas une source
    de capture. On ne l'utilise pas : elle décalerait tous les noms.
    """
    choices = [CameraChoice(index, f"Caméra {index}") for index in indexes]
    if len(names) != len(choices) or not names:
        return choices
    return [
        CameraChoice(choice.index, f"Caméra {choice.index} — {name}")
        for choice, name in zip(choices, names, strict=True)
    ]


def detect_cameras(limit: int = 4) -> list[CameraChoice]:
    """Ouvre brièvement les premiers index. Les noms suivent l'ordre DirectShow."""
    names = _capture_device_names()
    found: list[int] = []
    api = cv2.CAP_DSHOW if sys.platform == "win32" and PREFER_DIRECTSHOW else cv2.CAP_ANY
    for index in range(max(1, limit)):
        capture = cv2.VideoCapture(index, api)
        opened = capture.isOpened()
        capture.release()
        if opened:
            found.append(index)
    return assign_camera_labels(found, names)


def _capture_device_names() -> list[str]:
    if sys.platform != "win32":
        return []
    script = Path(tempfile.gettempdir()) / "finish-dshow-names.ps1"
    try:
        script.write_text(_DIRECTSHOW_NAMES.strip() + "\n", encoding="utf-8-sig")
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if completed.returncode != 0:
        return []
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]
