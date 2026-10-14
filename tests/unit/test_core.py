from pathlib import Path

import pytest
from pydantic import ValidationError

from automated_screen_recorder import (
    RecordingConfig,
    RecordingState,
    ScreenRecorder)
from automated_screen_recorder.exceptions import (
    InvalidStateTransitionError,
    OutputPathError)


class FakeBackend:
    def __init__(self): self.running = False

    def command(self, config, display, target):
        return ["ffmpeg.exe", "-an", str(target)]

    def start(self, config, display, target):
        self.running = True
        target.write_bytes(b"video")

    def stop(self, timeout):
        self.running = False

    def cancel(self, timeout):
        self.running = False


def config(tmp_path: Path) -> RecordingConfig:
    return RecordingConfig(output_path=(tmp_path / "out.mp4").resolve())


def test_model_validation(tmp_path):
    with pytest.raises(ValidationError):
        RecordingConfig(output_path=Path("relative.mp4"))


def test_lifecycle_and_save(tmp_path):
    recorder = ScreenRecorder(FakeBackend())
    recorder.start_recording(config(tmp_path))
    assert recorder.pause_recording().state == RecordingState.PAUSED
    recorder.resume_recording()
    recorder.stop_recording()
    result = recorder.save_recording()
    assert result.output_path.read_bytes() == b"video"


def test_cancel_cleans_temporary(tmp_path):
    recorder = ScreenRecorder(FakeBackend())
    recorder.start_recording(config(tmp_path))
    recorder.cancel_recording()
    assert recorder.get_status().state == RecordingState.CANCELLED


def test_invalid_transition():
    with pytest.raises(InvalidStateTransitionError):
        ScreenRecorder(FakeBackend()).stop_recording()


def test_prevent_overwrite(tmp_path):
    target = tmp_path / "out.mp4"
    target.write_bytes(b"old")
    with pytest.raises(OutputPathError):
        ScreenRecorder(FakeBackend()).start_recording(
            RecordingConfig(output_path=target.resolve()))


def test_public_import():
    from automated_screen_recorder import ScreenRecorder as Imported
    assert Imported is ScreenRecorder
