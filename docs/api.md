# API Reference

## Recording modes

```python
from automated_screen_recorder import RecordingMode

RecordingMode.NORMAL
RecordingMode.INTERVAL
RecordingMode.REPLAY
```

`NORMAL` records until explicitly stopped. `INTERVAL` persists numbered parts automatically. `REPLAY` maintains a rolling recent-history buffer and saves that buffer on demand.

## Configuration examples

### Normal

```python
RecordingConfig(
    output_path=Path(r"C:\Recordings\normal.mp4"),
    mode=RecordingMode.NORMAL,
)
```

### Interval

```python
RecordingConfig(
    output_path=Path(r"C:\Recordings\interval.mp4"),
    mode=RecordingMode.INTERVAL,
    interval_seconds=300,
)
```

### Replay

```python
RecordingConfig(
    output_path=Path(r"C:\Recordings\incident.mp4"),
    mode=RecordingMode.REPLAY,
    replay_buffer_seconds=60,
    replay_segment_seconds=2,
)
```

## `ScreenRecorder`

### Common lifecycle

```python
start_recording(config)
pause_recording()
resume_recording()
stop_recording()
save_recording(output_path=None)
cancel_recording()
get_status()
enumerate_displays()
```

### Replay save

```python
result = recorder.save_replay_buffer()
```

The method is valid only in replay mode and while the session is recording, paused, or stopped. During active recording, the current segment is finalized so that the saved replay includes recent data, then capture resumes in a fresh segment.

An explicit destination may be supplied:

```python
result = recorder.save_replay_buffer(Path(r"C:\Recordings\incident-42.mp4"))
```

## `RecordingStatus`

| Field | Meaning |
|---|---|
| `state` | Current lifecycle state |
| `mode` | Active recording mode |
| `elapsed_seconds` | Total active capture duration |
| `buffered_seconds` | Current replay window represented by temporary data |
| `saved_output_paths` | Outputs committed in this session |
| `next_rotation_in_seconds` | Best-effort countdown for interval/replay rotation |
| `error` | Last service failure message |

## `RecordingResult`

`RecordingResult.mode` identifies the mode that created the output. `output_path` is the most recently created file. `output_paths` contains all outputs committed in the session.

## Validation rules

- `interval_seconds` is required only in interval mode.
- `replay_segment_seconds` cannot exceed `replay_buffer_seconds`.
- Replay buffer range: 5 to 3600 seconds.
- Replay segment range: 0.5 to 30 seconds.
- Output paths must be absolute after caller resolution.
- Output suffix must match the configured container.

## REST model reuse

The REST API uses the same `RecordingConfig`, `RecordingStatus`, and `RecordingResult` models. State-changing requests include a bounded idempotency key.
