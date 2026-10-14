"""FFmpeg process backend and testable protocol."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Protocol

from automated_screen_recorder.exceptions import ExternalProcessError
from automated_screen_recorder.models import DisplayInfo, RecordingConfig


class CaptureProcess(Protocol):
    """Minimal process adapter used by the service."""

    def start(
        self, config: RecordingConfig, display: DisplayInfo, target: Path
    ) -> None:
        raise NotImplementedError

    def stop(self, timeout: float) -> None:
        raise NotImplementedError

    def cancel(self, timeout: float) -> None:
        raise NotImplementedError

    def command(
        self, config: RecordingConfig, display: DisplayInfo, target: Path
    ) -> list[str]:
        raise NotImplementedError


class FfmpegBackend:
    """Capture screen pixels and encode them in one FFmpeg process."""

    def __init__(self) -> None:
        self._process: subprocess.Popen[bytes] | None = None

    @staticmethod
    def discover(configured: Path | None) -> Path:
        candidates = [
            configured,
            Path(os.environ["AUTOSCREENREC_FFMPEG"])
            if "AUTOSCREENREC_FFMPEG" in os.environ
            else None,
            Path.cwd() / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe",
        ]
        found = shutil.which("ffmpeg.exe")
        if found:
            candidates.append(Path(found))
        for candidate in candidates:
            if candidate and candidate.is_file():
                return candidate.resolve()
        raise ExternalProcessError(
            "FFmpeg executable was not found. Configure ffmpeg_path or install the local tool bundle."
        )

    @classmethod
    def validate_version(cls, path: Path) -> str:
        result = subprocess.run(
            [str(path), "-version"],
            capture_output=True,
            text=True,
            check=False,
            shell=False,
            timeout=10,
        )
        if result.returncode or not result.stdout.startswith("ffmpeg version"):
            raise ExternalProcessError("The configured FFmpeg executable is invalid.")
        return result.stdout.splitlines()[0]

    def command(
        self, config: RecordingConfig, display: DisplayInfo, target: Path
    ) -> list[str]:
        executable = self.discover(config.ffmpeg_path)
        self.validate_version(executable)
        command = [
            str(executable),
            "-hide_banner",
            "-loglevel",
            "warning",
            "-nostats",
            "-y",
            "-f",
            "gdigrab",
            "-draw_mouse",
            "1",
            "-framerate",
            str(config.frame_rate),
            "-offset_x",
            str(display.left),
            "-offset_y",
            str(display.top),
            "-video_size",
            f"{display.width}x{display.height}",
            "-i",
            "desktop",
            "-an",
        ]
        if config.width is not None:
            command += [
                "-vf",
                f"scale={config.width}:{config.height}:force_original_aspect_ratio=decrease,pad={config.width}:{config.height}:(ow-iw)/2:(oh-ih)/2",
            ]
        command += [
            "-c:v",
            config.codec.value,
            "-preset",
            config.encoder_preset,
            "-pix_fmt",
            "yuv420p",
            str(target),
        ]
        return command

    def start(
        self, config: RecordingConfig, display: DisplayInfo, target: Path
    ) -> None:
        self._process = subprocess.Popen(
            self.command(config, display, target),
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            shell=False,
        )
        if self._process.poll() is not None:
            raise ExternalProcessError("FFmpeg terminated during startup.")

    def stop(self, timeout: float) -> None:
        process = self._require()
        process_stdin = process.stdin

        if process_stdin is not None:
            try:
                process_stdin.write(b"q\n")
                process_stdin.flush()
            except OSError:
                pass

        self._wait(process, timeout, False)
        if process.returncode:
            raise ExternalProcessError("FFmpeg failed while finalizing the recording.")
        self._process = None

    def cancel(self, timeout: float) -> None:
        process = self._process
        if process is None:
            return
        process.terminate()
        self._wait(process, timeout, True)
        self._process = None

    def _require(self) -> subprocess.Popen[bytes]:
        if self._process is None:
            raise ExternalProcessError("FFmpeg process is not running.")
        return self._process

    @staticmethod
    def _wait(
        process: subprocess.Popen[bytes], timeout: float, allow_nonzero: bool
    ) -> None:
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            if not allow_nonzero:
                raise ExternalProcessError(
                    "FFmpeg did not stop within the configured timeout."
                ) from None
