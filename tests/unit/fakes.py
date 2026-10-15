"""Deterministic test doubles."""

from pathlib import Path

from automated_screen_recorder.models import DisplayInfo, RecordingConfig


class FakeBackend:
    """Write small deterministic byte segments without FFmpeg."""

    def __init__(self) -> None:
        self.start_count = 0
        self.stop_count = 0
        self.cancel_count = 0
        self.concatenate_calls: list[tuple[float, float | None]] = []

    def command(
        self,
        config: RecordingConfig,
        display: DisplayInfo,
        target: Path,
    ) -> list[str]:
        del config, display
        return ["fake", "-an", str(target)]

    def start(
        self,
        config: RecordingConfig,
        display: DisplayInfo,
        target: Path,
    ) -> None:
        del config, display
        self.start_count += 1
        target.write_bytes(f"segment-{self.start_count}".encode())

    def stop(self, timeout: float) -> None:
        del timeout
        self.stop_count += 1

    def cancel(self, timeout: float) -> None:
        del timeout
        self.cancel_count += 1

    def concatenate(
        self,
        config: RecordingConfig,
        segments: list[Path],
        target: Path,
        *,
        start_offset_seconds: float = 0.0,
        maximum_duration_seconds: float | None = None,
    ) -> None:
        del config
        self.concatenate_calls.append((start_offset_seconds, maximum_duration_seconds))
        target.write_bytes(b"|".join(path.read_bytes() for path in segments))
