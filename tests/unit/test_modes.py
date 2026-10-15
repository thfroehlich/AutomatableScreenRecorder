"""Mode behavior tests."""

import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from automated_screen_recorder import (
    RecordingConfig,
    RecordingMode,
    RecordingState,
    ScreenRecorder,
)
from automated_screen_recorder.exceptions import InvalidStateTransitionError

from .fakes import FakeBackend


def test_normal_mode_saves_one_output(tmp_path: Path) -> None:
    target = (tmp_path / "normal.mp4").resolve()
    recorder = ScreenRecorder(FakeBackend())
    recorder.start_recording(RecordingConfig(output_path=target))
    recorder.stop_recording()
    result = recorder.save_recording()
    assert result.mode is RecordingMode.NORMAL
    assert result.output_paths == [target]
    assert target.is_file()


def test_interval_mode_requires_interval(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        RecordingConfig(
            output_path=(tmp_path / "interval.mp4").resolve(),
            mode=RecordingMode.INTERVAL,
        )


def test_interval_mode_writes_numbered_parts(tmp_path: Path) -> None:
    base = (tmp_path / "interval.mp4").resolve()
    recorder = ScreenRecorder(FakeBackend())
    recorder.start_recording(
        RecordingConfig(
            output_path=base,
            mode=RecordingMode.INTERVAL,
            interval_seconds=1.0,
        )
    )
    time.sleep(1.1)
    recorder.stop_recording()
    result = recorder.save_recording()
    assert (tmp_path / "interval.part000001.mp4").is_file()
    assert (tmp_path / "interval.part000002.mp4").is_file()
    assert len(result.output_paths) == 2


def test_replay_mode_defaults_to_sixty_seconds(tmp_path: Path) -> None:
    config = RecordingConfig(
        output_path=(tmp_path / "replay.mp4").resolve(),
        mode=RecordingMode.REPLAY,
    )
    assert config.replay_buffer_seconds == 60.0


def test_replay_save_continues_recording(tmp_path: Path) -> None:
    backend = FakeBackend()
    base = (tmp_path / "replay.mp4").resolve()
    recorder = ScreenRecorder(backend)
    recorder.start_recording(
        RecordingConfig(
            output_path=base,
            mode=RecordingMode.REPLAY,
            replay_buffer_seconds=5.0,
            replay_segment_seconds=0.5,
        )
    )
    time.sleep(0.6)
    result = recorder.save_replay_buffer()
    status = recorder.get_status()
    assert result.output_path == tmp_path / "replay.replay000001.mp4"
    assert result.output_path.is_file()
    assert status.state is RecordingState.RECORDING
    assert backend.start_count >= 2
    recorder.cancel_recording()


def test_replay_save_rejected_in_normal_mode(tmp_path: Path) -> None:
    recorder = ScreenRecorder(FakeBackend())
    recorder.start_recording(
        RecordingConfig(output_path=(tmp_path / "normal.mp4").resolve())
    )
    with pytest.raises(InvalidStateTransitionError):
        recorder.save_replay_buffer()
    recorder.cancel_recording()


def test_replay_buffer_is_bounded(tmp_path: Path) -> None:
    recorder = ScreenRecorder(FakeBackend())
    recorder.start_recording(
        RecordingConfig(
            output_path=(tmp_path / "bounded.mp4").resolve(),
            mode=RecordingMode.REPLAY,
            replay_buffer_seconds=5.0,
            replay_segment_seconds=0.5,
        )
    )
    time.sleep(1.2)
    status = recorder.get_status()
    assert 0.0 < status.buffered_seconds <= 5.0
    recorder.cancel_recording()
