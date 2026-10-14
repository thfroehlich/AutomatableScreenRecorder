# API reference

## Public facade

`ScreenRecorder` exposes:

- `enumerate_displays()`
- `start_recording(config)`
- `pause_recording()`
- `resume_recording()`
- `stop_recording()`
- `cancel_recording()`
- `save_recording(output_path=None)`
- `get_status()`

The facade is thread-safe. It accepts calls from Python threads and serializes backend and state changes with an `RLock`.

## Interval output configuration

```python
RecordingConfig(
    output_path=Path(r"C:\Recordings\capture.mkv"),
    save_interval_seconds=600.0,
)
```

`save_interval_seconds=None` disables interval output. Enabled interval output creates numbered paths by adding `.partNNNNNN` before the file suffix.

## Status fields

`RecordingStatus.saved_output_paths` contains files committed during interval rotation. `next_interval_save_in_seconds` is a best-effort countdown and is `None` when interval output is disabled, paused, stopped, cancelled, saved, or failed.

Frame counters are optional because the baseline FFmpeg process adapter does not expose reliable real-time counters.

## Save result

`RecordingResult.output_paths` contains all output files created by the session. In single-output mode it contains one path. In interval mode it includes every completed part, including the final partial part. `total_file_size_bytes` is the sum of their current sizes.

## Failure behavior

An interval rotation failure moves the recorder to `FAILED`, records the message in status, stops further rotation, and removes temporary artifacts. Files committed before the failure remain on disk. A new start resets a completed, cancelled, or failed session to `IDLE` before recording.
