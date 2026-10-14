"""Secure temporary and final output handling."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from automated_screen_recorder.exceptions import OutputPathError, SaveError


class RecordingStorage:
    """Own private session artifacts and atomic final commits."""

    def __init__(self) -> None:
        self._directory: Path | None = None
        self._segments: list[Path] = []

    @property
    def segments(self) -> list[Path]:
        return list(self._segments)

    def create_session(self) -> None:
        self.cleanup()
        self._directory = Path(tempfile.mkdtemp(prefix="autoscreenrec-"))

    def create_segment(self, suffix: str) -> Path:
        if self._directory is None:
            raise SaveError("Temporary recording storage is unavailable.")
        path = self._directory / f"segment-{len(self._segments):06d}{suffix}"
        self._segments.append(path)
        return path

    def remove_segment(self, path: Path) -> None:
        path.unlink(missing_ok=True)
        if path in self._segments:
            self._segments.remove(path)

    def create_assembled(self, suffix: str) -> Path:
        if self._directory is None:
            raise SaveError("Temporary recording storage is unavailable.")
        return self._directory / f"assembled{suffix}"

    def interval_destination(self, base: Path, index: int) -> Path:
        return base.with_name(f"{base.stem}.part{index:06d}{base.suffix}")

    def validate_destination(
        self, path: Path, overwrite: bool, create_directory: bool
    ) -> None:
        if not path.is_absolute():
            raise OutputPathError("Output path must be absolute.")
        parent = path.parent
        if not parent.exists():
            if not create_directory:
                raise OutputPathError("Output directory does not exist.")
            try:
                parent.mkdir(parents=True, exist_ok=True)
            except OSError as error:
                raise OutputPathError(
                    "Output directory could not be created."
                ) from error
        if not parent.is_dir():
            raise OutputPathError("Output parent is not a directory.")
        if path.exists() and not overwrite:
            raise OutputPathError("Output file already exists.")

    def commit(self, source: Path, destination: Path, overwrite: bool) -> None:
        if not source.is_file():
            raise SaveError("Temporary recording is missing.")
        staging: Path | None = None
        try:
            descriptor, name = tempfile.mkstemp(
                prefix=f".{destination.name}.",
                suffix=".tmp",
                dir=destination.parent,
            )
            os.close(descriptor)
            staging = Path(name)
            shutil.copyfile(source, staging)
            if overwrite:
                os.replace(staging, destination)
            else:
                try:
                    os.link(staging, destination)
                except FileExistsError as error:
                    raise OutputPathError("Output file already exists.") from error
                staging.unlink()
        except (OSError, OutputPathError) as error:
            if staging is not None:
                staging.unlink(missing_ok=True)
            if isinstance(error, OutputPathError):
                raise
            raise SaveError(
                "Recording could not be saved to the output path."
            ) from error

    def cleanup(self) -> None:
        if self._directory and self._directory.exists():
            try:
                shutil.rmtree(self._directory)
            except OSError as error:
                raise SaveError("Temporary recording cleanup failed.") from error
        self._directory = None
        self._segments = []
