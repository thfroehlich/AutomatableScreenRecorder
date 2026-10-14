# Architecture

This document describes the implementation boundaries and design decisions behind **Automated Screen Recorder**.

## Design goals

The architecture prioritizes:

- video-only Windows screen capture;
- predictable automation through a stable Python API;
- optional local HTTP control without duplicating business logic;
- bounded resource use;
- deterministic cleanup;
- replaceable capture and encoding boundaries for tests;
- local processing without telemetry or cloud dependencies.

## Component overview

```text
Python API / CLI / HTTP API
            |
            v
     ScreenRecorder
            |
    +-------+--------+
    |       |        |
    v       v        v
 State   Storage   CaptureProcess
Machine             protocol
                       |
                       v
                 FfmpegBackend
                       |
                       v
                    FFmpeg
                       |
                       v
                Windows desktop
```

The public facade owns lifecycle coordination. The state machine validates transitions. Storage owns temporary artifacts and final commits. The capture protocol isolates process-specific behavior. The Windows adapter isolates monitor enumeration.

## Public API boundary

External Python code should depend on the package-level public surface and `ScreenRecorder`, not on backend or storage implementation classes.

The service facade is responsible for:

- validating lifecycle state;
- selecting a display;
- coordinating capture segments;
- pause and resume behavior;
- optional interval rotation;
- stop, save, and cancellation behavior;
- status snapshots;
- deterministic cleanup on handled failures.

## State machine

The principal lifecycle is:

```text
IDLE
  -> RECORDING
  -> PAUSED
  -> RECORDING
  -> STOPPED
  -> SAVED
```

Additional terminal paths are available for cancellation and failure:

```text
RECORDING / PAUSED / STOPPED -> CANCELLED
RECORDING / PAUSED / STOPPED -> FAILED
```

A completed, cancelled, or failed session can be reset when a new recording begins.

Invalid lifecycle changes raise a dedicated state-transition exception before conflicting backend work is intentionally started.

## Windows capture boundary

Windows-specific monitor enumeration is isolated from the application service. The baseline recording backend uses FFmpeg with the Windows `gdigrab` desktop input.

The capture command is constructed as an argument list and executed with `shell=False`.

Audio is explicitly excluded from the FFmpeg pipeline. The backend does not configure an audio capture device.

## Encoding strategy

FFmpeg performs capture and video encoding directly. Python does not receive or retain normal video frame buffers.

Supported encoder selections are represented by configuration models. Hardware encoders depend on support from the local hardware, installed drivers, and selected FFmpeg build. The software H.264 encoder remains the compatibility-oriented fallback where supported by that FFmpeg distribution.

## FFmpeg process lifecycle

A capture segment uses one FFmpeg child process.

Process behavior is designed around these rules:

1. Process arguments are passed as a list.
2. `shell=False` is used.
3. Standard output is not consumed as a video transport.
4. FFmpeg diagnostic output is stored outside an unread pipe so stderr backpressure cannot accumulate indefinitely.
5. Stop first requests graceful FFmpeg finalization.
6. A configured timeout bounds helper shutdown.
7. Cancellation terminates the helper and escalates only when required by timeout handling.

## Segment model

Each active capture writes to a private temporary segment.

### Pause and resume

```text
start
  -> segment 1
pause
  -> finalize segment 1
resume
  -> segment 2
stop
  -> finalize segment 2
save
  -> assemble pending segments
  -> commit final output
```

This avoids reopening the same finalized video container as though FFmpeg could safely append arbitrary new recording data to it.

### Single-output saving

When interval saving is disabled, finalized segments remain temporary until `save_recording()` assembles them into the requested final output.

FFmpeg stream-copy concatenation is used when multiple compatible segments need to be combined without an unnecessary video re-encode.

## Optional interval saving

Interval saving is an opt-in durability feature controlled by `save_interval_seconds`.

A dedicated worker uses a monotonic deadline and a `threading.Event`. The worker does not poll at frame frequency.

At a recording interval boundary:

1. the active capture segment is gracefully finalized;
2. the completed segment is prepared for final storage;
3. storage creates a same-directory staging file;
4. the numbered destination is committed;
5. the committed temporary segment is removed;
6. a new capture segment starts;
7. the next monotonic deadline is scheduled.

Example output sequence:

```text
capture.part000001.mp4
capture.part000002.mp4
capture.part000003.mp4
```

### Durability semantics

An interval file becomes a durable session output after its commit succeeds. A later cancellation removes temporary artifacts but does not delete already committed parts.

The final partial interval is persisted by the normal stop-and-save lifecycle.

### Interval trade-off

Rotation requires FFmpeg finalization and process restart. This can create a short recording gap at the boundary. The design intentionally favors independently playable recovery files over a claim of seamless segment rotation.

## Concurrency model

The application service uses a reentrant lock to serialize lifecycle operations and interval rotation.

The interval worker uses the same service lock before mutating recorder state. Stop and cancellation signal and join the interval worker before proceeding with terminal lifecycle operations, reducing the risk of conflicting rotation and shutdown work.

The architecture does not use:

- unbounded capture queues;
- busy-wait frame loops;
- a Python frame accumulation buffer;
- independent duplicated recording logic in the HTTP adapter.

## HTTP adapter

The optional HTTP service is an adapter over `ScreenRecorder`.

It provides:

- Pydantic request and response bodies;
- structured recorder errors;
- localhost binding by default;
- operation-scoped idempotency keys for state-changing requests;
- a bounded idempotency-result cache.

Recorder state is still protected by the core service lock. The HTTP layer does not implement a second capture pipeline.

## Storage model

Temporary recording artifacts belong to a dedicated private session directory.

Final output creation follows a staging-and-commit approach in the destination directory. The overwrite policy is checked before final replacement or exclusive creation.

This separation has two goals:

- avoid treating partially written staging data as a completed recording;
- keep temporary cleanup independent from already committed final outputs.

## Path policy

Application paths use `pathlib.Path`.

The output layer validates:

- absolute output paths;
- output-directory existence;
- whether directory creation is explicitly allowed;
- overwrite policy;
- output suffix compatibility with the configured container.

## Failure model

Handled backend, display, interval, storage, and save failures preserve actionable exception context where possible.

A failure can transition the session to `FAILED`. Temporary session artifacts are cleaned where cleanup remains possible. If cleanup itself fails, that failure is logged rather than silently ignored.

Already committed final interval outputs are not temporary artifacts and are not removed as part of failure cleanup.

## Logging

The package uses Python's standard `logging` module.

Lifecycle logs include contextual fields such as:

- session ID;
- state;
- backend;
- operation.

The frame loop is owned by FFmpeg, and the Python layer does not emit per-frame log entries.

## Performance characteristics

The design minimizes Python-side overhead by keeping screen capture and encoding within FFmpeg.

Resource-use controls available to callers include:

- frame-rate reduction;
- resolution reduction;
- encoder selection;
- encoder preset selection;
- optional interval duration.

No fixed CPU, memory, latency, or frame-rate guarantees are claimed. Performance should be measured on the target Windows hardware and selected FFmpeg build.

## Security and privacy boundary

Normal recording is intended to remain local.

The core design excludes:

- microphone capture;
- camera capture;
- audio recording;
- telemetry;
- cloud upload;
- shell-command execution through `shell=True`.

The optional HTTP API is unauthenticated and intended for loopback automation. Deployments that intentionally expose it beyond localhost require protection outside this project.

## Testability

Capture and encoding behavior is represented behind a protocol so unit tests can use deterministic fake backends.

This allows tests for:

- lifecycle transitions;
- pause and resume segmentation;
- cancellation;
- interval output rotation;
- storage cleanup;
- overwrite handling;
- HTTP idempotency;
- backend failures;

without requiring a real Windows desktop.

Real desktop capture remains an explicitly opted-in integration test because hosted CI environments cannot be assumed to provide an interactive Windows desktop suitable for screen capture.

## Known limitations

- `gdigrab` is the compatibility baseline rather than a zero-copy Windows Graphics Capture implementation.
- Secure desktops and protected surfaces can prevent usable screen capture.
- Hardware encoders depend on the machine and FFmpeg build.
- Interval rotation introduces process-finalization and restart overhead.
- Individually committed interval files are separate outputs unless another workflow later combines them.
- Display topology can change while a recording is active; callers should treat disappearance of the selected display as a recording failure condition.
