# Contributing

Thank you for helping improve Automated Screen Recorder. Contributions should preserve the project's local-only, video-only design and keep the public API predictable and testable.

## Development requirements

- Python 3.11 or newer
- Windows for real desktop-capture integration testing
- FFmpeg for tests that exercise the real recording pipeline

Install the development environment from the repository root:

```powershell
py -3.11 -m pip install -e ".[dev,http]"
```

## Development workflow

1. Create a focused branch for the change.
2. Keep implementation changes small and explicit.
3. Add or update tests for changed behavior.
4. Update documentation when public behavior, configuration, CLI options, or API models change.
5. Run the quality checks before opening a pull request.

## Required quality checks

```powershell
python -m ruff check . --ignore E501,I001
python -m ruff format --check .
python -m mypy src
python -m pytest --cov=automated_screen_recorder
```

E501 and I001 are advisory in CI. Other selected Ruff findings, formatting failures, mypy errors, and test failures are blocking.

## Testing expectations

Add deterministic tests for:

- state-machine changes;
- configuration validation;
- storage and cleanup behavior;
- interval rotation behavior;
- HTTP request idempotency;
- backend process failures;
- output-path and overwrite handling.

Use fake or stub backends for unit tests. Do not require a physical microphone, camera, or other peripheral.

Tests requiring a real interactive Windows desktop must use the `windows_desktop` marker and be safely skipped when the environment cannot provide desktop capture.

## Project constraints

Contributions must not introduce:

- audio recording;
- microphone or camera access;
- telemetry;
- cloud upload or cloud processing;
- hidden network dependencies for normal recording;
- `shell=True` for external processes;
- unbounded frame or work queues;
- per-frame logging in the performance-critical path.

External-process arguments should be supplied as argument lists. Filesystem paths should use `pathlib.Path`.

## Documentation style

All repository documentation, code comments, docstrings, exceptions, CLI text, API errors, and examples are written in English.

Public examples must use the actual supported API. Avoid placeholder code and undocumented behavior.

## Pull requests

A pull request should explain:

- what changed;
- why the change is needed;
- which tests cover the change;
- whether public API or configuration behavior changed;
- any Windows or FFmpeg-specific validation that was performed.

Developer Certificate of Origin sign-off is required for contributions.
