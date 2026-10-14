from pathlib import Path

from automated_screen_recorder import RecordingConfig, ScreenRecorder

config = RecordingConfig(output_path=Path(r"C:\Recordings\example.mp4"), create_output_directory=True)
with ScreenRecorder() as recorder:
    from automated_screen_recorder.exceptions import RecorderError

    try:
        recorder.stop_recording()
    except RecorderError as error:
        print(f"Recorder error: {error}")
