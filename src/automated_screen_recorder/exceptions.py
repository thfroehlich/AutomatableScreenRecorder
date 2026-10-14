"""Public exception hierarchy."""


class RecorderError(Exception): """Base recorder error."""


class InvalidConfigurationError(RecorderError): """Configuration is invalid."""


class InvalidStateTransitionError(RecorderError): """State transition is invalid."""


class CaptureInitializationError(RecorderError): """Capture could not start."""


class EncoderInitializationError(RecorderError): """Encoder could not start."""


class DisplayUnavailableError(RecorderError): """Display is unavailable."""


class OutputPathError(RecorderError): """Output path is unusable."""


class RecordingError(RecorderError): """Recording failed."""


class SaveError(RecorderError): """Recording could not be saved."""


class CancellationError(RecorderError): """Recording could not be cancelled."""


class ExternalProcessError(RecorderError): """External process failed."""
