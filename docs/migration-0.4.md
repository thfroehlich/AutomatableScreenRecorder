# Migration to 0.4

## Configuration changes

The earlier optional interval field is replaced by an explicit mode model:

```python
RecordingConfig(
    mode=RecordingMode.INTERVAL,
    interval_seconds=300,
)
```

Normal mode is the default and rejects `interval_seconds`. Replay mode uses `replay_buffer_seconds` and `replay_segment_seconds`.

## New replay operation

Use `ScreenRecorder.save_replay_buffer()` or `POST /recordings/save-replay`. This operation does not stop an actively recording replay session.

## Status changes

Use `mode`, `buffered_seconds`, and `next_rotation_in_seconds` to distinguish mode-specific behavior.

## Naming

“Replay” and “replay buffer” are the public API terms. “Time travel” is not used as an enum value or endpoint term.
