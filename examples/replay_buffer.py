"""Save the most recent replay window while capture continues."""

import time
from pathlib import Path

from automated_screen_recorder import RecordingConfig, RecordingMode, ScreenRecorder

config = RecordingConfig(
    output_path=Path(r"C:\Recordings\incident.mp4"),
    mode=RecordingMode.REPLAY,
    replay_buffer_seconds=60,
)

with ScreenRecorder() as recorder:
    recorder.start_recording(config)
    time.sleep(75)
    result = recorder.save_replay_buffer()
    print(result.output_path)
    recorder.cancel_recording()
