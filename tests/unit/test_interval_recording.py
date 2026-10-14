"""Tests for optional interval-based saving."""

import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from automated_screen_recorder import RecordingConfig, RecordingState, ScreenRecorder
from automated_screen_recorder.models import DisplayInfo


class FakeBackend:
    """Create deterministic segment bytes without Windows or FFmpeg."""

    def __init__(self) -> None:
        self.start_count = 0
        self.stop_count = 0

    def command(
        self, config: RecordingConfig, display: DisplayInfo, target: Path
    ) -> list[str]:
        return ["fake", "-an", str(target)]

    def start(
        self, config: RecordingConfig, display: DisplayInfo, target: Path
    ) -> None:
        del config, display
        self.start_count += 1
        target.write_bytes(f"segment-{self.start_count}".encode())

    def stop(self, timeout: float) -> None:
        del timeout
        self.stop_count += 1

    def cancel(self, timeout: float) -> None:
        del timeout

    def concatenate(
        self, config: RecordingConfig, segments: list[Path], target: Path
    ) -> None:
        del config
        target.write_bytes(b"|".join(path.read_bytes() for path in segments))


def test_interval_is_optional(tmp_path: Path) -> None:
    config = RecordingConfig(output_path=(tmp_path / "single.mp4").resolve())
    assert config.save_interval_seconds is None


def test_interval_validation(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        RecordingConfig(
            output_path=(tmp_path / "invalid.mp4").resolve(),
            save_interval_seconds=0.01,
        )


def test_interval_saves_numbered_playable_parts(tmp_path: Path) -> None:
    backend = FakeBackend()
    config = RecordingConfig(
        output_path=(tmp_path / "capture.mp4").resolve(),
        save_interval_seconds=0.1,
    )
    with ScreenRecorder(backend) as recorder:
        recorder.start_recording(config)
        time.sleep(0.16)
        status = recorder.get_status()
        assert status.state is RecordingState.RECORDING
        assert status.saved_output_paths == [tmp_path / "capture.part000001.mp4"]
        recorder.stop_recording()
        result = recorder.save_recording()
    assert result.output_paths == [
        tmp_path / "capture.part000001.mp4",
        tmp_path / "capture.part000002.mp4",
    ]
    assert all(path.is_file() for path in result.output_paths)
    assert backend.start_count == 2
    assert backend.stop_count == 2


def test_cancel_keeps_already_committed_interval_files(tmp_path: Path) -> None:
    config = RecordingConfig(
        output_path=(tmp_path / "capture.mp4").resolve(),
        save_interval_seconds=0.1,
    )
    recorder = ScreenRecorder(FakeBackend())
    recorder.start_recording(config)
    time.sleep(0.16)
    recorder.cancel_recording()
    assert (tmp_path / "capture.part000001.mp4").is_file()
