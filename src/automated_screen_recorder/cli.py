"""Command-line interface for all recording modes."""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from automated_screen_recorder.models import RecordingConfig, RecordingMode
from automated_screen_recorder.service import ScreenRecorder


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record a Windows display without audio."
    )
    parser.add_argument("output", type=Path, help="Absolute or resolvable base path")
    parser.add_argument(
        "--mode",
        choices=[mode.value for mode in RecordingMode],
        default=RecordingMode.NORMAL.value,
    )
    parser.add_argument("--display", type=int, default=0)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--ffmpeg", type=Path)
    parser.add_argument(
        "--interval-seconds",
        type=float,
        help="Required in interval mode.",
    )
    parser.add_argument(
        "--buffer-seconds",
        type=float,
        default=60.0,
        help="Replay window in seconds. Default: 60.",
    )
    parser.add_argument(
        "--segment-seconds",
        type=float,
        default=2.0,
        help="Replay rotation granularity. Default: 2.",
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--create-output-directory", action="store_true")
    return parser


def _run_replay_console(recorder: ScreenRecorder) -> None:
    print(
        "Replay buffer active. Commands: save [PATH], status, pause, "
        "resume, quit, cancel"
    )
    while True:
        try:
            command = input("replay> ").strip()
        except (EOFError, KeyboardInterrupt):
            command = "quit"
        if not command:
            continue
        name, _, argument = command.partition(" ")
        if name == "save":
            destination = Path(argument).resolve() if argument else None
            result = recorder.save_replay_buffer(destination)
            print(result.model_dump_json(indent=2))
        elif name == "status":
            print(recorder.get_status().model_dump_json(indent=2))
        elif name == "pause":
            print(recorder.pause_recording().model_dump_json(indent=2))
        elif name == "resume":
            print(recorder.resume_recording().model_dump_json(indent=2))
        elif name == "cancel":
            print(recorder.cancel_recording().model_dump_json(indent=2))
            return
        elif name == "quit":
            recorder.stop_recording()
            result = recorder.save_recording()
            print(result.model_dump_json(indent=2))
            return
        else:
            print("Unknown command. Use save, status, pause, resume, quit, or cancel.")


def main() -> None:
    """Run the recorder until an explicit command or Ctrl+C."""
    arguments = _build_parser().parse_args()
    logging.basicConfig(level=logging.INFO)
    mode = RecordingMode(arguments.mode)
    config = RecordingConfig(
        output_path=arguments.output.resolve(),
        mode=mode,
        display_index=arguments.display,
        frame_rate=arguments.fps,
        ffmpeg_path=arguments.ffmpeg,
        interval_seconds=arguments.interval_seconds,
        replay_buffer_seconds=arguments.buffer_seconds,
        replay_segment_seconds=arguments.segment_seconds,
        overwrite=arguments.overwrite,
        create_output_directory=arguments.create_output_directory,
    )
    with ScreenRecorder() as recorder:
        recorder.start_recording(config)
        if mode is RecordingMode.REPLAY:
            _run_replay_console(recorder)
            return
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            recorder.stop_recording()
            result = recorder.save_recording()
            print(result.model_dump_json(indent=2))
