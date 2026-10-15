# Architecture

## Overview

```text
CLI / Python / REST
        |
        v
  ScreenRecorder
        |
  +-----+---------+
  |     |         |
State Storage  CaptureProcess
                  |
             FfmpegBackend
```

All modes share the same service, storage, state machine, and backend boundaries.

## Mode strategies

### Normal

Normal mode starts one segment, plus additional segments created by pause/resume. On final save, compatible segments are concatenated and committed to one destination. No rotation thread runs.

### Interval

Interval mode runs a rotation worker. At each deadline, the active segment is finalized and committed as a numbered file. A fresh segment then starts. The final partial interval is saved after stop.

### Replay

Replay mode, also known as a replay buffer, continuously rotates short temporary segments. The service deletes the oldest finalized segments when their retention is no longer required for the configured recent-history window.

```text
oldest                                        newest
  [deleted] [segment N-2] [segment N-1] [active segment]
             <------ configured window ------>
```

When `save_replay_buffer()` is invoked:

1. the current segment is finalized;
2. the retained segment snapshot is selected;
3. FFmpeg concatenates the snapshot and trims it to the configured tail duration;
4. storage commits the final output;
5. recording resumes in a fresh segment when the session was active.

## Bounded storage

Replay uses file segments, not an in-memory frame queue. The retained temporary duration is bounded to approximately:

```text
replay_buffer_seconds + replay_segment_seconds
```

The additional segment is the granularity required to avoid discarding data that still overlaps the requested window. The saved output is requested with a tail duration equal to `replay_buffer_seconds`.

## Timing

Scheduling uses `time.monotonic()`. Wall-clock changes therefore do not directly shift segment deadlines. Exact video duration can still vary because process finalization, scheduling, codec keyframes, and stream-copy trimming are not real-time or frame-exact operations.

## Concurrency

A reentrant lock serializes lifecycle operations and rotation. The worker is signaled and joined before terminal stop/cancel operations. REST idempotency is scoped by operation name and request ID.

## Failure semantics

A rotation or backend failure transitions the session to `FAILED`, records an actionable error string, and stops further rotation. Temporary artifacts are cleaned where possible. Already committed normal, interval, or replay outputs are not deleted as temporary data.

## Capture gaps

Pause/resume, interval rotation, and replay saving require FFmpeg finalization and restart. These operations can create short gaps. A future backend could reduce gaps by using FFmpeg-native segment muxing or Windows Graphics Capture, but such a backend is not implemented here.

## Security boundary

Capture and concatenation use argument lists with `shell=False`; audio is disabled. The optional REST adapter remains local by default and has no built-in authentication.
