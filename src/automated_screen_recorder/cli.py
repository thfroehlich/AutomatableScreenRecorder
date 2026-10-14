"""Command-line interface."""

import argparse
import logging
import time
from pathlib import Path

from automated_screen_recorder.models import RecordingConfig
from automated_screen_recorder.service import ScreenRecorder


def main() -> None:
    """Record until Ctrl+C, then stop and save."""
    parser = argparse.ArgumentParser(
        description="Record a Windows display without audio."
    )
    parser.add_argument("output", type=Path)
    parser.add_argument("--display", type=int, default=0)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--ffmpeg", type=Path)
    parser.add_argument(
        "--save-interval",
        type=float,
        help=(
            "Save independently playable numbered video parts at this "
            "interval in seconds. Disabled when omitted."
        ),
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--create-output-directory", action="store_true")
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    config = RecordingConfig(
        output_path=arguments.output.resolve(),
        display_index=arguments.display,
        frame_rate=arguments.fps,
        ffmpeg_path=arguments.ffmpeg,
        save_interval_seconds=arguments.save_interval,
        overwrite=arguments.overwrite,
        create_output_directory=arguments.create_output_directory,
    )
    with ScreenRecorder() as recorder:
        recorder.start_recording(config)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            recorder.stop_recording()
            print(recorder.save_recording().model_dump_json(indent=2))
