"""Tests for the optional HTTP API."""

from pathlib import Path

from fastapi.testclient import TestClient

from automated_screen_recorder import (
    DisplayInfo,
    RecordingConfig,
    ScreenRecorder,
)
from automated_screen_recorder.http import (
    create_app,
)


class FakeBackend:
    """Deterministic backend for HTTP unit tests."""

    def __init__(self) -> None:
        """Initialize counters used by assertions."""
        self.start_count = 0
        self.stop_count = 0
        self.cancel_count = 0

    def command(
        self,
        config: RecordingConfig,
        display: DisplayInfo,
        target: Path,
    ) -> list:
        """Return a deterministic synthetic command."""
        return [
            "fake-recorder",
            str(target),
        ]

    def start(
        self,
        config: RecordingConfig,
        display: DisplayInfo,
        target: Path,
    ) -> None:
        """Create a deterministic fake video segment."""
        del config
        del display

        self.start_count += 1

        target.write_bytes(b"video")

    def stop(
        self,
        timeout: float,
    ) -> None:
        """Record one fake stop invocation."""
        del timeout

        self.stop_count += 1

    def cancel(
        self,
        timeout: float,
    ) -> None:
        """Record one fake cancellation invocation."""
        del timeout

        self.cancel_count += 1

    def concatenate(
        self,
        config: RecordingConfig,
        segments: list[Path],
        target: Path,
    ) -> None:
        """Concatenate fake video segments."""
        del config

        content = b"".join(segment.read_bytes() for segment in segments)

        target.write_bytes(content)


def test_status_and_structured_error(
    tmp_path: Path,
) -> None:
    """Return structured errors for invalid transitions."""
    del tmp_path

    backend = FakeBackend()

    client = TestClient(create_app(ScreenRecorder(backend)))

    status_response = client.get("/recordings/status")

    assert status_response.status_code == 200

    response = client.post(
        "/recordings/stop",
        json={
            "request_id": "request-0001",
        },
    )

    assert response.status_code == 409

    response_body = response.json()

    assert response_body["error_type"] == "InvalidStateTransitionError"

    assert response_body["state"] == "idle"


def test_duplicate_start_is_idempotent(
    tmp_path: Path,
) -> None:
    """Execute duplicate start requests only once."""
    backend = FakeBackend()
    recorder = ScreenRecorder(backend)

    client = TestClient(create_app(recorder))

    payload = {
        "request_id": "request-0002",
        "config": {
            "output_path": str((tmp_path / "x.mp4").resolve()),
        },
    }

    first = client.post(
        "/recordings/start",
        json=payload,
    )

    second = client.post(
        "/recordings/start",
        json=payload,
    )

    assert first.status_code == 200
    assert second.status_code == 200

    assert second.json() == first.json()

    assert backend.start_count == 1

    recorder.cancel_recording()


def test_request_identifier_is_scoped_to_operation(
    tmp_path: Path,
) -> None:
    """Allow one request identifier for different operations."""
    backend = FakeBackend()
    recorder = ScreenRecorder(backend)

    client = TestClient(create_app(recorder))

    request_id = "request-0003"

    start_response = client.post(
        "/recordings/start",
        json={
            "request_id": request_id,
            "config": {
                "output_path": str((tmp_path / "recording.mp4").resolve()),
            },
        },
    )

    assert start_response.status_code == 200

    stop_response = client.post(
        "/recordings/stop",
        json={
            "request_id": request_id,
        },
    )

    assert stop_response.status_code == 200
    assert stop_response.json()["state"] == "stopped"
    assert backend.start_count == 1
    assert backend.stop_count == 1

    recorder.cancel_recording()
