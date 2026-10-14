"""Windows display enumeration isolated from portable code."""

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

    rect_pointer_type = ctypes.POINTER(wintypes.RECT)

    monitor_proc_type = ctypes.WINFUNCTYPE(
        ctypes.c_int,
        wintypes.HMONITOR,
        wintypes.HDC,
        rect_pointer_type,
        wintypes.LPARAM,
    )

    def callback(
        _monitor: wintypes.HMONITOR,
        _dc: wintypes.HDC,
        rect_ptr: Any,
        _data: wintypes.LPARAM,
    ) -> int:
        rect = ctypes.cast(
            rect_ptr,
            rect_pointer_type,
        ).contents

        index = len(displays)

        displays.append(
            DisplayInfo(
                index=index,
                name=f"Display {index}",
                left=rect.left,
                top=rect.top,
                width=rect.right - rect.left,
                height=rect.bottom - rect.top,
                primary=rect.left == 0 and rect.top == 0,
            )
        )
        return 1

    callback_function = monitor_proc_type(callback)

    if not user32.EnumDisplayMonitors(
        None,
        None,
        callback_function,
        0,
    ):
        raise DisplayUnavailableError("Windows display enumeration failed.")

    if not displays:
        raise DisplayUnavailableError("No active display was found.")

    return displays
