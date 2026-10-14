"""Optional localhost HTTP adapter."""

from __future__ import annotations

import argparse

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from automated_screen_recorder import RecorderError
from automated_screen_recorder.models import (
    ControlRequest,
    ErrorResponse,
    SaveRequest,
    StartRequest,
    RecordingStatus,
    DisplayInfo,
    RecordingResult,
)
from automated_screen_recorder.service import ScreenRecorder


def create_app(recorder: ScreenRecorder | None = None) -> FastAPI:
    """Create a FastAPI application without enabling a network listener."""
    service = recorder or ScreenRecorder()
    app = FastAPI(
        title="Automated Screen Recorder",
        version="0.2.0",
    )

    @app.get("/recordings/status")
    def status() -> RecordingStatus:
        return service.get_status()

    @app.get("/displays")
    def displays() -> list[DisplayInfo]:
        return service.enumerate_displays()

    @app.exception_handler(RecorderError)
    async def recorder_error_handler(
            _request: Request,
            error: RecorderError,
    ) -> JSONResponse:
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
        body = ErrorResponse(
            error_type="RequestValidationError",
            message="Request validation failed.",
            state=service.get_status().state,
        )

        return JSONResponse(
            status_code=422,
            content={
                **body.model_dump(mode="json"),
                "details": error.errors(),
            },
        )

    @app.post("/recordings/start")
    def start(request: StartRequest) -> RecordingStatus:
        return service.start_recording(request.config)

    @app.post("/recordings/pause")
    def pause(request: ControlRequest) -> RecordingStatus:
        return service.pause_recording()

    @app.post("/recordings/resume")
    def resume(request: ControlRequest) -> RecordingStatus:
        return service.resume_recording()

    @app.post("/recordings/stop")
    def stop(request: ControlRequest) -> RecordingStatus:
        return service.stop_recording()

    @app.post("/recordings/cancel")
    def cancel(request: ControlRequest) -> RecordingStatus:
        return service.cancel_recording()

    @app.post("/recordings/save")
    def save(request: SaveRequest) -> RecordingResult:
        return service.save_recording(request.output_path)

    return app


def main() -> None:
    """Start the optional server; default is loopback only."""
    parser = argparse.ArgumentParser(
        description="Run the local screen recorder HTTP API."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    arguments = parser.parse_args()
    import uvicorn

    uvicorn.run(create_app(), host=arguments.host, port=arguments.port)
