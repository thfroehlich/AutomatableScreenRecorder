from pathlib import Path

from automated_screen_recorder import RecordingConfig, ScreenRecorder

config = RecordingConfig(
    output_path=Path(r"C:\Recordings\example.mp4"), create_output_directory=True
)
with ScreenRecorder() as recorder:
    recorder.start_recording(config)
    recorder.stop_recording()
    print(recorder.save_recording())
