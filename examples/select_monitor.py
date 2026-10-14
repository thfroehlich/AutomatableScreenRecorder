from pathlib import Path

from automated_screen_recorder import RecordingConfig, ScreenRecorder

config = RecordingConfig(
    output_path=Path(r"C:\Recordings\example.mp4"), create_output_directory=True
)
with ScreenRecorder() as recorder:
    displays = recorder.enumerate_displays()
    print(displays)
    recorder.start_recording(
        config.model_copy(update={"display_index": displays[-1].index})
    )
    recorder.stop_recording()
    recorder.save_recording()
