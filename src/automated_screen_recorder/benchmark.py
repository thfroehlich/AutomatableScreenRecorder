"""Measured benchmark utility without synthetic performance claims."""

import argparse
import json
import time
from pathlib import Path

from automated_screen_recorder.models import RecordingConfig, RecordingMode
from automated_screen_recorder.service import ScreenRecorder


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure a real recording run.")
    parser.add_argument("output", type=Path)
    parser.add_argument("--duration", type=float, default=10.0)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument(
        "--mode",
        choices=[mode.value for mode in RecordingMode],
        default="normal",
    )
    parser.add_argument("--interval-seconds", type=float)
    parser.add_argument("--buffer-seconds", type=float, default=60.0)
    arguments = parser.parse_args()
    config = RecordingConfig(
        output_path=arguments.output.resolve(),
        mode=RecordingMode(arguments.mode),
        frame_rate=arguments.fps,
        interval_seconds=arguments.interval_seconds,
        replay_buffer_seconds=arguments.buffer_seconds,
    )
    started = time.monotonic()
    with ScreenRecorder() as recorder:
        recorder.start_recording(config)
        time.sleep(arguments.duration)
        recorder.stop_recording()
        result = recorder.save_recording()
        status = recorder.get_status()
    report = {
        "wall_duration_seconds": time.monotonic() - started,
        "recording_duration_seconds": result.duration_seconds,
        "mode": result.mode,
        "buffered_seconds": status.buffered_seconds,
        "output_file_count": len(result.output_paths),
        "total_file_size_bytes": result.total_file_size_bytes,
        "backend": status.backend,
    }
    print(json.dumps(report, indent=2, default=str))
