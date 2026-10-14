"""Stable public package surface."""
from automated_screen_recorder.exceptions import (
    CancellationError, CaptureInitializationError,
    DisplayUnavailableError, EncoderInitializationError,
    ExternalProcessError, InvalidConfigurationError,
    InvalidStateTransitionError, OutputPathError, RecorderError,
    RecordingError, SaveError)
from automated_screen_recorder.models import (
    DisplayInfo, OutputFormat, RecordingConfig, RecordingResult,
    RecordingState, RecordingStatus, VideoCodec)
from automated_screen_recorder.service import ScreenRecorder

__all__ = ["DisplayInfo", "OutputFormat", "RecordingConfig", "RecordingResult", "RecordingState", "RecordingStatus",
           "ScreenRecorder", "VideoCodec"]
__version__ = "0.1.0"
