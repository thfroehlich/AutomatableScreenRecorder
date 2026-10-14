from pathlib import Path

from automated_screen_recorder import RecordingConfig, ScreenRecorder

config = RecordingConfig(output_path=Path(r"C:\Recordings\example.mp4"), create_output_directory=True)
with ScreenRecorder() as recorder:
    custom = config.model_copy(update={"frame_rate": 15, "width": 1280, "height": 720})
    recorder.start_recording(custom)
    recorder.stop_recording()
    recorder.save_recording()
