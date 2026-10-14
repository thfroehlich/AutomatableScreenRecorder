"""Optional localhost HTTP adapter."""
from __future__ import annotations

import argparse
import threading
from collections import OrderedDict
from typing import Callable

from automated_screen_recorder.models import ControlRequest, ErrorResponse, SaveRequest, StartRequest
from automated_screen_recorder.service import ScreenRecorder


def create_app(recorder: ScreenRecorder | None = None):
    """Create a FastAPI application without enabling a network listener."""
    try:
        from fastapi import FastAPI, Request
        from fastapi.responses import JSONResponse
    except ImportError as error:
        raise RuntimeError("Install the 'http' optional dependency to use the HTTP API.") from error
    service = recorder or ScreenRecorder()
    app = FastAPI(title="Win Screen Recorder", version="0.1.0")
    lock = threading.RLock()
    cache: OrderedDict[str, object] = OrderedDict()

    def once(key: str, operation: Callable[[], object]) -> object:
        with lock:
            if key in cache: return cache[key]
            result = operation()
            cache[key] = result
            while len(cache) > 256: cache.popitem(last=False)
            return result

    @app.exception_handler(Exception)
    async def error_handler(_request: Request, error: Exception):
        body = ErrorResponse(error_type=type(error).__name__, message=str(error), state=service.get_status().state)
        return JSONResponse(status_code=409, content=body.model_dump(mode="json"))

    @app.post("/recordings/start")
    def start(request: StartRequest):
        return once(request.request_id, lambda: service.start_recording(request.config))

    @app.post("/recordings/pause")
    def pause(request: ControlRequest):
        return once(request.request_id, service.pause_recording)

    @app.post("/recordings/resume")
    def resume(request: ControlRequest):
        return once(request.request_id, service.resume_recording)

    @app.post("/recordings/stop")
    def stop(request: ControlRequest):
        return once(request.request_id, service.stop_recording)

    @app.post("/recordings/cancel")
    def cancel(request: ControlRequest):
        return once(request.request_id, service.cancel_recording)

    @app.post("/recordings/save")
    def save(request: SaveRequest):
        return once(request.request_id, lambda: service.save_recording(request.output_path))

    @app.get("/recordings/status")
    def status():
        return service.get_status()

    @app.get("/displays")
    def displays():
        return service.enumerate_displays()

    return app


def main() -> None:
    """Start the optional server; default is loopback only."""
    parser = argparse.ArgumentParser(description="Run the local screen recorder HTTP API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    arguments = parser.parse_args()
    import uvicorn
    uvicorn.run(create_app(), host=arguments.host, port=arguments.port)
