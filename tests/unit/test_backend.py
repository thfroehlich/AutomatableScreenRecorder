from unittest.mock import patch

from automated_screen_recorder.backends import FfmpegBackend
from automated_screen_recorder.models import (
    DisplayInfo,
    RecordingConfig,
)


def test_command_has_no_audio_and_no_shell(tmp_path):
    executable = tmp_path / "ffmpeg.exe"
    executable.write_bytes(b"x")
    config = RecordingConfig(
        output_path=(tmp_path / "x.mp4").resolve(),
        ffmpeg_path=executable.resolve(),
    )
    display = DisplayInfo(
        index=0,
        name="x",
        left=0,
        top=0,
        width=800,
        height=600,
        primary=True,
    )
    with patch.object(
            FfmpegBackend, "validate_version", return_value="ffmpeg version test"
    ):
        command = FfmpegBackend().command(config, display, tmp_path / "temp.mp4")
    assert "-an" in command and command[0] == str(executable.resolve())
