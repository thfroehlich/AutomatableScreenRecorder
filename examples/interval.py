"""Write five-minute recording parts."""

import time
from pathlib import Path

from automated_screen_recorder import RecordingConfig, RecordingMode, ScreenRecorder

config = RecordingConfig(
    output_path=Path(r"C:\Recordings\shift.mp4"),
    mode=RecordingMode.INTERVAL,
    interval_seconds=300,
)

with ScreenRecorder() as recorder:
    recorder.start_recording(config)
    time.sleep(900)
    recorder.stop_recording()
    print(recorder.save_recording().model_dump_json(indent=2))
