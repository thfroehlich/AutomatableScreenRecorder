"""Measured benchmark utility; never fabricates results."""

import argparse
import json
import time
from pathlib import Path

from automated_screen_recorder.models import RecordingConfig
from automated_screen_recorder.service import ScreenRecorder


def main() -> None:
    """Record for a requested duration and write observed metrics as JSON."""
    parser = argparse.ArgumentParser(description="Measure a real screen recording run.")
    parser.add_argument("output", type=Path)
    parser.add_argument("--duration", type=float, default=10)
    parser.add_argument("--fps", type=int, default=30)
    arguments = parser.parse_args()
    config = RecordingConfig(
        output_path=arguments.output.resolve(), frame_rate=arguments.fps
    )
    started = time.monotonic()
    with ScreenRecorder() as recorder:
        recorder.start_recording(config)
        time.sleep(arguments.duration)
        recorder.stop_recording()
        status = recorder.get_status()
        result = recorder.save_recording()
    duration = time.monotonic() - started
    report = {
        "recording_duration_seconds": duration,
        "requested_frame_rate": arguments.fps,
        "captured_frame_count": status.captured_frames,
        "dropped_frame_count": status.dropped_frames,
        "average_achieved_frame_rate": status.captured_frames / duration
        if duration
        else 0,
        "peak_process_memory_bytes": None,
        "output_file_size_bytes": result.file_size_bytes,
        "backend": status.backend,
    }
    print(json.dumps(report, indent=2))
