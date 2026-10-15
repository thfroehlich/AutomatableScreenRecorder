"""Validated public models for recording modes and API payloads."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RecordingMode(StrEnum):
    """Supported recording strategies."""

    NORMAL = "normal"
    INTERVAL = "interval"
    REPLAY = "replay"


class RecordingState(StrEnum):
    """Lifecycle states for one recorder instance."""

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
    """Immutable recording configuration shared by CLI, API, and service."""

    model_config = ConfigDict(frozen=True)

    output_path: Path
    mode: RecordingMode = RecordingMode.NORMAL
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
    replay_buffer_seconds: float = Field(default=60.0, ge=5.0, le=3600.0)
    replay_segment_seconds: float = Field(default=2.0, ge=0.5, le=30.0)
    interval_seconds: float | None = Field(default=None, ge=0.1, le=86400.0)
    # Compatibility input for releases before the explicit mode model.
    # New code should use mode="interval" and interval_seconds.
    save_interval_seconds: float | None = Field(
        default=None,
        ge=0.1,
        le=86400.0,
        exclude=True,
        repr=False,
    )

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_interval_configuration(cls, value: Any) -> Any:
        """Map the former save_interval_seconds option to interval mode."""
        if not isinstance(value, dict):
            return value
        legacy_interval = value.get("save_interval_seconds")
        if legacy_interval is None:
            return value
        configured_interval = value.get("interval_seconds")
        if configured_interval is not None and configured_interval != legacy_interval:
            raise ValueError(
                "save_interval_seconds and interval_seconds must match when both are provided."
            )
        configured_mode = value.get("mode", RecordingMode.NORMAL)
        if configured_mode not in {
            RecordingMode.NORMAL,
            RecordingMode.INTERVAL,
            RecordingMode.NORMAL.value,
            RecordingMode.INTERVAL.value,
        }:
            raise ValueError(
                "save_interval_seconds cannot be combined with replay mode."
            )
        migrated = dict(value)
        migrated["mode"] = RecordingMode.INTERVAL
        migrated["interval_seconds"] = legacy_interval
        return migrated

    @field_validator("output_path")
    @classmethod
    def require_absolute_output(cls, value: Path) -> Path:
        """Require a deterministic absolute destination path."""
        if not value.is_absolute():
            raise ValueError("Output path must be absolute.")
        return value

    @model_validator(mode="after")
    def validate_mode_specific_settings(self) -> RecordingConfig:
        """Reject ambiguous combinations before any process starts."""
        if (self.width is None) != (self.height is None):
            raise ValueError("Width and height must be provided together.")
        if self.output_path.suffix.lower() != f".{self.output_format.value}":
            raise ValueError("Output path suffix must match output format.")
        if self.mode is RecordingMode.INTERVAL and self.interval_seconds is None:
            raise ValueError("Interval mode requires interval_seconds.")
        if (
            self.mode is not RecordingMode.INTERVAL
            and self.interval_seconds is not None
        ):
            raise ValueError("interval_seconds is only valid in interval mode.")
        if (
            self.mode is RecordingMode.REPLAY
            and self.replay_segment_seconds > self.replay_buffer_seconds
        ):
            raise ValueError(
                "replay_segment_seconds cannot exceed replay_buffer_seconds."
            )
        return self


class RecordingStatus(BaseModel):
    """Thread-safe recorder status snapshot."""

    session_id: str | None = None
    state: RecordingState = RecordingState.IDLE
    mode: RecordingMode | None = None
    started_at: str | None = None
    elapsed_seconds: float = Field(default=0.0, ge=0)
    buffered_seconds: float = Field(default=0.0, ge=0)
    saved_output_paths: list[Path] = Field(default_factory=list)
    next_rotation_in_seconds: float | None = Field(default=None, ge=0)
    backend: str | None = None
    error: str | None = None


class RecordingResult(BaseModel):
    """Result returned for normal, interval, or replay saves."""

    session_id: str
    mode: RecordingMode
    output_path: Path
    output_paths: list[Path]
    duration_seconds: float = Field(ge=0)
    file_size_bytes: int = Field(ge=0)
    total_file_size_bytes: int = Field(ge=0)
    codec: VideoCodec


class ErrorResponse(BaseModel):
    """Structured HTTP error response."""

    error_type: str
    message: str
    state: RecordingState


class StartRequest(BaseModel):
    """HTTP start request with an idempotency key."""

    request_id: str = Field(min_length=8, max_length=128)
    config: RecordingConfig


class ControlRequest(BaseModel):
    """HTTP state-changing request with an idempotency key."""

    request_id: str = Field(min_length=8, max_length=128)


class SaveRequest(ControlRequest):
    """HTTP final-save request."""

    output_path: Path | None = None


class SaveReplayRequest(ControlRequest):
    """HTTP replay-buffer save request."""

    output_path: Path | None = None
