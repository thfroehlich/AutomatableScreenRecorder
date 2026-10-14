# Automated Screen Recorder

A local, video-only Windows 10/11 screen recorder for Python 3.11+. It never requests an audio, microphone, camera, telemetry, or cloud input.

## Features and non-goals

The package provides a thread-safe Python facade, explicit state machine, monitor selection, pause/resume, atomic save behavior, optional localhost FastAPI adapter, deterministic fake-backend tests, and Windows packaging. It is not a streamer, editor, audio recorder, or remote service.

## Architecture

`ScreenRecorder` serializes commands with an `RLock`. `FfmpegBackend` launches one argument-list subprocess with `shell=False`; FFmpeg `gdigrab` captures the chosen monitor rectangle and encodes directly, with `-an` guaranteeing no audio input or stream. Frames are not buffered in Python. Pause finalizes capture; resume starts capture again. This initial release uses one temporary output and therefore pause/resume support depends on the selected FFmpeg container accepting continuation. See `docs/architecture.md` for constraints.

## Installation

```powershell
py -3.11 -m pip install .
py -3.11 -m pip install ".[http]"
```

FFmpeg is required at runtime. Set `ffmpeg_path` explicitly, set `AUTOSCREENREC_FFMPEG`, place an executable at `tools/ffmpeg/bin/ffmpeg.exe`, or use PATH only as a final convenience fallback. The executable is validated with `ffmpeg -version`. The project does not silently download tools at runtime. A redistribution must follow the license of its exact FFmpeg build; FFmpeg is normally LGPL 2.1-or-later, while optional GPL components make the build GPL. If unavailable, start raises `ExternalProcessError` without creating a final file.

## Python API quick start and lifecycle

```python
from pathlib import Path
from automated_screen_recorder import RecordingConfig, ScreenRecorder

config = RecordingConfig(output_path=Path(r"C:\Recordings\demo.mp4"), create_output_directory=True)
with ScreenRecorder() as recorder:
    print(recorder.enumerate_displays())
    recorder.start_recording(config)
    recorder.pause_recording()
    recorder.resume_recording()
    recorder.stop_recording()
    result = recorder.save_recording()
    print(result)
```

Call `cancel_recording()` instead of stop/save to terminate the helper and delete temporary artifacts. `get_status()` is safe from another thread. Invalid transitions raise `InvalidStateTransitionError`; operational failures preserve the original exception as `__cause__`. Select a monitor with `display_index`, frame rate with `frame_rate`, and optional aspect-preserving letterboxed size with `width` plus `height`. Formats are MP4/MKV; codecs are software H.264, NVENC, and QSV where the installed FFmpeg build and hardware support them. `overwrite` defaults to false. Missing output directories are created only when `create_output_directory=True`.

## HTTP API

The server is optional and disabled until launched.

```powershell
autoscreenrec-http --host 127.0.0.1 --port 8765
```

POST `/recordings/start`, `/pause`, `/resume`, `/stop`, `/cancel`, and `/save`; GET `/recordings/status` and `/displays`. Every mutation requires a unique `request_id`; the bounded cache returns the first result for duplicates. FastAPI supplies OpenAPI at `/docs`. Binding beyond loopback is explicit and should be protected by OS controls because this adapter provides no authentication.

## Logging and performance

The library uses standard `logging` and never configures the root logger. Lifecycle entries include session, state, backend, and operation; no frame is logged. Lower FPS or resolution to reduce load. Python holds no frame queue because FFmpeg captures and encodes directly. Run `autoscreenrec-benchmark C:\Recordings\bench.mp4 --duration 30 --fps 30`; unavailable measurements are JSON `null`, never estimates.

## Configuration reference

`RecordingConfig`: absolute `output_path`; `display_index`; `frame_rate` 1..120; paired `width`/`height`; `output_format`; `codec`; `overwrite`; `create_output_directory`; optional `ffmpeg_path`; `encoder_preset`; and `stop_timeout_seconds`. Paths use `pathlib.Path`.

## Testing and builds

```powershell
py -m pip install -e ".[dev,http]"
ruff check .
ruff format --check .
mypy src
pytest
./scripts/build.ps1
```

Unit tests use no display. `windows_desktop` integration tests are skipped unless Windows, an interactive desktop, and `AUTOSCREENREC_RUN_DESKTOP_TESTS=1` are present. GitHub Actions checks Python 3.11-3.13 on Windows, coverage, distributions, wheel installation, and a PyInstaller executable artifact.

## Privacy, troubleshooting, and limitations

Normal operation is local and has no network call, telemetry, screenshot file, peripheral access, or audio. Screen recordings can contain sensitive visible data; users control destination retention. A black frame can indicate a secure desktop, DRM surface, minimized session, or capture restriction. Hardware codecs require matching drivers. Display geometry can change mid-session; stop/cancel and start a new session. Disk-full and encoder failures leave no final destination but can leave FFmpeg diagnostics in the raised cause. Pause/resume compatibility varies by container in this initial release; prefer MKV and validate it for production workloads. Exact performance depends on display, content, codec, and hardware, so benchmark locally.

## Packaging and license

`python -m build` creates wheel and sdist. `scripts/build.ps1` also runs PyInstaller. Project code is MIT. Dependencies retain their own licenses: Pydantic (MIT), FastAPI (MIT), Uvicorn (BSD-3-Clause), pytest (MIT), Ruff (MIT), mypy (MIT), and PyInstaller (GPL with its bootloader exception). FFmpeg is external and is not included by default. See `docs/architecture.md`, `CONTRIBUTING.md`, `SECURITY.md`, and `CHANGELOG.md`.
