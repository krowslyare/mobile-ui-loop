# First collection run

Local run on October 7, 2026. This records what was actually exercised; it is not
a benchmark or proof of every possible app state.

| Layer | Evidence |
| --- | --- |
| App | Original Fieldnotes demo, Godot 4.7.2, Android debug APK, `dev.mobileuiloop.fieldnotes` |
| Device | Dedicated Android API 36 emulator, 1080 × 2340 portrait screenshots |
| Driver | Pinned `agent-device` 0.21.23 public SDK; explicitly selected serial and named session |
| Collection | 11 observed captures across all 10 supplied states, including one repeated detail screen |
| Navigation | Real coordinate presses through agent-device; Godot's canvas button labels were absent from native accessibility |
| Review | Existing Codex agent inspected images and recorded a grounded review of Home, details, loading and Explore |
| Generation | Codex built-in Image Gen, local screenshots as references; imported PNGs preserve exact prompts and review link |
| Viewer | Desktop 1200 × 853 and mobile 390 × 844 / 320 × 740 checks in Chrome |
| Automated checks | 40 Python tests + 6 Node tests; fake provider/SDK transports, no paid API calls |

Supplied states: Home, Explore, details, loading, empty saved collection,
connection error, saved plan, preferences, confirmation sheet and ready
itinerary. The demo's loader and error are deterministic fixtures, not a real
backend outage or measured performance. An unlisted state remains unknown.

The browser checks exercised selection, filtering, empty results, clipboard
feedback, image aspect ratios, capture context, Escape/focus restoration,
expected-state coverage, refresh, offline messaging and comparison. A temporary
empty session was checked separately. Generation proposals are inspected for
content preservation; no claim of improved task success is made.

## Reproduce locally

Run or export the [demo](../examples/mobile-demo/README.md), install its APK on
your dedicated device, then open a new collection through the CLI. The optional
[fixture collector](../examples/collect-fieldnotes.py) replays this demo's known
coordinate journey. It is not an app crawler.

The checked-in [session](../examples/fieldnotes-session) can be viewed offline
without an emulator or key. It includes captures, their dimensions/hashes,
review, proposals and generation prompts. Device connection files and upstream
daemon state are excluded.

## Remaining verification boundaries

The live standalone OpenAI API path, iOS, physical devices, arbitrary-app
discovery and actual user task performance have not been exercised. API tests
check serialization, reference ordering, provenance, response validation and
error behavior using fake transports. Actual multi-image generation in this
example used the existing agent's built-in Image Gen tool.
