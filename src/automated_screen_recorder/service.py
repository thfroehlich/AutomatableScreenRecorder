"""Recording application service."""
from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from automated_screen_recorder.backends import CaptureProcess, FfmpegBackend
from automated_screen_recorder.exceptions import DisplayUnavailableError, RecordingError
from automated_screen_recorder.models import (DisplayInfo, RecordingConfig, RecordingResult, RecordingState,
                                              RecordingStatus)
from automated_screen_recorder.platform_windows import enumerate_displays
from automated_screen_recorder.state import RecordingStateMachine
from automated_screen_recorder.storage import RecordingStorage

LOGGER = logging.getLogger(__name__)


class ScreenRecorder:
    """Stable, thread-safe facade for video-only screen recording."""

    def __init__(self, backend: CaptureProcess | None = None, storage: RecordingStorage | None = None) -> None:
        self._backend = backend or FfmpegBackend()
        self._storage = storage or RecordingStorage()
        self._machine = RecordingStateMachine()
        self._lock = threading.RLock()
        self._config: RecordingConfig | None = None
        self._temporary: Path | None = None
        self._session_id: str | None = None
        self._started: float | None = None
        self._started_at: str | None = None
        self._elapsed = 0.0
        self._error: str | None = None

    def __enter__(self) -> "ScreenRecorder":
        return self

    def __exit__(self, *_args: object) -> None:
        if self._machine.state in {RecordingState.RECORDING, RecordingState.PAUSED,
                                   RecordingState.STOPPED}:
            self.cancel_recording()

    def enumerate_displays(self) -> list[DisplayInfo]:
        return enumerate_displays()

    def start_recording(self, config: RecordingConfig) -> RecordingStatus:
        with self._lock:
            if self._machine.state in {RecordingState.SAVED, RecordingState.CANCELLED,
                                       RecordingState.FAILED}:
                self._machine.reset()
            self._storage.validate_destination(config.output_path, config.overwrite, config.create_output_directory)
            displays = self.enumerate_displays()
            if config.display_index >= len(displays): raise DisplayUnavailableError("Selected display is unavailable.")
            self._session_id = str(uuid.uuid4())
            self._config = config
            self._temporary = self._storage.create(f".{config.output_format.value}")
            self._started = time.monotonic()
            self._started_at = datetime.now(UTC).isoformat()
            self._elapsed = 0
            self._error = None
            try:
                self._backend.start(config, displays[config.display_index], self._temporary)
                self._machine.transition(RecordingState.RECORDING)
            except Exception as error:
                self._fail(error)
                raise RecordingError("Recording could not be started.") from error
            LOGGER.info("Recording started", extra=self._context("start"))
            return self.get_status()

    def pause_recording(self) -> RecordingStatus:
        with self._lock:
            self._machine.transition(RecordingState.PAUSED)
            self._elapsed += self._running_elapsed()
            self._backend.stop(self._timeout())
            self._started = None
            LOGGER.info("Recording paused", extra=self._context("pause"))
            return self.get_status()

    def resume_recording(self) -> RecordingStatus:
        with self._lock:
            self._machine.transition(RecordingState.RECORDING)
            try:
                self._backend.start(self._require_config(),
                                    self.enumerate_displays()[self._require_config().display_index],
                                    self._require_temp())
            except Exception as error:
                self._fail(error)
                raise RecordingError("Recording could not be resumed.") from error
            self._started = time.monotonic()
            LOGGER.info("Recording resumed", extra=self._context("resume"))
            return self.get_status()

    def stop_recording(self) -> RecordingStatus:
        with self._lock:
            current = self._machine.state
            self._machine.transition(RecordingState.STOPPED)
            if current == RecordingState.RECORDING:
                self._elapsed += self._running_elapsed()
                self._backend.stop(self._timeout())
            self._started = None
            LOGGER.info("Recording stopped", extra=self._context("stop"))
            return self.get_status()

    def cancel_recording(self) -> RecordingStatus:
        with self._lock:
            self._machine.transition(RecordingState.CANCELLED)
            try:
                self._backend.cancel(self._timeout())
            finally:
                self._storage.cleanup()
                self._temporary = None
                self._started = None
            LOGGER.info("Recording cancelled", extra=self._context("cancel"))
            return self.get_status()

    def save_recording(self, output_path: Path | None = None) -> RecordingResult:
        with self._lock:
            config = self._require_config()
            destination = output_path or config.output_path
            self._storage.validate_destination(destination, config.overwrite, config.create_output_directory)
            self._storage.save(self._require_temp(), destination, config.overwrite)
            self._temporary = None
            self._machine.transition(RecordingState.SAVED)
            result = RecordingResult(session_id=self._session_id or "", output_path=destination,
                                     duration_seconds=self._elapsed, file_size_bytes=destination.stat().st_size,
                                     codec=config.codec)
            LOGGER.info("Recording saved", extra=self._context("save"))
            return result

    def get_status(self) -> RecordingStatus:
        with self._lock:
            return RecordingStatus(
                session_id=self._session_id,
                state=self._machine.state,
                started_at=self._started_at,
                elapsed_seconds=self._elapsed + self._running_elapsed(),
                backend=type(self._backend).__name__, error=self._error)

    def _running_elapsed(self) -> float:
        return 0.0 if self._started is None else max(0.0, time.monotonic() - self._started)

    def _timeout(self) -> float:
        return self._require_config().stop_timeout_seconds

    def _require_config(self) -> RecordingConfig:
        if self._config is None:
            raise RecordingError("No recording session is configured.")
        return self._config

    def _require_temp(self) -> Path:
        if self._temporary is None:
            raise RecordingError("Temporary recording is unavailable.")
        return self._temporary

    def _fail(self, error: Exception) -> None:
        self._error = str(error)
        self._started = None
        if self._machine.state in {RecordingState.RECORDING, RecordingState.PAUSED,
                                   RecordingState.STOPPED}:
            self._machine.transition(RecordingState.FAILED)
        self._storage.cleanup()

    def _context(self, operation: str) -> dict[str, object]:
        return {"session_id": self._session_id, "state": self._machine.state.value,
                "backend": type(self._backend).__name__, "operation": operation}
