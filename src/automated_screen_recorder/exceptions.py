"""Public exception hierarchy."""


class RecorderError(Exception):
    """Base recorder error."""


class InvalidConfigurationError(RecorderError):
    """Configuration cannot be used by the recorder."""


class InvalidStateTransitionError(RecorderError):
    """Lifecycle operation is invalid for the current state."""


class DisplayUnavailableError(RecorderError):
    """Selected display is unavailable."""


class OutputPathError(RecorderError):
    """Output path cannot be used safely."""


class RecordingError(RecorderError):
    """Recording operation failed."""


class SaveError(RecorderError):
    """Recording could not be persisted."""


class CancellationError(RecorderError):
    """Cancellation did not complete cleanly."""


class ExternalProcessError(RecorderError):
    """FFmpeg or another external helper failed."""
