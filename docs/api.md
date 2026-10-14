# API Reference

This document describes the stable public Python API of **Automated Screen Recorder**. Application code should import public models, exceptions, and `ScreenRecorder` from `automated_screen_recorder` rather than importing implementation modules directly.

## Quick import

```python
from automated_screen_recorder import (
    RecordingConfig,
    RecordingResult,
    RecordingState,
    RecordingStatus,
    ScreenRecorder,
)
```

## `ScreenRecorder`

`ScreenRecorder` is the thread-safe service facade for one recording session at a time.

### Lifecycle methods

```text
start_recording(config)
pause_recording()
resume_recording()
stop_recording()
cancel_recording()
save_recording(output_path=None)
get_status()
enumerate_displays()
```

Typical lifecycle:

```text
IDLE
  -> RECORDING
  -> PAUSED
  -> RECORDING
  -> STOPPED
  -> SAVED
```

Cancellation or a recording failure can terminate an active session before saving.

### Context-manager use

```python
from pathlib import Path

from automated_screen_recorder import RecordingConfig, ScreenRecorder

config = RecordingConfig(
    output_path=Path(r"C:\Recordings\capture.mp4"),
)

with ScreenRecorder() as recorder:
    recorder.start_recording(config)
    recorder.stop_recording()
    result = recorder.save_recording()

print(result.output_path)
```

Leaving the context manager with an unsaved active session triggers cleanup through cancellation semantics.

## Recording configuration

`RecordingConfig` is a Pydantic 2 model and validates configuration before capture starts.

Example:

```python
from pathlib import Path

from automated_screen_recorder import RecordingConfig

config = RecordingConfig(
    output_path=Path(r"C:\Recordings\capture.mp4"),
    display_index=0,
    frame_rate=30,
    width=1920,
    height=1080,
    create_output_directory=True,
)
```

Important settings include:

| Setting | Description |
|---|---|
| `output_path` | Absolute base output path |
| `display_index` | Display selected for recording |
| `frame_rate` | Requested capture rate |
| `width`, `height` | Optional paired output dimensions |
| `output_format` | Video container such as MP4 or MKV |
| `codec` | Configured FFmpeg video encoder |
| `overwrite` | Allows replacement of an existing destination |
| `create_output_directory` | Allows creation of a missing parent directory |
| `ffmpeg_path` | Explicit path to `ffmpeg.exe` |
| `encoder_preset` | Encoder preset forwarded to FFmpeg |
| `stop_timeout_seconds` | Graceful helper-process shutdown timeout |
| `save_interval_seconds` | Optional periodic output interval |

## Display enumeration

```python
from automated_screen_recorder import ScreenRecorder

with ScreenRecorder() as recorder:
    displays = recorder.enumerate_displays()

for display in displays:
    print(
        display.index,
        display.name,
        display.width,
        display.height,
        display.primary,
    )
```

Use the returned `index` as `RecordingConfig.display_index`.

## Pause and resume

```python
recorder.start_recording(config)
recorder.pause_recording()
recorder.resume_recording()
recorder.stop_recording()
result = recorder.save_recording()
```

Pause finalizes the currently active temporary capture segment. Resume starts another segment. Pending segments are assembled by the backend when a normal single-output recording is saved.

## Optional interval saving

Set `save_interval_seconds` to periodically persist independently playable numbered outputs.

```python
from pathlib import Path

from automated_screen_recorder import RecordingConfig

config = RecordingConfig(
    output_path=Path(r"C:\Recordings\capture.mp4"),
    save_interval_seconds=300.0,
)
```

With the base path above, interval outputs follow this pattern:

```text
capture.part000001.mp4
capture.part000002.mp4
capture.part000003.mp4
```

Set the field to `None`, or omit it, to disable interval saving.

### Interval lifecycle behavior

- The active segment is finalized at an interval boundary.
- The completed interval is committed to its numbered destination.
- Capture continues in a new segment.
- Pause suspends the interval deadline.
- Resume starts a new interval deadline.
- `stop_recording()` finalizes the current capture segment.
- `save_recording()` persists any remaining partial interval.
- Already committed interval files remain durable outputs if the remaining active recording is later cancelled.

## Status model

Retrieve status at any time:

```python
status = recorder.get_status()

print(status.state)
print(status.elapsed_seconds)
print(status.saved_output_paths)
print(status.next_interval_save_in_seconds)
```

Relevant fields include:

| Field | Meaning |
|---|---|
| `session_id` | Current session identifier |
| `state` | Current `RecordingState` |
| `started_at` | UTC session start timestamp |
| `elapsed_seconds` | Recorded active-session duration |
| `backend` | Active backend implementation name |
| `error` | Last actionable recording error, if present |
| `saved_output_paths` | Interval outputs committed so far |
| `next_interval_save_in_seconds` | Best-effort interval countdown |
| `captured_frames` | Captured-frame count when measurable |
| `dropped_frames` | Dropped-frame count when measurable |

The baseline backend does not invent frame counters. A measurement that is not available is represented as `None`.

## Save result

`save_recording()` returns `RecordingResult`.

```python
result = recorder.save_recording()

print(result.output_path)
print(result.output_paths)
print(result.file_size_bytes)
print(result.total_file_size_bytes)
print(result.duration_seconds)
```

In single-output mode, `output_paths` contains one path. In interval mode, the collection contains all committed outputs from the session, including the final partial part when one exists.

## Cancellation

```python
recorder.start_recording(config)
recorder.cancel_recording()
```

Cancellation terminates active capture and removes temporary artifacts. It does not remove interval files that were already successfully committed.

## State errors

Invalid lifecycle operations raise `InvalidStateTransitionError`.

```python
from automated_screen_recorder import (
    InvalidStateTransitionError,
    ScreenRecorder,
)

recorder = ScreenRecorder()

try:
    recorder.stop_recording()
except InvalidStateTransitionError as error:
    print(error)
```

## Recording failures

Recorder-specific failures derive from `RecorderError`. Callers can catch the base exception or a more specific subtype.

```python
from automated_screen_recorder import RecorderError, ScreenRecorder

recorder = ScreenRecorder()

try:
    recorder.start_recording(config)
except RecorderError as error:
    print(f"Recording operation failed: {error}")
```

Important error categories include invalid state transitions, unavailable displays, output-path failures, save failures, cancellation failures, and external-process failures.

## HTTP API model reuse

The optional HTTP adapter uses the same `RecordingConfig`, status, result, and display models as the Python API. Recording logic is not duplicated in the HTTP layer.

A start request can therefore include interval saving directly in the configuration:

```json
{
  "request_id": "recording-0001",
  "config": {
    "output_path": "C:\\Recordings\\capture.mp4",
    "save_interval_seconds": 300.0,
    "create_output_directory": true
  }
}
```

## Thread safety

Public lifecycle operations are serialized by the recorder service. Multiple active recordings cannot intentionally share one `ScreenRecorder` instance. The HTTP adapter adds operation-scoped idempotency protection for state-changing requests.

## Cleanup guarantees

Temporary artifacts are owned by the recording storage component and are cleaned after successful final saving, cancellation, and handled failures. Final output files are not treated as temporary data.
