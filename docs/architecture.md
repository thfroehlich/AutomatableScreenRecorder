# Architecture

## Decisions

The public facade delegates to a testable process protocol, state machine, Windows display adapter, and storage owner. A reentrant lock serializes lifecycle operations, while FFmpeg owns its internal capture/encode pipeline and backpressure. There is no Python frame queue. `gdigrab` is the compatibility-first Windows capture baseline. FFmpeg is chosen because it combines capture, scaling, software/hardware encoding, and finalization in a reproducible executable boundary.

## State and failures

Valid paths are IDLE→RECORDING→PAUSED↔RECORDING→STOPPED→SAVED, plus active/stopped→CANCELLED or active/stopped→FAILED. SAVED, CANCELLED, and FAILED reset to IDLE only when a new start begins. Invalid calls fail before backend work. Process crash, encoding error, or disappearing display becomes `RecordingError`/`ExternalProcessError`; storage cleanup removes temporary data. Disk-full or invalid targets become `SaveError`/`OutputPathError`. Graceful `q` shutdown is attempted for stop, then kill after timeout; cancellation terminates then kills after timeout.

## Security boundary

All subprocess arguments are a list and `shell=False`. The only input device is `gdigrab desktop`; `-an` disables audio. No DirectShow, camera, microphone, network output, URL, or telemetry code exists. The optional HTTP adapter instantiates the same facade and defaults to 127.0.0.1.

## Known design constraint

The compact baseline opens the same temporary path after pause. Some FFmpeg/container combinations do not append safely. Production deployments requiring seamless pause should implement the existing backend protocol with segment files plus a final concat/remux step. The state semantics and fake-backed tests remain valid, but this is a documented limitation of version 0.1.0.
