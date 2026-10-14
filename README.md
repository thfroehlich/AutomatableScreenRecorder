# Automated Screen Recorder

A local, video-only screen recorder for Windows 10/11 and Python 3.11 or newer. The recorder is designed for automation, predictable lifecycle control, local processing, and low integration overhead.

> **Privacy by design:** normal recording captures screen pixels only. The project does not intentionally request microphone, camera, telemetry, cloud storage, or network services.

## Highlights

- Stable, thread-safe Python API
- Optional localhost HTTP API
- Primary or selected-display capture
- Configurable frame rate, resolution, container, and video codec
- Explicit start, pause, resume, stop, cancel, and save lifecycle
- Optional interval saving into independently playable numbered files
- Local FFmpeg capture and encoding with no audio stream
- Deterministic fake-backend tests plus opt-in Windows desktop integration tests

## Requirements

- Windows 10 or Windows 11
- Python 3.11 or newer
- FFmpeg available locally

## Installation

### Install the Python package

Core package:

```powershell
py -3.11 -m pip install .
```

With the optional local HTTP API:

```powershell
py -3.11 -m pip install ".[http]"
```

For development:

```powershell
py -3.11 -m pip install -e ".[dev,http]"
```

## Installing FFmpeg on Windows

FFmpeg itself publishes source code. The official FFmpeg download page links to third-party providers of ready-to-run Windows builds, including **gyan.dev** and **BtbN**. Always review the license of the exact build you redistribute. The recorder does not download FFmpeg during normal operation.

### Option A: Install with WinGet

The Windows builds page linked by FFmpeg documents WinGet packages. One documented option is the Essentials build:

```powershell
winget install "FFmpeg (Essentials Build)"
```

A full build is also listed:

```powershell
winget install ffmpeg
```

After installation, open a new terminal and verify:

```powershell
ffmpeg -version
```

### Option B: Install with Chocolatey

The same Windows builds provider documents:

```powershell
choco install ffmpeg
```

Then verify:

```powershell
ffmpeg -version
```

### Option C: Install with Scoop

A documented Essentials package is:

```powershell
scoop install ffmpeg-essentials
```

Then verify:

```powershell
ffmpeg -version
```

### Option D: Use a downloaded Windows build without modifying PATH

1. Open the official FFmpeg download page: `https://ffmpeg.org/download.html`.
2. Follow one of the linked Windows-build providers.
3. Download and extract the selected build.
4. Locate `ffmpeg.exe` inside the extracted `bin` directory.
5. Either configure its absolute path in Python or place the executable at the repository-local location `tools/ffmpeg/bin/ffmpeg.exe`.

Explicit configuration is the most deterministic approach:

```python
from pathlib import Path

from automated_screen_recorder import RecordingConfig

config = RecordingConfig(
    output_path=Path(r"C:\Recordings\demo.mp4"),
    ffmpeg_path=Path(r"C:\Tools\ffmpeg\bin\ffmpeg.exe"),
)
```

Alternatively, set the environment variable used by the recorder:

```powershell
$env:AUTOSCREENREC_FFMPEG = "C:\Tools\ffmpeg\bin\ffmpeg.exe"
```

### FFmpeg discovery order

The recorder searches for FFmpeg in this order:

1. `RecordingConfig.ffmpeg_path`
2. `AUTOSCREENREC_FFMPEG`
3. `tools/ffmpeg/bin/ffmpeg.exe`
4. the process `PATH`

The discovered executable is validated with:

```powershell
ffmpeg -version
```

If FFmpeg cannot be found or validated, recording startup fails instead of silently downloading another executable.

## Quick start

```python
from pathlib import Path

from automated_screen_recorder import RecordingConfig, ScreenRecorder

config = RecordingConfig(
    output_path=Path(r"C:\Recordings\demo.mp4"),
    create_output_directory=True,
)

with ScreenRecorder() as recorder:
    recorder.start_recording(config)
    recorder.pause_recording()
    recorder.resume_recording()
    recorder.stop_recording()
    result = recorder.save_recording()

print(result.output_path)
```

Pause finalizes the active temporary segment. Resume starts a new segment. Saving joins pending segments using the encoding backend without buffering captured frames in Python.

## Optional interval saving

Set `save_interval_seconds` to periodically commit independently playable numbered files. Leave the value as `None` to keep normal single-output behavior.

```python
from pathlib import Path
import time

from automated_screen_recorder import RecordingConfig, ScreenRecorder

config = RecordingConfig(
    output_path=Path(r"C:\Recordings\session.mp4"),
    save_interval_seconds=300.0,
    create_output_directory=True,
)

with ScreenRecorder() as recorder:
    recorder.start_recording(config)
    time.sleep(900)
    recorder.stop_recording()
    result = recorder.save_recording()

for output_path in result.output_paths:
    print(output_path)
```

Example output names:

```text
session.part000001.mp4
session.part000002.mp4
session.part000003.mp4
```

### Interval behavior

- Allowed interval: 0.1 through 86,400 seconds.
- Pause suspends interval timing; resume begins a new interval.
- Rotation finalizes the active segment, commits the completed file, and starts the next segment.
- `RecordingStatus.saved_output_paths` lists committed interval files.
- `RecordingStatus.next_interval_save_in_seconds` reports the current countdown while recording.
- `RecordingResult.output_paths` lists all committed outputs from the session.
- `RecordingResult.output_path` identifies the last committed output.
- Existing numbered files block the corresponding save unless `overwrite=True`.
- Already committed interval files remain on disk when a later recording is cancelled.

Interval boundaries include FFmpeg finalization and restart overhead. Benchmark the intended interval on the target Windows system before production use.

## CLI

### Single output

```powershell
autoscreenrec C:\Recordings\demo.mp4 --fps 30
```

### Five-minute interval outputs

```powershell
autoscreenrec C:\Recordings\demo.mp4 `
  --fps 30 `
  --save-interval 300 `
  --create-output-directory
```

Press `Ctrl+C` to stop capture and save remaining finalized data.

## Local HTTP API

The HTTP adapter is disabled until explicitly started and binds to loopback by default:

```powershell
autoscreenrec-http --host 127.0.0.1 --port 8765
```

Available operations:

- `POST /recordings/start`
- `POST /recordings/pause`
- `POST /recordings/resume`
- `POST /recordings/stop`
- `POST /recordings/cancel`
- `POST /recordings/save`
- `GET /recordings/status`
- `GET /displays`

`POST /recordings/start` accepts the complete `RecordingConfig`, including `save_interval_seconds`. State-changing requests use a `request_id` for duplicate-execution protection.

## Configuration reference

`RecordingConfig` includes:

| Setting | Purpose |
|---|---|
| `output_path` | Absolute base output path |
| `display_index` | Selected display index, default `0` |
| `frame_rate` | Requested frame rate, `1` through `120` |
| `width`, `height` | Optional paired output dimensions |
| `output_format` | `mp4` or `mkv` |
| `codec` | `libx264`, `h264_nvenc`, or `h264_qsv` |
| `overwrite` | Permit replacement of existing output targets |
| `create_output_directory` | Create a missing parent directory |
| `ffmpeg_path` | Explicit local FFmpeg executable |
| `encoder_preset` | FFmpeg encoder preset |
| `stop_timeout_seconds` | Graceful helper-process shutdown timeout |
| `save_interval_seconds` | Optional interval-output rotation |

## Display enumeration

```python
from automated_screen_recorder import ScreenRecorder

with ScreenRecorder() as recorder:
    for display in recorder.enumerate_displays():
        print(display)
```

Choose another monitor with `display_index` in `RecordingConfig`.

## Logging

The package uses the standard `logging` module and does not configure the root logger on import.

Example application configuration:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
```

Lifecycle log context includes session ID, recording state, backend, and operation. Interval commits use operation `interval_save`. No per-frame logging is performed.

## Performance and reliability

FFmpeg handles capture and encoding directly, so Python does not store video frames in a queue. The interval worker waits on an event instead of busy-waiting.

Ways to reduce resource use:

- lower `frame_rate`;
- reduce `width` and `height`;
- select a suitable encoder and preset;
- use interval saving only when periodic durable output is required;
- benchmark on the intended hardware before choosing production settings.

Benchmark examples:

```powershell
autoscreenrec-benchmark C:\Recordings\bench.mp4 --duration 30 --fps 30
```

```powershell
autoscreenrec-benchmark C:\Recordings\bench.mp4 `
  --duration 300 `
  --save-interval 60
```

Unavailable measurements are represented as JSON `null`, not invented values.

## Privacy and security

- Normal recording processing is local.
- Capture uses screen content only.
- FFmpeg capture and concatenation are configured without audio output.
- External commands use argument lists rather than `shell=True`.
- The optional HTTP adapter is intended for localhost by default.
- Recordings can contain sensitive visible information; callers are responsible for destination permissions and retention.

## Testing

Install development dependencies:

```powershell
py -m pip install -e ".[dev,http]"
```

Run the checks used by CI:

```powershell
python -m ruff check . --ignore E501,I001
python -m ruff format --check .
python -m mypy src
python -m pytest --cov=automated_screen_recorder
```

The real capture integration test requires Windows, an interactive desktop, FFmpeg, and:

```powershell
$env:AUTOSCREENREC_RUN_DESKTOP_TESTS = "1"
```

Normal unit tests use fake backends and do not require physical peripherals.

## Building and packaging

Local build:

```powershell
.\scripts\build.ps1
```

Python distributions:

```powershell
python -m build
python -m twine check dist\*
```

GitHub Actions also validates supported Python versions, coverage, package metadata, wheel installation, and the standalone Windows executable.

### FFmpeg troubleshooting on Windows

If the recorder reports that FFmpeg cannot be found or started, check the installation before changing recorder code.

#### `ffmpeg` is not recognized

In PowerShell, check whether Windows can resolve the executable:

```powershell
Get-Command ffmpeg -All -ErrorAction SilentlyContinue
where.exe ffmpeg
```

If both commands return nothing, either configure `RecordingConfig.ffmpeg_path`, set `AUTOSCREENREC_FFMPEG`, or add the directory containing `ffmpeg.exe` to `PATH`.

After changing `PATH`, close the terminal, open a new PowerShell window, and verify:

```powershell
ffmpeg -version
```

#### FFmpeg exists but the recorder still cannot find it

Use an explicit executable path to remove PATH ambiguity:

```python
from pathlib import Path

config = RecordingConfig(
    output_path=Path(r"C:\Recordings\demo.mp4"),
    ffmpeg_path=Path(r"C:\Tools\ffmpeg\bin\ffmpeg.exe"),
)
```

Or set the environment variable before starting the recorder:

```powershell
$env:AUTOSCREENREC_FFMPEG = "C:\Tools\ffmpeg\bin\ffmpeg.exe"
```

#### Multiple FFmpeg installations are present

List every matching executable:

```powershell
Get-Command ffmpeg -All
where.exe ffmpeg
```

Then configure the intended `ffmpeg.exe` explicitly with `ffmpeg_path` instead of relying on PATH order.

#### A configured hardware encoder fails

Confirm which encoders are available in the selected FFmpeg build:

```powershell
ffmpeg -hide_banner -encoders
```

If a hardware-specific encoder is unavailable or fails to initialize, test the software H.264 configuration first and verify the machine's graphics driver and FFmpeg build separately.

#### Capture starts but the result is black or unavailable

Test from an ordinary interactive Windows desktop session. Secure desktops, protected content, and disconnected sessions may not be capturable through the selected desktop-capture backend.

## Troubleshooting

### FFmpeg was not found

Verify the executable:

```powershell
ffmpeg -version
```

If FFmpeg is intentionally not on `PATH`, configure `ffmpeg_path` or `AUTOSCREENREC_FFMPEG`.

### Hardware encoder fails

Try `libx264` first. Hardware encoders depend on the installed hardware, drivers, and the capabilities of the selected FFmpeg build.

### Black or unavailable capture

Secure desktops, protected content, disconnected sessions, and other Windows capture restrictions can prevent normal desktop capture.

### Existing output file

The recorder does not overwrite recordings by default. Choose another target or explicitly configure `overwrite=True`.

## Known limitations

- Secure desktop, DRM-protected surfaces, and disconnected sessions can prevent usable capture.
- Hardware codecs require compatible hardware, drivers, and FFmpeg support.
- An interval boundary can contain a short capture gap while FFmpeg finalizes and restarts.
- Interval outputs are separate files; they are not automatically turned into one continuous final file.
- File duration can vary slightly around an interval boundary because process finalization and scheduling are not real-time operations.

## Licensing

Project code is MIT. FFmpeg is external and retains the license of the exact build used. Review the selected FFmpeg build before redistribution. PyInstaller and all Python dependencies retain their respective licenses.

## Further documentation

- `docs/api.md`
- `docs/architecture.md`
- `CONTRIBUTING.md`
- `SECURITY.md`
- `CHANGELOG.md`
