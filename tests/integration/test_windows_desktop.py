import os
import sys
import time
from pathlib import Path

import pytest

from automated_screen_recorder import RecordingConfig, ScreenRecorder


@pytest.mark.windows_desktop
@pytest.mark.skipif(sys.platform != "win32" or os.getenv("AUTOSCREENREC_RUN_DESKTOP_TESTS") != "1",
                    reason="Requires an opted-in interactive Windows desktop and FFmpeg.")
def test_real_recording(tmp_path: Path):
    output = (tmp_path / "real.mp4").resolve()
    with ScreenRecorder() as recorder:
        recorder.start_recording(RecordingConfig(output_path=output))
        time.sleep(2)
        recorder.stop_recording()
        recorder.save_recording()
    assert output.stat().st_size > 0
