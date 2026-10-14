"""Secure temporary and final output handling."""
import shutil
import tempfile
from pathlib import Path

from automated_screen_recorder.exceptions import OutputPathError, SaveError


class RecordingStorage:
    """Own one private temporary directory and final atomic move."""

    def __init__(self) -> None:
        self._directory: Path | None = None

    def create(self, suffix: str) -> Path:
        self.cleanup()
        self._directory = Path(tempfile.mkdtemp(prefix="autoscreenrec-"))
        return self._directory / f"capture{suffix}"

    def validate_destination(self, path: Path, overwrite: bool, create_directory: bool) -> None:
        parent = path.parent
        if not parent.exists():
            if create_directory:
                parent.mkdir(parents=True, exist_ok=True)
            else:
                raise OutputPathError("Output directory does not exist.")
        if not parent.is_dir():
            raise OutputPathError("Output parent is not a directory.")
        if path.exists() and not overwrite:
            raise OutputPathError("Output file already exists.")

    def save(self, source: Path, destination: Path, overwrite: bool) -> None:
        if not source.is_file():
            raise SaveError("Temporary recording is missing.")
        try:
            if overwrite:
                source.replace(destination)
            else:
                with destination.open("xb") as output, source.open("rb") as input_file:
                    shutil.copyfileobj(input_file, output, 1024 * 1024)
                source.unlink()
        except OSError as error:
            raise SaveError("Recording could not be saved to the output path.") from error
        self.cleanup()

    def cleanup(self) -> None:
        if self._directory and self._directory.exists():
            shutil.rmtree(self._directory)
        self._directory = None
