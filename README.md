# Automatable Screen Recorder

Local, video-only Windows screen recording for Python 3.11 or newer. The recorder supports three explicit operating modes and can be controlled through Python, an interactive CLI, or an optional localhost REST API.


## Recording modes

| Mode | Use case | Save behavior |
|---|---|---|
| `normal` | One manually controlled recording | Start, optionally pause/resume, stop, then save one file |
| `interval` | Long-running recording with durable parts | Save numbered files automatically at the configured interval |
| `replay` | Retrospective incident capture | Keep a rolling window, 60 seconds by default, and save the recent past on demand |

## Installation

### Install the Python package

Core package:

```powershell
py -3.11 -m pip install .
```

With the optional REST API:

```powershell
py -3.11 -m pip install ".[http]"
```

For development:

```powershell
py -3.11 -m pip install -e ".[dev,http]"
```

FFmpeg is required at runtime. Configure `ffmpeg_path`, set `AUTOSCREENREC_FFMPEG`, place `ffmpeg.exe` at `tools/ffmpeg/bin/ffmpeg.exe`, or make it available through `PATH`.


### Installing FFmpeg on Windows

FFmpeg itself publishes source code. The official FFmpeg download page links to third-party providers of ready-to-run Windows builds, including **gyan.dev** and **BtbN**. Always review the license of the exact build you redistribute. The recorder does not download FFmpeg during normal operation.

#### Option A: Install with WinGet

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

#### Option B: Install with Chocolatey

The same Windows builds provider documents:

```powershell
choco install ffmpeg
```

Then verify:

```powershell
ffmpeg -version
```

#### Option C: Install with Scoop

A documented Essentials package is:

```powershell
scoop install ffmpeg-essentials
```

Then verify:

```powershell
ffmpeg -version
```

#### Option D: Use a downloaded Windows build without modifying PATH

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

#### FFmpeg discovery order

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


## Normal mode

```python
from pathlib import Path

from automated_screen_recorder import RecordingConfig, RecordingMode, ScreenRecorder

config = RecordingConfig(
    output_path=Path(r"C:\Recordings\normal.mp4"),
    mode=RecordingMode.NORMAL,
)

with ScreenRecorder() as recorder:
    recorder.start_recording(config)
    recorder.stop_recording()
    result = recorder.save_recording()
```

CLI:

```powershell
autoscreenrec C:\Recordings\normal.mp4 --mode normal
```

Press `Ctrl+C` to stop and save.

## Interval mode

```python
config = RecordingConfig(
    output_path=Path(r"C:\Recordings\shift.mp4"),
    mode=RecordingMode.INTERVAL,
    interval_seconds=300,
)
```

Output names:

```text
shift.part000001.mp4
shift.part000002.mp4
shift.part000003.mp4
```

CLI:

```powershell
autoscreenrec C:\Recordings\shift.mp4 `
  --mode interval `
  --interval-seconds 300
```

## Replay mode

Replay mode continuously captures short temporary segments. Old segments are deleted as the configured window advances. The default replay window is 60 seconds.

```python
config = RecordingConfig(
    output_path=Path(r"C:\Recordings\incident.mp4"),
    mode=RecordingMode.REPLAY,
    replay_buffer_seconds=60,
    replay_segment_seconds=2,
)

with ScreenRecorder() as recorder:
    recorder.start_recording(config)

    # Called when something worth retaining just happened.
    result = recorder.save_replay_buffer()
    print(result.output_path)

    # Capture continues after the save.
    recorder.cancel_recording()
```

Default output names are numbered so repeated saves do not overwrite each other:

```text
incident.replay000001.mp4
incident.replay000002.mp4
```

### Buffer accuracy

Replay data is rotated in short segments. The temporary on-disk buffer may exceed the requested replay window by at most approximately one configured segment. When a replay is saved, FFmpeg is asked to retain only the configured tail duration. Stream-copy trimming can begin on a nearby keyframe, so exact frame-level duration is not guaranteed.

Smaller `replay_segment_seconds` values reduce timing granularity but increase process finalization and restart overhead. The default is 2 seconds.

### Interactive replay CLI

```powershell
autoscreenrec C:\Recordings\incident.mp4 `
  --mode replay `
  --buffer-seconds 60 `
  --segment-seconds 2
```

The process then accepts:

```text
save
save C:\Recordings\custom-incident.mp4
status
pause
resume
quit
cancel
```

- `save` writes the current replay window and continues buffering.
- `quit` stops and saves the remaining replay window.
- `cancel` stops and removes temporary data. Previously committed replay outputs remain.

## REST API

Start the local API:

```powershell
autoscreenrec-http --host 127.0.0.1 --port 8765
```

Start replay mode:

```powershell
$Body = @{
  request_id = "start-replay-0001"
  config = @{
    output_path = "C:\Recordings\incident.mp4"
    mode = "replay"
    replay_buffer_seconds = 60
    replay_segment_seconds = 2
    create_output_directory = $true
  }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8765/recordings/start" `
  -ContentType "application/json" `
  -Body $Body
```

Save the recent replay window without stopping:

```powershell
$Body = @{
  request_id = "save-replay-0001"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8765/recordings/save-replay" `
  -ContentType "application/json" `
  -Body $Body
```

## REST endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/recordings/start` | Start any configured mode |
| `POST` | `/recordings/pause` | Pause active capture |
| `POST` | `/recordings/resume` | Resume capture |
| `POST` | `/recordings/stop` | Stop capture |
| `POST` | `/recordings/save` | Save a stopped session |
| `POST` | `/recordings/save-replay` | Save the current replay window and continue |
| `POST` | `/recordings/cancel` | Cancel and clean temporary artifacts |
| `GET` | `/recordings/status` | Return state, mode, buffer duration, and outputs |
| `GET` | `/displays` | Enumerate displays |
| `GET` | `/docs` | Swagger API Doc |
| `GET` | `/redoc` | ReDoc API Doc |

## Configuration reference

| Setting | Default | Meaning |
|---|---:|---|
| `mode` | `normal` | `normal`, `interval`, or `replay` |
| `interval_seconds` | `None` | Required only in interval mode |
| `replay_buffer_seconds` | `60` | Retrospective window, 5 to 3600 seconds |
| `replay_segment_seconds` | `2` | Replay rotation granularity, 0.5 to 30 seconds |
| `frame_rate` | `30` | Requested capture rate, 1 to 120 |
| `display_index` | `0` | Selected monitor |
| `overwrite` | `False` | Allow destination replacement |
| `create_output_directory` | `False` | Create a missing output parent |
| `stop_timeout_seconds` | `10` | Graceful FFmpeg stop timeout |

## Status fields

Replay-aware status adds:

- `mode`
- `buffered_seconds`
- `saved_output_paths`
- `next_rotation_in_seconds`

## Reliability and performance

- Python does not buffer video frames.
- FFmpeg owns capture and encoding.
- Normal mode does not run a rotation worker.
- Interval and replay modes rotate finalized segments on a monotonic schedule.
- Replay mode keeps a bounded set of temporary files instead of unbounded video history.
- Saving a replay finalizes the current segment, writes the snapshot, and starts another segment. This introduces a short capture gap.
- All final destinations use staging and commit behavior to avoid presenting a partially copied file as complete.

## Privacy and security

Normal processing remains local. Capture commands explicitly disable audio with `-an`. The REST API is unauthenticated and defaults to loopback. Do not expose it directly to an untrusted network.

## Testing

```powershell
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest --cov=automated_screen_recorder
```

Unit tests use a deterministic fake backend. Real Windows capture still requires an interactive desktop and FFmpeg.

## Known limitations

- Replay saves use stream-copy trimming and are therefore keyframe-aligned rather than guaranteed frame-exact.
- Segment rotation and on-demand replay saving introduce a brief capture gap.
- Secure desktops, protected surfaces, and disconnected sessions can prevent usable capture.
- Hardware encoders depend on the machine, driver, and FFmpeg build.
