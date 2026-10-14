# Architecture

## Component boundaries

The public facade owns lifecycle coordination. A state machine validates transitions, a capture protocol isolates FFmpeg, a storage component owns temporary artifacts and atomic commits, and the Windows adapter isolates monitor enumeration. The optional HTTP adapter calls the same facade.

## Capture and encoding

FFmpeg `gdigrab` captures the selected monitor rectangle and encodes video in one process. `-an` is used for capture and concatenation. Python never receives frame buffers. FFmpeg diagnostics are written to a temporary file instead of an unread pipe, preventing stderr backpressure from blocking long recordings.

## Segment model

Every active capture writes one private segment. Pause and interval rotation finalize the current segment. Resume and post-rotation continuation start a new segment. In normal mode, pending segments are concatenated with FFmpeg stream copy before the final atomic commit.

## Interval saving

Interval output is optional and implemented by one daemon worker per active recorder instance. The worker waits on `threading.Event`, reads a monotonic deadline, and acquires the same service lock used by public control calls. At a deadline it:

1. gracefully finalizes the active FFmpeg segment;
2. copies the finalized segment to a same-directory staging file;
3. atomically commits the numbered destination;
4. removes the committed temporary segment;
5. starts the next capture segment;
6. schedules the next monotonic deadline.

The design has bounded memory use and no polling loop at frame-level frequency. Rotation necessarily introduces a short capture gap. The implementation favors independently playable recovery files over seamless single-file continuity.

## Concurrency

Public operations and interval rotation are serialized by an `RLock`. The interval worker is stopped and joined before stop or cancel acquires the service lock, avoiding lock inversion. The join uses the configured helper timeout. Concurrent HTTP mutations additionally pass through a bounded operation-scoped idempotency cache.

## Storage guarantees

Final files are copied into a temporary staging file in the destination directory. Commit uses atomic replacement when overwrite is allowed and an exclusive hard-link operation when overwrite is forbidden. Failure removes staging data and does not intentionally leave a partial final destination.

Already committed interval files are durable session outputs. Cancellation removes temporary segments but does not delete committed interval files.

## States and failure handling

Valid lifecycle paths are `IDLE → RECORDING ↔ PAUSED → STOPPED → SAVED`, plus active or stopped states to `CANCELLED` or `FAILED`. Backend, interval, storage, and display errors preserve their cause through the public exception hierarchy. A failed interval worker records the failure in status and ends rotation.

## Security boundary

No DirectShow audio, camera, microphone, network output, telemetry, or cloud code is present. FFmpeg arguments are passed as a list with `shell=False`. Paths are validated, and output directories are created only when explicitly configured.
