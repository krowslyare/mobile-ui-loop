# Working on Mobile UI Loop

Start with `README.md` and the master prompt in
`prompts/mobile-ui-loop.en.md` or `prompts/mobile-ui-loop.es.md`.
Device setup and CLI/MCP review contracts live in `docs/`.

This is a standalone public-facing developer tool. Keep examples original and
independent of private apps. Capture provenance and coverage claims must be
explicit: a supplied inventory is different from observed running states, and
unlisted states remain unknown. Imported screenshots retain external provenance.

Use Python 3.9+ with the standard library and the pinned agent-device Node.js
SDK for navigation and capture. The CLI and MCP server use the same operations. Never log credentials
or commit captured private projects, session tokens, local outputs, or API keys.

Run `PYTHONPATH=src python3 -m unittest discover -s tests -v`. Integration
checks use only `examples/mobile-demo` and an explicitly selected device; do not modify external projects.
Provider tests use a fake transport. Live image generation is opt-in and its
results must not be described as verified until it has actually run.

Stage explicit paths and keep commits focused. Do not push or create a remote
repository without the user's instruction.
