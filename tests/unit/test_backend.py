"""FFmpeg command construction tests."""

from pathlib import Path
from unittest.mock import patch

from automated_screen_recorder.backends import FfmpegBackend
from automated_screen_recorder.models import DisplayInfo, RecordingConfig


def test_capture_command_is_video_only(tmp_path: Path) -> None:
    executable = (tmp_path / "ffmpeg.exe").resolve()
    executable.write_bytes(b"fake")
    config = RecordingConfig(
        output_path=(tmp_path / "capture.mp4").resolve(),
        ffmpeg_path=executable,
    )
    display = DisplayInfo(
        index=0,
        name="display",
        left=0,
        top=0,
        width=800,
        height=600,
        primary=True,
    )
    with patch.object(
        FfmpegBackend,
        "validate_version",
        return_value="ffmpeg version test",
    ):
        command = FfmpegBackend().command(
            config,
            display,
            tmp_path / "segment.mp4",
        )
    assert "-an" in command
    assert command[0] == str(executable)
