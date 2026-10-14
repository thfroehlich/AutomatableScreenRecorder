"""Windows display enumeration isolated from portable code."""

import ctypes
import sys
from ctypes import wintypes

from automated_screen_recorder.exceptions import DisplayUnavailableError
from automated_screen_recorder.models import DisplayInfo


def enumerate_displays() -> list[DisplayInfo]:
    """Return active monitor rectangles in Windows virtual-screen coordinates."""
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
    monitor_proc = ctypes.WINFUNCTYPE(
        ctypes.c_int,
        wintypes.HMONITOR,
        wintypes.HDC,
        ctypes.POINTER(wintypes.RECT),
        wintypes.LPARAM)

    def callback(
            _monitor: object, _dc: object, rect_ptr: object, _data: object
    ) -> int:
        rect = rect_ptr.contents
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

    if not user32.EnumDisplayMonitors(0, 0, monitor_proc(callback), 0) or not displays:
        raise DisplayUnavailableError("No active display was found.")
    return displays
