# Security Policy

## Supported versions

Security fixes are provided for the latest released version of Automatable Screen Recorder.

## Reporting a vulnerability

Please report security vulnerabilities privately through **GitHub Security Advisories** rather than opening a public issue.

When reporting a vulnerability:

- describe the affected component and reproduction conditions;
- include the smallest safe reproduction that demonstrates the issue;
- do not attach real screen recordings containing confidential information;
- do not include credentials, tokens, private URLs, or unnecessary local filesystem paths.

## Security boundaries

Automatable Screen Recorder is designed around the following boundaries:

- normal recording processing is local;
- screen pixels are the intended capture input;
- audio capture is not part of the recorder design;
- microphone and camera access are outside the project scope;
- normal recording does not require telemetry or cloud services;
- external helper processes are invoked with argument lists rather than shell command strings;
- output paths and overwrite behavior are validated before final writes.

## HTTP API

The optional HTTP adapter is unauthenticated and intended for local automation. The default binding is loopback.

Replay mode continuously writes short-lived local temporary video segments.

Do not expose the HTTP adapter to an untrusted network. If a deployment intentionally changes the binding beyond localhost, network access controls and authentication must be provided outside this project.

## Recordings and sensitive information

Screen recordings can contain confidential information visible on the desktop. Treat video files, temporary storage, logs, and destination directories according to the sensitivity of the captured content.

Already committed interval files are persistent outputs. Cancelling a later portion of a recording does not imply deletion of previously saved interval files.
