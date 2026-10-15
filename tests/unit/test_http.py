"""HTTP adapter tests including replay save idempotency."""

import time
from pathlib import Path

from fastapi.testclient import TestClient

from automated_screen_recorder import ScreenRecorder
from automated_screen_recorder.http import create_app

from .fakes import FakeBackend


def test_replay_buffer_can_be_saved_via_rest(tmp_path: Path) -> None:
    recorder = ScreenRecorder(FakeBackend())
    client = TestClient(create_app(recorder))
    start = client.post(
        "/recordings/start",
        json={
            "request_id": "request-start-0001",
            "config": {
                "output_path": str((tmp_path / "rest.mp4").resolve()),
                "mode": "replay",
                "replay_buffer_seconds": 5.0,
                "replay_segment_seconds": 0.5,
            },
        },
    )
    assert start.status_code == 200
    time.sleep(0.6)
    payload = {"request_id": "request-save-0001"}
    first = client.post("/recordings/save-replay", json=payload)
    second = client.post("/recordings/save-replay", json=payload)
    assert first.status_code == 200
    assert second.json() == first.json()
    assert first.json()["mode"] == "replay"
    client.post(
        "/recordings/cancel",
        json={"request_id": "request-cancel-0001"},
    )
