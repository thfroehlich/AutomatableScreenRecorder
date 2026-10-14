"""Core service tests using a deterministic backend."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from automated_screen_recorder import RecordingConfig, RecordingState, ScreenRecorder
from automated_screen_recorder.exceptions import (
    InvalidStateTransitionError,
    OutputPathError,
)
from automated_screen_recorder.models import DisplayInfo


class FakeBackend:
    def __init__(self) -> None:
        self.running = False
        self.counter = 0

    def command(
        self, config: RecordingConfig, display: DisplayInfo, target: Path
    ) -> list[str]:
        return ["ffmpeg.exe", "-an", str(target)]

    def start(
        self, config: RecordingConfig, display: DisplayInfo, target: Path
    ) -> None:
        del config, display
        self.running = True
        self.counter += 1
        target.write_bytes(f"video-{self.counter}".encode())

    def stop(self, timeout: float) -> None:
        del timeout
        self.running = False

    def cancel(self, timeout: float) -> None:
        del timeout
        self.running = False

    def concatenate(
        self, config: RecordingConfig, segments: list[Path], target: Path
    ) -> None:
        del config
        target.write_bytes(b"|".join(segment.read_bytes() for segment in segments))


def config(tmp_path: Path) -> RecordingConfig:
    return RecordingConfig(output_path=(tmp_path / "out.mp4").resolve())


def test_model_validation() -> None:
    with pytest.raises(ValidationError):
        RecordingConfig(output_path=Path("relative.mp4"))


def test_lifecycle_and_save(tmp_path: Path) -> None:
    recorder = ScreenRecorder(FakeBackend())
    recorder.start_recording(config(tmp_path))
    assert recorder.pause_recording().state is RecordingState.PAUSED
    recorder.resume_recording()
    recorder.stop_recording()
    result = recorder.save_recording()
    assert result.output_path.read_bytes() == b"video-1|video-2"


def test_cancel_cleans_temporary(tmp_path: Path) -> None:
    recorder = ScreenRecorder(FakeBackend())
    recorder.start_recording(config(tmp_path))
    recorder.cancel_recording()
    assert recorder.get_status().state is RecordingState.CANCELLED


def test_invalid_transition() -> None:
    with pytest.raises(InvalidStateTransitionError):
        ScreenRecorder(FakeBackend()).stop_recording()


def test_prevent_overwrite(tmp_path: Path) -> None:
    target = tmp_path / "out.mp4"
    target.write_bytes(b"old")
    with pytest.raises(OutputPathError):
        ScreenRecorder(FakeBackend()).start_recording(
            RecordingConfig(output_path=target.resolve())
        )
