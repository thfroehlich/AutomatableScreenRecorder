"""Thread-safe recording application service."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from automated_screen_recorder.backends import CaptureProcess, FfmpegBackend
from automated_screen_recorder.exceptions import (
    CancellationError,
    DisplayUnavailableError,
    InvalidStateTransitionError,
    RecordingError,
    SaveError,
)
from automated_screen_recorder.models import (
    DisplayInfo,
    RecordingConfig,
    RecordingResult,
    RecordingState,
    RecordingStatus,
)
from automated_screen_recorder.platform_windows import enumerate_displays
from automated_screen_recorder.state import RecordingStateMachine
from automated_screen_recorder.storage import RecordingStorage

LOGGER = logging.getLogger(__name__)


class ScreenRecorder:
    """Stable facade for manual and interval-based video-only recording."""

    def __init__(
        self,
        backend: CaptureProcess | None = None,
        storage: RecordingStorage | None = None,
    ) -> None:
        self._backend = backend or FfmpegBackend()
        self._storage = storage or RecordingStorage()
        self._machine = RecordingStateMachine()
        self._lock = threading.RLock()
        self._interval_stop = threading.Event()
        self._interval_thread: threading.Thread | None = None
        self._config: RecordingConfig | None = None
        self._session_id: str | None = None
        self._current_segment: Path | None = None
        self._pending_segments: list[Path] = []
        self._saved_outputs: list[Path] = []
        self._part_index = 0
        self._started: float | None = None
        self._started_at: str | None = None
        self._elapsed = 0.0
        self._next_interval_deadline: float | None = None
        self._error: str | None = None

    def __enter__(self) -> ScreenRecorder:
        return self

    def __exit__(self, *_args: object) -> None:
        if self._machine.state in {
            RecordingState.RECORDING,
            RecordingState.PAUSED,
            RecordingState.STOPPED,
        }:
            self.cancel_recording()

    def enumerate_displays(self) -> list[DisplayInfo]:
        """Return currently available displays."""
        return enumerate_displays()

    def start_recording(self, config: RecordingConfig) -> RecordingStatus:
        """Start a recording and optionally its interval-save worker."""
        with self._lock:
            if self._machine.state in {
                RecordingState.SAVED,
                RecordingState.CANCELLED,
                RecordingState.FAILED,
            }:
                self._machine.reset()
            if self._machine.state is not RecordingState.IDLE:
                raise InvalidStateTransitionError(
                    f"Cannot start from {self._machine.state.value}."
                )
            self._validate_all_destinations(config)
            displays = self.enumerate_displays()
            if config.display_index >= len(displays):
                raise DisplayUnavailableError("Selected display is unavailable.")
            self._session_id = str(uuid.uuid4())
            self._config = config
            self._started_at = datetime.now(UTC).isoformat()
            self._elapsed = 0.0
            self._saved_outputs = []
            self._pending_segments = []
            self._part_index = 0
            self._error = None
            self._interval_stop.clear()
            try:
                self._storage.create_session()
                self._start_new_segment(displays[config.display_index])
                self._machine.transition(RecordingState.RECORDING)
                self._schedule_next_interval()
                self._start_interval_worker()
            except Exception as error:
                self._set_failed(error)
                raise RecordingError("Recording could not be started.") from error
            LOGGER.info("Recording started", extra=self._context("start"))
            return self.get_status()

    def pause_recording(self) -> RecordingStatus:
        """Finalize the active segment and pause interval timing."""
        with self._lock:
            self._require_state(RecordingState.RECORDING)
            try:
                self._finalize_current_segment()
                self._next_interval_deadline = None
                self._machine.transition(RecordingState.PAUSED)
            except Exception as error:
                self._set_failed(error)
                raise RecordingError("Recording could not be paused.") from error
            LOGGER.info("Recording paused", extra=self._context("pause"))
            return self.get_status()

    def resume_recording(self) -> RecordingStatus:
        """Start a new segment and resume interval timing."""
        with self._lock:
            self._require_state(RecordingState.PAUSED)
            config = self._require_config()
            displays = self.enumerate_displays()
            if config.display_index >= len(displays):
                error = DisplayUnavailableError("Selected display is unavailable.")
                self._set_failed(error)
                raise error
            try:
                self._start_new_segment(displays[config.display_index])
                self._machine.transition(RecordingState.RECORDING)
                self._schedule_next_interval()
            except Exception as error:
                self._set_failed(error)
                raise RecordingError("Recording could not be resumed.") from error
            LOGGER.info("Recording resumed", extra=self._context("resume"))
            return self.get_status()

    def stop_recording(self) -> RecordingStatus:
        """Stop capture while retaining unsaved segments."""
        self._stop_interval_worker()
        with self._lock:
            if self._machine.state not in {
                RecordingState.RECORDING,
                RecordingState.PAUSED,
            }:
                self._machine.transition(RecordingState.STOPPED)
            try:
                if self._machine.state is RecordingState.RECORDING:
                    self._finalize_current_segment()
                self._next_interval_deadline = None
                self._machine.transition(RecordingState.STOPPED)
            except Exception as error:
                self._set_failed(error)
                raise RecordingError("Recording could not be stopped.") from error
            LOGGER.info("Recording stopped", extra=self._context("stop"))
            return self.get_status()

    def cancel_recording(self) -> RecordingStatus:
        """Terminate capture and delete only temporary, not already saved, files."""
        self._stop_interval_worker()
        with self._lock:
            if self._machine.state not in {
                RecordingState.RECORDING,
                RecordingState.PAUSED,
                RecordingState.STOPPED,
            }:
                self._machine.transition(RecordingState.CANCELLED)
            failures: list[Exception] = []
            try:
                self._backend.cancel(self._timeout())
            except Exception as error:
                failures.append(error)
            try:
                self._storage.cleanup()
            except Exception as error:
                failures.append(error)
            self._current_segment = None
            self._pending_segments = []
            self._started = None
            self._next_interval_deadline = None
            if failures:
                self._set_failed(failures[0], cleanup=False)
                raise CancellationError(
                    "Recording cancellation did not complete cleanly."
                ) from failures[0]
            self._machine.transition(RecordingState.CANCELLED)
            LOGGER.info("Recording cancelled", extra=self._context("cancel"))
            return self.get_status()

    def save_recording(self, output_path: Path | None = None) -> RecordingResult:
        """Save pending video and return all outputs created by the session."""
        with self._lock:
            self._require_state(RecordingState.STOPPED)
            config = self._require_config()
            destination = output_path or config.output_path
            if destination.suffix.lower() != f".{config.output_format.value}":
                raise SaveError("Output path suffix must match output format.")
            try:
                if config.save_interval_seconds is None:
                    saved = self._save_pending(destination)
                elif self._pending_segments:
                    saved = self._save_pending(
                        self._next_interval_destination(destination)
                    )
                elif self._saved_outputs:
                    saved = self._saved_outputs[-1]
                else:
                    raise SaveError("No finalized recording data is available.")
                self._storage.cleanup()
                self._machine.transition(RecordingState.SAVED)
            except Exception as error:
                self._set_failed(error, cleanup=False)
                raise SaveError("Recording could not be saved.") from error
            outputs = list(self._saved_outputs)
            total_size = sum(path.stat().st_size for path in outputs)
            result = RecordingResult(
                session_id=self._session_id or "",
                output_path=saved,
                output_paths=outputs,
                duration_seconds=self._elapsed,
                file_size_bytes=saved.stat().st_size,
                total_file_size_bytes=total_size,
                codec=config.codec,
            )
            LOGGER.info("Recording saved", extra=self._context("save"))
            return result

    def get_status(self) -> RecordingStatus:
        """Return a thread-safe status snapshot."""
        with self._lock:
            remaining = None
            if self._next_interval_deadline is not None:
                remaining = max(0.0, self._next_interval_deadline - time.monotonic())
            return RecordingStatus(
                session_id=self._session_id,
                state=self._machine.state,
                started_at=self._started_at,
                elapsed_seconds=self._elapsed + self._running_elapsed(),
                backend=type(self._backend).__name__,
                error=self._error,
                saved_output_paths=list(self._saved_outputs),
                next_interval_save_in_seconds=remaining,
            )

    def _interval_loop(self) -> None:
        while not self._interval_stop.is_set():
            with self._lock:
                deadline = self._next_interval_deadline
                active = self._machine.state is RecordingState.RECORDING
            if not active or deadline is None:
                self._interval_stop.wait(0.25)
                continue
            remaining = max(0.0, deadline - time.monotonic())
            if self._interval_stop.wait(remaining):
                return
            with self._lock:
                if (
                        self._machine.state is not RecordingState.RECORDING
                        or self._next_interval_deadline != deadline
                ):
                    continue
                try:
                    config = self._require_config()
                    self._finalize_current_segment()
                    segment = self._pending_segments.pop()
                    destination = self._next_interval_destination(config.output_path)
                    self._storage.validate_destination(
                        destination,
                        config.overwrite,
                        config.create_output_directory,
                    )
                    self._storage.commit(segment, destination, config.overwrite)
                    self._storage.remove_segment(segment)
                    self._saved_outputs.append(destination)
                    displays = self.enumerate_displays()
                    if config.display_index >= len(displays):
                        raise DisplayUnavailableError(
                            "Selected display is unavailable."
                        )
                    self._start_new_segment(displays[config.display_index])
                    self._schedule_next_interval()
                    LOGGER.info(
                        "Recording interval saved",
                        extra=self._context("interval_save"),
                    )
                except Exception as error:
                    self._set_failed(error)
                    self._interval_stop.set()
                    LOGGER.exception(
                        "Recording interval save failed",
                        extra=self._context("interval_save"),
                    )
                    return

    def _start_interval_worker(self) -> None:
        config = self._require_config()
        if config.save_interval_seconds is None:
            return
        self._interval_thread = threading.Thread(
            target=self._interval_loop,
            name=f"autoscreenrec-interval-{self._session_id}",
            daemon=True,
        )
        self._interval_thread.start()

    def _stop_interval_worker(self) -> None:
        self._interval_stop.set()
        worker = self._interval_thread
        if worker is not None and worker is not threading.current_thread():
            worker.join(timeout=self._timeout() if self._config else 10.0)
            if worker.is_alive():
                raise RecordingError("Interval save worker did not stop in time.")
        self._interval_thread = None

    def _schedule_next_interval(self) -> None:
        interval = self._require_config().save_interval_seconds
        self._next_interval_deadline = (
            None if interval is None else time.monotonic() + interval
        )

    def _start_new_segment(self, display: DisplayInfo) -> None:
        config = self._require_config()
        segment = self._storage.create_segment(f".{config.output_format.value}")
        self._backend.start(config, display, segment)
        self._current_segment = segment
        self._started = time.monotonic()

    def _finalize_current_segment(self) -> None:
        if self._current_segment is None:
            return
        self._elapsed += self._running_elapsed()
        self._backend.stop(self._timeout())
        self._pending_segments.append(self._current_segment)
        self._current_segment = None
        self._started = None

    def _save_pending(self, destination: Path) -> Path:
        config = self._require_config()
        self._storage.validate_destination(
            destination,
            config.overwrite,
            config.create_output_directory,
        )
        assembled = self._storage.create_assembled(f".{config.output_format.value}")
        self._backend.concatenate(config, self._pending_segments, assembled)
        self._storage.commit(assembled, destination, config.overwrite)
        self._saved_outputs.append(destination)
        for segment in list(self._pending_segments):
            self._storage.remove_segment(segment)
        self._pending_segments = []
        return destination

    def _next_interval_destination(self, base: Path) -> Path:
        self._part_index += 1
        return self._storage.interval_destination(base, self._part_index)

    def _validate_all_destinations(self, config: RecordingConfig) -> None:
        destination = (
            config.output_path
            if config.save_interval_seconds is None
            else self._storage.interval_destination(config.output_path, 1)
        )
        self._storage.validate_destination(
            destination,
            config.overwrite,
            config.create_output_directory,
        )

    def _require_state(self, expected: RecordingState) -> None:
        if self._machine.state is not expected:
            raise InvalidStateTransitionError(
                f"Operation requires {expected.value}, current state is "
                f"{self._machine.state.value}."
            )

    def _running_elapsed(self) -> float:
        return (
            0.0 if self._started is None else max(0.0, time.monotonic() - self._started)
        )

    def _timeout(self) -> float:
        return self._require_config().stop_timeout_seconds

    def _require_config(self) -> RecordingConfig:
        if self._config is None:
            raise RecordingError("No recording session is configured.")
        return self._config

    def _set_failed(self, error: Exception, *, cleanup: bool = True) -> None:
        self._error = str(error)
        self._started = None
        self._next_interval_deadline = None
        current = self._machine.state
        if current is RecordingState.IDLE:
            self._machine.transition(RecordingState.RECORDING)
            current = RecordingState.RECORDING
        if current in {
            RecordingState.RECORDING,
            RecordingState.PAUSED,
            RecordingState.STOPPED,
        }:
            self._machine.transition(RecordingState.FAILED)
        if cleanup:
            try:
                self._storage.cleanup()
            except Exception as cleanup_error:
                LOGGER.error(
                    "Temporary cleanup failed after recording failure",
                    extra={
                        **self._context("cleanup"),
                        "cleanup_error": str(cleanup_error),
                    },
                )

    def _context(self, operation: str) -> dict[str, object]:
        return {
            "session_id": self._session_id,
            "state": self._machine.state.value,
            "backend": type(self._backend).__name__,
            "operation": operation,
        }
