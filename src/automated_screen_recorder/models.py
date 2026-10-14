"""Validated public models."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import (BaseModel, ConfigDict, Field, field_validator, model_validator)


class RecordingState(StrEnum):
    """Lifecycle states for one recording session."""

    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"
    STOPPED = "stopped"
    SAVED = "saved"
    CANCELLED = "cancelled"
    FAILED = "failed"


class OutputFormat(StrEnum):
    """Supported output containers."""

    MP4 = "mp4"
    MKV = "mkv"


class VideoCodec(StrEnum):
    """Supported FFmpeg video encoders."""

    H264 = "libx264"
    H264_NVENC = "h264_nvenc"
    H264_QSV = "h264_qsv"


class DisplayInfo(BaseModel):
    """Windows display geometry."""

    model_config = ConfigDict(frozen=True)
    index: int = Field(ge=0)
    name: str
    left: int
    top: int
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    primary: bool = False


class RecordingConfig(BaseModel):
    """Validated recording configuration."""

    model_config = ConfigDict(frozen=True)
    output_path: Path
    display_index: int = Field(default=0, ge=0)
    frame_rate: int = Field(default=30, ge=1, le=120)
    width: int | None = Field(default=None, ge=16, le=16384)
    height: int | None = Field(default=None, ge=16, le=16384)
    output_format: OutputFormat = OutputFormat.MP4
    codec: VideoCodec = VideoCodec.H264
    overwrite: bool = False
    create_output_directory: bool = False
    ffmpeg_path: Path | None = None
    encoder_preset: str = "veryfast"
    stop_timeout_seconds: float = Field(default=10.0, gt=0, le=120)

    @field_validator("output_path")
    @classmethod
    def absolute_output(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError("Output path must be absolute.")
        return value

    @model_validator(mode="after")
    def validate_dimensions_and_suffix(self) -> RecordingConfig:
        if (self.width is None) != (self.height is None):
            raise ValueError("Width and height must be provided together.")
        if self.output_path.suffix.lower() != f".{self.output_format.value}":
            raise ValueError("Output path suffix must match output format.")
        return self


class RecordingStatus(BaseModel):
    """Thread-safe status snapshot."""

    session_id: str | None = None
    state: RecordingState = RecordingState.IDLE
    started_at: str | None = None
    elapsed_seconds: float = Field(default=0, ge=0)
    captured_frames: int = Field(default=0, ge=0)
    dropped_frames: int = Field(default=0, ge=0)
    backend: str | None = None
    error: str | None = None


class RecordingResult(BaseModel):
    """Result returned after save."""

    session_id: str
    output_path: Path
    duration_seconds: float = Field(ge=0)
    file_size_bytes: int = Field(ge=0)
    codec: VideoCodec


class ErrorResponse(BaseModel):
    """Structured HTTP error response."""

    error_type: str
    message: str
    state: RecordingState


class StartRequest(BaseModel):
    """HTTP start body with idempotency key."""

    request_id: str = Field(min_length=8, max_length=128)
    config: RecordingConfig


class ControlRequest(BaseModel):
    """HTTP state-change body with idempotency key."""

    request_id: str = Field(min_length=8, max_length=128)


class SaveRequest(ControlRequest):
    """HTTP save body."""

    output_path: Path | None = None
