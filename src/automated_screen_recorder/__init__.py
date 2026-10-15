"""Stable public package surface."""

from automated_screen_recorder.exceptions import (
    CancellationError,
    DisplayUnavailableError,
    ExternalProcessError,
    InvalidConfigurationError,
    InvalidStateTransitionError,
    OutputPathError,
    RecorderError,
    RecordingError,
    SaveError,
)
from automated_screen_recorder.models import (
    DisplayInfo,
    OutputFormat,
    RecordingConfig,
    RecordingMode,
    RecordingResult,
    RecordingState,
    RecordingStatus,
    VideoCodec,
)
from automated_screen_recorder.service import ScreenRecorder

__all__ = [
    "CancellationError",
    "DisplayInfo",
    "DisplayUnavailableError",
    "ExternalProcessError",
    "InvalidConfigurationError",
    "InvalidStateTransitionError",
    "OutputFormat",
    "OutputPathError",
    "RecorderError",
    "RecordingConfig",
    "RecordingError",
    "RecordingMode",
    "RecordingResult",
    "RecordingState",
    "RecordingStatus",
    "SaveError",
    "ScreenRecorder",
    "VideoCodec",
]
__version__ = "0.4.5"
