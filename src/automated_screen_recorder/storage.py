"""Private temporary storage and atomic final output handling."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from automated_screen_recorder.exceptions import OutputPathError, SaveError


class RecordingStorage:
    """Own all temporary artifacts for one recording session."""

    def __init__(self) -> None:
        self._directory: Path | None = None
        self._counter = 0

    def create_session(self) -> None:
        """Create a new private session directory."""
        self.cleanup()
        self._directory = Path(tempfile.mkdtemp(prefix="autoscreenrec-"))
        self._counter = 0

    def create_segment(self, suffix: str) -> Path:
        """Allocate a unique temporary segment path."""
        directory = self._require_directory()
        path = directory / f"segment-{self._counter:08d}{suffix}"
        self._counter += 1
        return path

    def create_assembled(self, suffix: str) -> Path:
        """Allocate an assembled-output staging path."""
        directory = self._require_directory()
        path = directory / f"assembled-{self._counter:08d}{suffix}"
        self._counter += 1
        return path

    @staticmethod
    def interval_destination(base: Path, index: int) -> Path:
        """Return the numbered destination for interval mode."""
        return base.with_name(f"{base.stem}.part{index:06d}{base.suffix}")

    @staticmethod
    def replay_destination(base: Path, index: int) -> Path:
        """Return a collision-resistant numbered replay destination."""
        return base.with_name(f"{base.stem}.replay{index:06d}{base.suffix}")

    def validate_destination(
        self,
        path: Path,
        overwrite: bool,
        create_directory: bool,
    ) -> None:
        """Validate destination policy without creating the final file."""
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
        """Commit a file through same-directory staging."""
        if not source.is_file():
            raise SaveError("Temporary recording is missing.")
        staging: Path | None = None
        try:
            descriptor, staging_name = tempfile.mkstemp(
                prefix=f".{destination.name}.",
                suffix=".tmp",
                dir=destination.parent,
            )
            os.close(descriptor)
            staging = Path(staging_name)
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
                "Recording could not be committed to the output path."
            ) from error

    @staticmethod
    def remove(path: Path) -> None:
        """Remove one temporary artifact if present."""
        path.unlink(missing_ok=True)

    def cleanup(self) -> None:
        """Delete all temporary artifacts owned by the session."""
        if self._directory is not None and self._directory.exists():
            try:
                shutil.rmtree(self._directory)
            except OSError as error:
                raise SaveError("Temporary recording cleanup failed.") from error
        self._directory = None
        self._counter = 0

    def _require_directory(self) -> Path:
        if self._directory is None:
            raise SaveError("Temporary recording storage is unavailable.")
        return self._directory
