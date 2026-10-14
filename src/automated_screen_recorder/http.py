"""Optional local HTTP API adapter."""

from __future__ import annotations

import argparse
import threading
from collections import OrderedDict
from collections.abc import Callable
from typing import TypeVar, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .exceptions import RecorderError
from .models import (
    ControlRequest,
    DisplayInfo,
    ErrorResponse,
    RecordingResult,
    RecordingStatus,
    SaveRequest,
    StartRequest,
)
from .service import ScreenRecorder

ResultType = TypeVar("ResultType")
IdempotencyKey = tuple[str, str]


def create_app(
    recorder: ScreenRecorder | None = None,
) -> FastAPI:
    """Create the optional local HTTP application."""
    service = recorder or ScreenRecorder()

    app = FastAPI(
        title="Automated Screen Recorder",
        version="0.2.0",
    )

    cache_lock = threading.RLock()

    cache: OrderedDict[
        IdempotencyKey,
        object,
    ] = OrderedDict()

    def execute_once(
        operation_name: str,
        request_id: str,
        operation: Callable[[], ResultType],
    ) -> ResultType:
        """Execute a state-changing request once."""
        key = (
            operation_name,
            request_id,
        )

        with cache_lock:
            if key in cache:
                return cast(
                    ResultType,
                    cache[key],
                )

            result = operation()

            cache[key] = result

            while len(cache) > 256:
                cache.popitem(last=False)

            return result

    @app.exception_handler(RecorderError)
    async def recorder_error_handler(
        _request: Request,
        error: RecorderError,
    ) -> JSONResponse:
        """Return recorder failures as structured JSON."""
        body = ErrorResponse(
            error_type=type(error).__name__,
            message=str(error),
            state=service.get_status().state,
        )

        return JSONResponse(
            status_code=409,
            content=body.model_dump(mode="json"),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        """Return request validation failures as JSON."""
        body = ErrorResponse(
            error_type="RequestValidationError",
            message="Request validation failed.",
            state=service.get_status().state,
        )

        content = body.model_dump(mode="json")

        content["details"] = error.errors()

        return JSONResponse(
            status_code=422,
            content=content,
        )

    @app.post(
        "/recordings/start",
        response_model=RecordingStatus,
    )
    def start(
            request: StartRequest,
    ) -> RecordingStatus:
        """Start a recording once per request identifier."""
        return execute_once(
            "start",
            request.request_id,
            lambda: service.start_recording(request.config),
        )

    @app.post(
        "/recordings/pause",
        response_model=RecordingStatus,
    )
    def pause(
            request: ControlRequest,
    ) -> RecordingStatus:
        """Pause the active recording."""
        return execute_once(
            "pause",
            request.request_id,
            service.pause_recording,
        )

    @app.post(
        "/recordings/resume",
        response_model=RecordingStatus,
    )
    def resume(
            request: ControlRequest,
    ) -> RecordingStatus:
        """Resume the paused recording."""
        return execute_once(
            "resume",
            request.request_id,
            service.resume_recording,
        )

    @app.post(
        "/recordings/stop",
        response_model=RecordingStatus,
    )
    def stop(
        request: ControlRequest,
    ) -> RecordingStatus:
        """Stop the active recording."""
        return execute_once(
            "stop",
            request.request_id,
            service.stop_recording,
        )

    @app.post(
        "/recordings/cancel",
        response_model=RecordingStatus,
    )
    def cancel(
        request: ControlRequest,
    ) -> RecordingStatus:
        """Cancel the current recording."""
        return execute_once(
            "cancel",
            request.request_id,
            service.cancel_recording,
        )

    @app.post(
        "/recordings/save",
        response_model=RecordingResult,
    )
    def save(
        request: SaveRequest,
    ) -> RecordingResult:
        """Save a stopped recording."""
        return execute_once(
            "save",
            request.request_id,
            lambda: service.save_recording(request.output_path),
        )

    @app.get(
        "/recordings/status",
        response_model=RecordingStatus,
    )
    def status() -> RecordingStatus:
        """Return current recorder status."""
        return service.get_status()

    @app.get(
        "/displays",
        response_model=list[DisplayInfo],
    )
    def displays() -> list[DisplayInfo]:
        """Return available displays."""
        return service.enumerate_displays()

    return app


def main() -> None:
    """Start the optional local HTTP API."""
    parser = argparse.ArgumentParser(
        description="Run the local screen recorder HTTP API."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    arguments = parser.parse_args()

    import uvicorn

    uvicorn.run(create_app(), host=arguments.host, port=arguments.port)
