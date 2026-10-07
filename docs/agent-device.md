# Device runtime

Mobile UI Loop uses the pinned public `agent-device` SDK for opening an app,
snapshots, screenshots, presses, scrolling, and back navigation. It does not
implement a second device driver. Node 22.12+ and the platform's normal tooling
are required. Install local dependencies with `npm ci`.

The Python collection/evaluation layer calls a small Node adapter using one JSON
request over stdin and one JSON result over stdout. Arguments are data, never
shell commands. The adapter creates a named upstream session with reject-on-lock
ownership, and accepts only a small allowlist of public SDK operations.

An explicit serial/UDID is required for device sessions. Every later operation
uses the same named session and target. Errors retain dispatch uncertainty;
failed actions are never blindly retried. The session stores its selected app
and device for traceability, but those connection records are never exported
or served by the viewer.

Accessibility snapshots can be sparse, particularly with custom-rendered UI.
Keep that limitation in the capture metadata and use screenshots as evidence.
Coordinate actions require an explicit point observed in the current screen.
The tool does not claim discovery of every possible app state.

Sources: [Node API](https://oss.callstack.com/agent-device/docs/client-api),
[snapshots](https://oss.callstack.com/agent-device/docs/snapshots), and
[device ownership](https://oss.callstack.com/agent-device/docs/sessions).
