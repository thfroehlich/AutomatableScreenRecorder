"""Thread-safe state machine."""
from threading import RLock

from automated_screen_recorder.exceptions import InvalidStateTransitionError
from automated_screen_recorder.models import RecordingState

_ALLOWED = {RecordingState.IDLE: {RecordingState.RECORDING},
            RecordingState.RECORDING: {RecordingState.PAUSED, RecordingState.STOPPED, RecordingState.CANCELLED,
                                       RecordingState.FAILED},
            RecordingState.PAUSED: {RecordingState.RECORDING, RecordingState.STOPPED, RecordingState.CANCELLED,
                                    RecordingState.FAILED},
            RecordingState.STOPPED: {RecordingState.SAVED, RecordingState.CANCELLED, RecordingState.FAILED},
            RecordingState.SAVED: {RecordingState.IDLE}, RecordingState.CANCELLED: {RecordingState.IDLE},
            RecordingState.FAILED: {RecordingState.IDLE}}


class RecordingStateMachine:
    """Serialize and validate lifecycle changes."""

    def __init__(self) -> None: self._state = RecordingState.IDLE; self._lock = RLock()

    @property
    def state(self) -> RecordingState:
        with self._lock: return self._state

    def transition(self, target: RecordingState) -> None:
        with self._lock:
            if target not in _ALLOWED[self._state]:
                raise InvalidStateTransitionError(f"Cannot transition from {self._state.value} to {target.value}.")
            self._state = target

    def reset(self) -> None: self.transition(RecordingState.IDLE)
