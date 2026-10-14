# API reference

Import `ScreenRecorder`, `RecordingConfig`, enums, result/status/display models, and exceptions from `automated_screen_recorder`. The facade methods are `enumerate_displays()`, `start_recording(config)`, `pause_recording()`, `resume_recording()`, `stop_recording()`, `cancel_recording()`, `save_recording(output_path=None)`, and `get_status()`. Use the recorder as a context manager; exit cancels an unsaved session.
