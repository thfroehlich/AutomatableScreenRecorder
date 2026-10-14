from pathlib import Path

from fastapi.testclient import TestClient

from automated_screen_recorder import ScreenRecorder
from automated_screen_recorder.http import create_app


class FakeBackend:
    def command(self, *args):
        return []

    def start(self, config, display, target):
        target.write_bytes(b"video")

    def stop(self, timeout):
        return None

    def cancel(self, timeout):
        return None


def test_status_and_structured_error(tmp_path: Path):
    client = TestClient(create_app(ScreenRecorder(FakeBackend())))
    assert client.get("/recordings/status").status_code == 200
    response = client.post("/recordings/stop", json={
        "request_id": "request-0001",
    })
    assert (response.status_code == 409
            and response.json()["error_type"] == "InvalidStateTransitionError"
            )


def test_duplicate_start_is_idempotent(tmp_path: Path):
    client = TestClient(create_app(ScreenRecorder(FakeBackend())))
    payload = {
        "request_id": "request-0002",
        "config": {
            "output_path": str((tmp_path / "x.mp4").resolve())
        },
    }
    first = client.post("/recordings/start", json=payload)
    second = client.post("/recordings/start", json=payload)
    assert (first.status_code == 200
            and second.json() == first.json()
            )
