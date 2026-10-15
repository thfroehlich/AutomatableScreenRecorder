"""Thread-safe recording service for normal, interval, and replay modes."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass
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
    RecordingMode,
    RecordingResult,
    RecordingState,
    RecordingStatus,
)
from automated_screen_recorder.platform_windows import enumerate_displays
from automated_screen_recorder.state import RecordingStateMachine
from automated_screen_recorder.storage import RecordingStorage

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SegmentEntry:
    """One finalized temporary capture segment."""

    path: Path
    duration_seconds: float


class ScreenRecorder:
    """Stable facade for all supported recording modes."""

    def __init__(
        self,
        backend: CaptureProcess | None = None,
        storage: RecordingStorage | None = None,
    ) -> None:
        self._backend = backend or FfmpegBackend()
        self._storage = storage or RecordingStorage()
        self._machine = RecordingStateMachine()
        self._lock = threading.RLock()
        self._rotation_stop = threading.Event()
        self._rotation_thread: threading.Thread | None = None
        self._config: RecordingConfig | None = None
        self._session_id: str | None = None
        self._started_at: str | None = None
        self._current_segment: Path | None = None
        self._segment_started: float | None = None
        self._segments: list[SegmentEntry] = []
        self._saved_outputs: list[Path] = []
        self._elapsed_seconds = 0.0
        self._next_rotation_deadline: float | None = None
        self._interval_index = 0
        self._replay_index = 0
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
        """Start a session in the configured mode."""
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
            self._validate_initial_destination(config)
            display = self._selected_display(config)
            self._storage.create_session()
            self._config = config
            self._session_id = str(uuid.uuid4())
            self._started_at = datetime.now(UTC).isoformat()
            self._segments = []
            self._saved_outputs = []
            self._elapsed_seconds = 0.0
            self._interval_index = 0
            self._replay_index = 0
            self._error = None
            self._rotation_stop.clear()
            try:
                self._start_segment(display)
                self._machine.transition(RecordingState.RECORDING)
                self._schedule_rotation()
                self._start_rotation_worker()
            except Exception as error:
                self._set_failed(error)
                raise RecordingError("Recording could not be started.") from error
            LOGGER.info("Recording started", extra=self._context("start"))
            return self.get_status()

    def pause_recording(self) -> RecordingStatus:
        """Pause capture after finalizing the current segment."""
        with self._lock:
            self._require_state(RecordingState.RECORDING)
            try:
                self._finalize_current_segment()
                self._trim_replay_buffer()
                self._next_rotation_deadline = None
                self._machine.transition(RecordingState.PAUSED)
            except Exception as error:
                self._set_failed(error)
                raise RecordingError("Recording could not be paused.") from error
            LOGGER.info("Recording paused", extra=self._context("pause"))
            return self.get_status()

    def resume_recording(self) -> RecordingStatus:
        """Resume capture in a fresh segment."""
        with self._lock:
            self._require_state(RecordingState.PAUSED)
            try:
                self._start_segment(self._selected_display(self._require_config()))
                self._machine.transition(RecordingState.RECORDING)
                self._schedule_rotation()
            except Exception as error:
                self._set_failed(error)
                raise RecordingError("Recording could not be resumed.") from error
            LOGGER.info("Recording resumed", extra=self._context("resume"))
            return self.get_status()

    def stop_recording(self) -> RecordingStatus:
        """Stop capture while retaining data for an explicit save."""
        self._stop_rotation_worker()
        with self._lock:
            if self._machine.state not in {
                RecordingState.RECORDING,
                RecordingState.PAUSED,
            }:
                raise InvalidStateTransitionError(
                    "Recording can only be stopped while recording or paused."
                )
            try:
                if self._machine.state is RecordingState.RECORDING:
                    self._finalize_current_segment()
                self._trim_replay_buffer()
                self._next_rotation_deadline = None
                self._machine.transition(RecordingState.STOPPED)
            except Exception as error:
                self._set_failed(error)
                raise RecordingError("Recording could not be stopped.") from error
            LOGGER.info("Recording stopped", extra=self._context("stop"))
            return self.get_status()

    def save_recording(self, output_path: Path | None = None) -> RecordingResult:
        """Save a stopped session and mark it complete."""
        with self._lock:
            self._require_state(RecordingState.STOPPED)
            config = self._require_config()
            try:
                if config.mode is RecordingMode.REPLAY:
                    result = self._save_replay_snapshot(output_path)
                elif config.mode is RecordingMode.INTERVAL:
                    result = self._save_final_interval(output_path)
                else:
                    destination = output_path or config.output_path
                    result = self._save_entries(
                        self._segments,
                        destination,
                        duration_seconds=sum(
                            segment.duration_seconds for segment in self._segments
                        ),
                    )
                    self._remove_entries(self._segments)
                    self._segments = []
                self._storage.cleanup()
                self._machine.transition(RecordingState.SAVED)
            except Exception as error:
                self._set_failed(error, cleanup=False)
                raise SaveError("Recording could not be saved.") from error
            LOGGER.info("Recording saved", extra=self._context("save"))
            return result

    def save_replay_buffer(
        self,
        output_path: Path | None = None,
    ) -> RecordingResult:
        """Persist the most recent replay window and continue recording."""
        with self._lock:
            config = self._require_config()
            if config.mode is not RecordingMode.REPLAY:
                raise InvalidStateTransitionError(
                    "Replay-buffer saving is only available in replay mode."
                )
            if self._machine.state not in {
                RecordingState.RECORDING,
                RecordingState.PAUSED,
                RecordingState.STOPPED,
            }:
                raise InvalidStateTransitionError(
                    "Replay buffer can only be saved while recording, "
                    "paused, or stopped."
                )
            restart = self._machine.state is RecordingState.RECORDING
            try:
                if restart:
                    self._finalize_current_segment()
                    self._trim_replay_buffer()
                result = self._save_replay_snapshot(output_path)
                if restart:
                    self._start_segment(self._selected_display(config))
                    self._schedule_rotation()
            except Exception as error:
                self._set_failed(error)
                raise SaveError("Replay buffer could not be saved.") from error
            LOGGER.info("Replay buffer saved", extra=self._context("save_replay"))
            return result

    def cancel_recording(self) -> RecordingStatus:
        """Cancel active work and remove temporary data."""
        self._stop_rotation_worker()
        with self._lock:
            if self._machine.state not in {
                RecordingState.RECORDING,
                RecordingState.PAUSED,
                RecordingState.STOPPED,
            }:
                raise InvalidStateTransitionError(
                    "Recording can only be cancelled from an active or stopped session."
                )
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
            self._segment_started = None
            self._segments = []
            self._next_rotation_deadline = None
            if failures:
                self._set_failed(failures[0], cleanup=False)
                raise CancellationError(
                    "Recording cancellation did not complete cleanly."
                ) from failures[0]
            self._machine.transition(RecordingState.CANCELLED)
            LOGGER.info("Recording cancelled", extra=self._context("cancel"))
            return self.get_status()

    def get_status(self) -> RecordingStatus:
        """Return a thread-safe status snapshot."""
        with self._lock:
            remaining = None
            if self._next_rotation_deadline is not None:
                remaining = max(
                    0.0,
                    self._next_rotation_deadline - time.monotonic(),
                )
            return RecordingStatus(
                session_id=self._session_id,
                state=self._machine.state,
                mode=self._config.mode if self._config else None,
                started_at=self._started_at,
                elapsed_seconds=self._elapsed_seconds + self._active_elapsed(),
                buffered_seconds=self._buffered_seconds(),
                saved_output_paths=list(self._saved_outputs),
                next_rotation_in_seconds=remaining,
                backend=type(self._backend).__name__,
                error=self._error,
            )

    def _start_rotation_worker(self) -> None:
        config = self._require_config()
        if config.mode is RecordingMode.NORMAL:
            return
        self._rotation_thread = threading.Thread(
            target=self._rotation_loop,
            name=f"autoscreenrec-rotation-{self._session_id}",
            daemon=True,
        )
        self._rotation_thread.start()

    def _stop_rotation_worker(self) -> None:
        self._rotation_stop.set()
        worker = self._rotation_thread
        if worker is not None and worker is not threading.current_thread():
            worker.join(timeout=self._timeout() if self._config else 10.0)
            if worker.is_alive():
                raise RecordingError("Rotation worker did not stop in time.")
        self._rotation_thread = None

    def _rotation_loop(self) -> None:
        while not self._rotation_stop.is_set():
            with self._lock:
                deadline = self._next_rotation_deadline
                is_recording = self._machine.state is RecordingState.RECORDING
            if not is_recording or deadline is None:
                self._rotation_stop.wait(0.25)
                continue
            if self._rotation_stop.wait(max(0.0, deadline - time.monotonic())):
                return
            with self._lock:
                if (
                    self._machine.state is not RecordingState.RECORDING
                    or self._next_rotation_deadline != deadline
                ):
                    continue
                try:
                    config = self._require_config()
                    self._finalize_current_segment()
                    if config.mode is RecordingMode.INTERVAL:
                        self._save_completed_interval()
                    else:
                        self._trim_replay_buffer()
                    self._start_segment(self._selected_display(config))
                    self._schedule_rotation()
                    LOGGER.info(
                        "Recording segment rotated",
                        extra=self._context("rotate"),
                    )
                except Exception as error:
                    self._set_failed(error)
                    self._rotation_stop.set()
                    LOGGER.exception(
                        "Recording rotation failed",
                        extra=self._context("rotate"),
                    )
                    return

    def _schedule_rotation(self) -> None:
        config = self._require_config()
        if config.mode is RecordingMode.NORMAL:
            self._next_rotation_deadline = None
        elif config.mode is RecordingMode.INTERVAL:
            interval = config.interval_seconds
            if interval is None:
                raise RecordingError("Interval duration is unavailable.")
            self._next_rotation_deadline = time.monotonic() + interval
        else:
            self._next_rotation_deadline = (
                time.monotonic() + config.replay_segment_seconds
            )

    def _start_segment(self, display: DisplayInfo) -> None:
        config = self._require_config()
        segment = self._storage.create_segment(f".{config.output_format.value}")
        self._backend.start(config, display, segment)
        self._current_segment = segment
        self._segment_started = time.monotonic()

    def _finalize_current_segment(self) -> None:
        if self._current_segment is None:
            return
        duration = self._active_elapsed()
        self._backend.stop(self._timeout())
        self._segments.append(
            SegmentEntry(
                path=self._current_segment,
                duration_seconds=duration,
            )
        )
        self._elapsed_seconds += duration
        self._current_segment = None
        self._segment_started = None

    def _save_completed_interval(self) -> RecordingResult:
        if not self._segments:
            raise SaveError("No finalized interval is available.")
        self._interval_index += 1
        destination = self._storage.interval_destination(
            self._require_config().output_path,
            self._interval_index,
        )
        entries = list(self._segments)
        result = self._save_entries(
            entries,
            destination,
            duration_seconds=sum(entry.duration_seconds for entry in entries),
        )
        self._remove_entries(entries)
        self._segments = []
        return result

    def _save_final_interval(self, output_path: Path | None) -> RecordingResult:
        if output_path is not None:
            destination = output_path
        else:
            self._interval_index += 1
            destination = self._storage.interval_destination(
                self._require_config().output_path,
                self._interval_index,
            )
        entries = list(self._segments)
        result = self._save_entries(
            entries,
            destination,
            duration_seconds=sum(entry.duration_seconds for entry in entries),
        )
        self._remove_entries(entries)
        self._segments = []
        return result

    def _save_replay_snapshot(self, output_path: Path | None) -> RecordingResult:
        config = self._require_config()
        if not self._segments:
            raise SaveError("Replay buffer does not contain finalized video yet.")
        if output_path is None:
            self._replay_index += 1
            destination = self._storage.replay_destination(
                config.output_path,
                self._replay_index,
            )
        else:
            destination = output_path
        total_duration = sum(entry.duration_seconds for entry in self._segments)
        retained_duration = min(total_duration, config.replay_buffer_seconds)
        start_offset = max(0.0, total_duration - retained_duration)
        return self._save_entries(
            list(self._segments),
            destination,
            duration_seconds=retained_duration,
            start_offset_seconds=start_offset,
            maximum_duration_seconds=config.replay_buffer_seconds,
        )

    def _save_entries(
        self,
        entries: list[SegmentEntry],
        destination: Path,
        *,
        duration_seconds: float,
        start_offset_seconds: float = 0.0,
        maximum_duration_seconds: float | None = None,
    ) -> RecordingResult:
        if not entries:
            raise SaveError("No finalized recording data is available.")
        config = self._require_config()
        if destination.suffix.lower() != f".{config.output_format.value}":
            raise SaveError("Output path suffix must match output format.")
        self._storage.validate_destination(
            destination,
            config.overwrite,
            config.create_output_directory,
        )
        assembled = self._storage.create_assembled(f".{config.output_format.value}")
        self._backend.concatenate(
            config,
            [entry.path for entry in entries],
            assembled,
            start_offset_seconds=start_offset_seconds,
            maximum_duration_seconds=maximum_duration_seconds,
        )
        self._storage.commit(assembled, destination, config.overwrite)
        self._storage.remove(assembled)
        self._saved_outputs.append(destination)
        return RecordingResult(
            session_id=self._session_id or "",
            mode=config.mode,
            output_path=destination,
            output_paths=list(self._saved_outputs),
            duration_seconds=duration_seconds,
            file_size_bytes=destination.stat().st_size,
            total_file_size_bytes=sum(
                path.stat().st_size for path in self._saved_outputs if path.is_file()
            ),
            codec=config.codec,
        )

    def _trim_replay_buffer(self) -> None:
        config = self._require_config()
        if config.mode is not RecordingMode.REPLAY:
            return
        allowed = config.replay_buffer_seconds + config.replay_segment_seconds
        total = sum(entry.duration_seconds for entry in self._segments)
        while len(self._segments) > 1:
            oldest = self._segments[0]
            if total - oldest.duration_seconds < allowed:
                break
            self._storage.remove(oldest.path)
            self._segments.pop(0)
            total -= oldest.duration_seconds

    def _remove_entries(self, entries: list[SegmentEntry]) -> None:
        for entry in entries:
            self._storage.remove(entry.path)

    def _validate_initial_destination(self, config: RecordingConfig) -> None:
        if config.mode is RecordingMode.NORMAL:
            destination = config.output_path
        elif config.mode is RecordingMode.INTERVAL:
            destination = self._storage.interval_destination(config.output_path, 1)
        else:
            destination = self._storage.replay_destination(config.output_path, 1)
        self._storage.validate_destination(
            destination,
            config.overwrite,
            config.create_output_directory,
        )

    def _selected_display(self, config: RecordingConfig) -> DisplayInfo:
        displays = self.enumerate_displays()
        if config.display_index >= len(displays):
            raise DisplayUnavailableError("Selected display is unavailable.")
        return displays[config.display_index]

    def _buffered_seconds(self) -> float:
        config = self._config
        if config is None or config.mode is not RecordingMode.REPLAY:
            return 0.0
        return min(
            config.replay_buffer_seconds,
            sum(entry.duration_seconds for entry in self._segments)
            + self._active_elapsed(),
        )

    def _active_elapsed(self) -> float:
        if self._segment_started is None:
            return 0.0
        return max(0.0, time.monotonic() - self._segment_started)

    def _timeout(self) -> float:
        return self._require_config().stop_timeout_seconds

    def _require_config(self) -> RecordingConfig:
        if self._config is None:
            raise RecordingError("No recording session is configured.")
        return self._config

    def _require_state(self, expected: RecordingState) -> None:
        if self._machine.state is not expected:
            raise InvalidStateTransitionError(
                f"Operation requires {expected.value}; current state is "
                f"{self._machine.state.value}."
            )

    def _set_failed(self, error: Exception, *, cleanup: bool = True) -> None:
        self._error = str(error)
        self._segment_started = None
        self._current_segment = None
        self._next_rotation_deadline = None
        state = self._machine.state
        if state is RecordingState.IDLE:
            self._machine.transition(RecordingState.RECORDING)
            state = RecordingState.RECORDING
        if state in {
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
                    "Temporary cleanup failed",
                    extra={
                        **self._context("cleanup"),
                        "cleanup_error": str(cleanup_error),
                    },
                )

    def _context(self, operation: str) -> dict[str, object]:
        return {
            "session_id": self._session_id,
            "state": self._machine.state.value,
            "mode": self._config.mode.value if self._config else None,
            "backend": type(self._backend).__name__,
            "operation": operation,
        }
