"""Command-line interface."""

import argparse
import logging
import time
from pathlib import Path

from automated_screen_recorder.models import RecordingConfig
from automated_screen_recorder.service import ScreenRecorder


def main() -> None:
    """Record until Ctrl+C, then save."""
    parser = argparse.ArgumentParser(
        description="Record a Windows display without audio."
    )
    parser.add_argument("output", type=Path)
    parser.add_argument("--display", type=int, default=0)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--ffmpeg", type=Path)
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    config = RecordingConfig(
        output_path=arguments.output.resolve(),
        display_index=arguments.display,
        ffmpeg_path=arguments.ffmpeg,
    )
    with ScreenRecorder() as recorder:
        recorder.start_recording(config)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            recorder.stop_recording()
            result = recorder.save_recording()
            print(result.model_dump_json(indent=2))
