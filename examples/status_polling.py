from pathlib import Path

from automated_screen_recorder import RecordingConfig, ScreenRecorder

config = RecordingConfig(output_path=Path(r"C:\Recordings\example.mp4"), create_output_directory=True)
with ScreenRecorder() as recorder:
    import time

    recorder.start_recording(config)
    for _ in range(3):
        print(recorder.get_status())
        time.sleep(1)
    recorder.stop_recording()
    recorder.save_recording()
