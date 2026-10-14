"""Public exception hierarchy."""


class RecorderError(Exception):
    """Base recorder error."""


class InvalidConfigurationError(RecorderError):
    """Configuration is invalid."""


class InvalidStateTransitionError(RecorderError):
    """State transition is invalid."""


class CaptureInitializationError(RecorderError):
    """Capture initialization failed."""


class EncoderInitializationError(RecorderError):
    """Encoder initialization failed."""


class DisplayUnavailableError(RecorderError):
    """Display is unavailable."""


class OutputPathError(RecorderError):
    """Output path is unusable."""


class RecordingError(RecorderError):
    """Recording failed."""


class SaveError(RecorderError):
    """Recording save failed."""


class CancellationError(RecorderError):
    """Cancellation failed."""


class ExternalProcessError(RecorderError):
    """External process failed."""
