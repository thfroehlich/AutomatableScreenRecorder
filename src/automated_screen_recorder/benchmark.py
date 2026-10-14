"""Measured benchmark utility without fabricated values."""

import argparse
import json
import time
from pathlib import Path

from automated_screen_recorder.models import RecordingConfig
from automated_screen_recorder.service import ScreenRecorder


def main() -> None:
    """Record for the requested duration and print observed metrics."""
    parser = argparse.ArgumentParser(description="Measure a real recording run.")
    parser.add_argument("output", type=Path)
    parser.add_argument("--duration", type=float, default=10.0)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--save-interval", type=float)
    arguments = parser.parse_args()
    if arguments.duration <= 0:
        parser.error("--duration must be greater than zero")
    config = RecordingConfig(
        output_path=arguments.output.resolve(),
        frame_rate=arguments.fps,
        save_interval_seconds=arguments.save_interval,
    )
    started = time.monotonic()
    with ScreenRecorder() as recorder:
        recorder.start_recording(config)
        time.sleep(arguments.duration)
        recorder.stop_recording()
        status = recorder.get_status()
        result = recorder.save_recording()
    wall_duration = time.monotonic() - started
    captured = status.captured_frames
    report = {
        "wall_duration_seconds": wall_duration,
        "recording_duration_seconds": result.duration_seconds,
        "requested_frame_rate": arguments.fps,
        "captured_frame_count": captured,
        "dropped_frame_count": status.dropped_frames,
        "average_achieved_frame_rate": (
            captured / result.duration_seconds
            if captured is not None and result.duration_seconds > 0
            else None
        ),
        "peak_process_memory_bytes": None,
        "output_file_size_bytes": result.total_file_size_bytes,
        "output_file_count": len(result.output_paths),
        "backend": status.backend,
    }
    print(json.dumps(report, indent=2))
