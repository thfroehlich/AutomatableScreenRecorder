# Changelog

## 0.4.0 - 2026-10-15

- Added explicit `normal`, `interval`, and `replay` recording modes.
- Added a rolling replay buffer with a 60-second default window.
- Added `save_replay_buffer()` for retrospective on-demand capture.
- Added interactive replay CLI commands.
- Added `POST /recordings/save-replay` to the REST API.
- Added replay-aware status and result fields.
- Added bounded temporary segment retention.
- Added tests and documentation for all three modes.


## 0.3.0 - 2026-10-14

- Added optional `save_interval_seconds` configuration.
- Added durable numbered interval outputs and final partial-part saving.
- Added interval status and multi-output result fields.
- Replaced pause-path reuse with finalized capture segments and FFmpeg concatenation.
- Replaced unread FFmpeg stderr pipes with temporary diagnostic files.
- Added atomic destination commits and overwrite-race handling.
- Added CLI and benchmark interval options.
- Added deterministic interval-saving tests.
- Expanded API, architecture, performance, privacy, and interval documentation.
- Updated packaging constraints for Core Metadata 2.5 compatible tooling.


## 0.2.0 - 2026-10-14

- Fixed segmented pause/resume, process diagnostics, failure states, atomic output commits, structured HTTP validation errors, packaging, and measured frame counts.


## 0.1.0 - 2026-10-14

- Initial video-only Windows recorder, Python API, optional HTTP adapter, tests, packaging, and CI.
