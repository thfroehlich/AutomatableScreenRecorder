"""Windows display enumeration isolated from portable service code."""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from typing import Any

from automated_screen_recorder.exceptions import DisplayUnavailableError
from automated_screen_recorder.models import DisplayInfo


def enumerate_displays() -> list[DisplayInfo]:
    """Return active Windows displays."""
    if sys.platform != "win32":
        return [
            DisplayInfo(
                index=0,
                name="Synthetic primary display",
                left=0,
                top=0,
                width=1920,
                height=1080,
                primary=True,
            )
        ]

    user32 = ctypes.windll.user32
    displays: list[DisplayInfo] = []
    monitor_callback_type = ctypes.WINFUNCTYPE(
        ctypes.c_int,
        wintypes.HMONITOR,
        wintypes.HDC,
        ctypes.POINTER(wintypes.RECT),
        wintypes.LPARAM,
    )

    def callback(
        _monitor: wintypes.HMONITOR,
        _device_context: wintypes.HDC,
        rectangle_pointer: Any,
        _data: wintypes.LPARAM,
    ) -> int:
        rectangle = rectangle_pointer.contents
        index = len(displays)
        displays.append(
            DisplayInfo(
                index=index,
                name=f"Display {index}",
                left=rectangle.left,
                top=rectangle.top,
                width=rectangle.right - rectangle.left,
                height=rectangle.bottom - rectangle.top,
                primary=rectangle.left == 0 and rectangle.top == 0,
            )
        )
        return 1

    callback_function = monitor_callback_type(callback)
    if not user32.EnumDisplayMonitors(None, None, callback_function, 0):
        raise DisplayUnavailableError("Windows display enumeration failed.")
    if not displays:
        raise DisplayUnavailableError("No active display was found.")
    return displays
