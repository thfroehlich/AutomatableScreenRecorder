"""FFmpeg capture backend and replaceable process protocol."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Protocol

from automated_screen_recorder.exceptions import ExternalProcessError
from automated_screen_recorder.models import DisplayInfo, RecordingConfig


class CaptureProcess(Protocol):
    """Backend boundary consumed by the recording service."""

    def start(
        self,
        config: RecordingConfig,
        display: DisplayInfo,
        target: Path,
    ) -> None:
        """Start one recording segment."""
        raise NotImplementedError

    def stop(self, timeout: float) -> None:
        """Finalize the active segment."""
        raise NotImplementedError

    def cancel(self, timeout: float) -> None:
        """Terminate the active segment."""
        raise NotImplementedError

    def concatenate(
        self,
        config: RecordingConfig,
        segments: list[Path],
        target: Path,
        *,
        start_offset_seconds: float = 0.0,
        maximum_duration_seconds: float | None = None,
    ) -> None:
        """Join compatible finalized segments without video re-encoding."""
        raise NotImplementedError

    def command(
        self,
        config: RecordingConfig,
        display: DisplayInfo,
        target: Path,
    ) -> list[str]:
        """Return capture-process arguments."""
        raise NotImplementedError


class FfmpegBackend:
    """Capture and encode video-only segments with FFmpeg."""

    def __init__(self) -> None:
        self._process: subprocess.Popen[bytes] | None = None
        self._stderr: tempfile.SpooledTemporaryFile[bytes] | None = None

    @staticmethod
    def discover(configured: Path | None) -> Path:
        """Find FFmpeg without silently downloading it."""
        environment = os.environ.get("AUTOSCREENREC_FFMPEG")
        candidates = [
            configured,
            Path(environment) if environment else None,
            Path.cwd() / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe",
        ]
        discovered = shutil.which("ffmpeg.exe") or shutil.which("ffmpeg")
        candidates.append(Path(discovered) if discovered else None)
        for candidate in candidates:
            if candidate is not None and candidate.is_file():
                return candidate.resolve()
        raise ExternalProcessError(
            "FFmpeg was not found. Configure ffmpeg_path or AUTOSCREENREC_FFMPEG."
        )

    @staticmethod
    def validate_version(path: Path) -> str:
        """Validate that the selected executable identifies as FFmpeg."""
        try:
            result = subprocess.run(
                [str(path), "-version"],
                capture_output=True,
                text=True,
                check=False,
                shell=False,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise ExternalProcessError("FFmpeg version validation failed.") from error
        if result.returncode != 0 or not result.stdout.startswith("ffmpeg version"):
            raise ExternalProcessError("The configured FFmpeg executable is invalid.")
        return result.stdout.splitlines()[0]

    def command(
        self,
        config: RecordingConfig,
        display: DisplayInfo,
        target: Path,
    ) -> list[str]:
        """Build one video-only Windows desktop capture command."""
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
        if config.width is not None and config.height is not None:
            command.extend(
                [
                    "-vf",
                    "scale="
                    f"{config.width}:{config.height}:"
                    "force_original_aspect_ratio=decrease,"
                    f"pad={config.width}:{config.height}:(ow-iw)/2:(oh-ih)/2",
                ]
            )
        command.extend(
            [
                "-c:v",
                config.codec.value,
                "-preset",
                config.encoder_preset,
                "-pix_fmt",
                "yuv420p",
                str(target),
            ]
        )
        return command

    def start(
        self,
        config: RecordingConfig,
        display: DisplayInfo,
        target: Path,
    ) -> None:
        """Start one segment and detect immediate initialization failure."""
        if self._process is not None:
            raise ExternalProcessError("FFmpeg is already running.")
        self._stderr = tempfile.SpooledTemporaryFile(
            max_size=64 * 1024,
            mode="w+b",
        )
        try:
            self._process = subprocess.Popen(
                self.command(config, display, target),
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=self._stderr,
                shell=False,
            )
            time.sleep(0.15)
            if self._process.poll() is not None:
                diagnostic = self._read_stderr()
                self._process = None
                self._close_stderr()
                raise ExternalProcessError(
                    f"FFmpeg terminated during startup: {diagnostic}"
                )
        except Exception:
            process = self._process
            if process is not None and process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            self._process = None
            self._close_stderr()
            raise

    def stop(self, timeout: float) -> None:
        """Request graceful finalization and enforce a timeout."""
        process = self._require_process()
        process_stdin = process.stdin
        if process_stdin is not None:
            try:
                process_stdin.write(b"q\n")
                process_stdin.flush()
            except OSError:
                pass
        self._wait(process, timeout, allow_nonzero=False)
        diagnostic = self._read_stderr()
        return_code = process.returncode
        self._process = None
        self._close_stderr()
        if return_code != 0:
            raise ExternalProcessError(
                f"FFmpeg failed while finalizing the recording: {diagnostic}"
            )

    def cancel(self, timeout: float) -> None:
        """Terminate the active capture process."""
        process = self._process
        if process is None:
            self._close_stderr()
            return
        process.terminate()
        self._wait(process, timeout, allow_nonzero=True)
        self._process = None
        self._close_stderr()

    def concatenate(
        self,
        config: RecordingConfig,
        segments: list[Path],
        target: Path,
        *,
        start_offset_seconds: float = 0.0,
        maximum_duration_seconds: float | None = None,
    ) -> None:
        """Join segments and optionally retain only a bounded tail."""
        if not segments:
            raise ExternalProcessError("No recording segments are available.")
        executable = self.discover(config.ffmpeg_path)
        self.validate_version(executable)
        manifest = target.with_suffix(".concat.txt")
        manifest.write_text(
            "".join(f"file '{path.resolve().as_posix()}'\n" for path in segments),
            encoding="utf-8",
        )
        command = [
            str(executable),
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(manifest),
        ]
        if start_offset_seconds > 0:
            command.extend(["-ss", f"{start_offset_seconds:.6f}"])
        if maximum_duration_seconds is not None:
            command.extend(["-t", f"{maximum_duration_seconds:.6f}"])
        command.extend(
            [
                "-map",
                "0:v:0",
                "-c",
                "copy",
                "-an",
                "-y",
                str(target),
            ]
        )
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                shell=False,
                timeout=max(30.0, config.stop_timeout_seconds),
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise ExternalProcessError("FFmpeg concatenation failed.") from error
        finally:
            manifest.unlink(missing_ok=True)
        if result.returncode != 0 or not target.is_file():
            target.unlink(missing_ok=True)
            diagnostic = result.stderr.strip()[-1000:] or "no diagnostic output"
            raise ExternalProcessError(f"FFmpeg concatenation failed: {diagnostic}")

    def _require_process(self) -> subprocess.Popen[bytes]:
        if self._process is None:
            raise ExternalProcessError("FFmpeg is not running.")
        return self._process

    @staticmethod
    def _wait(
        process: subprocess.Popen[bytes],
        timeout: float,
        allow_nonzero: bool,
    ) -> None:
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as error:
            process.kill()
            process.wait(timeout=5)
            if not allow_nonzero:
                raise ExternalProcessError(
                    "FFmpeg did not stop within the configured timeout."
                ) from error

    def _read_stderr(self) -> str:
        stderr_file = self._stderr
        if stderr_file is None:
            return "no diagnostic output"
        stderr_file.flush()
        stderr_file.seek(0)
        data = stderr_file.read().decode("utf-8", errors="replace")
        return data.strip()[-1000:] or "no diagnostic output"

    def _close_stderr(self) -> None:
        if self._stderr is not None:
            self._stderr.close()
            self._stderr = None
