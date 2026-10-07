# Fieldnotes demo

A fictional outdoor planner for exercising a mobile UI collection loop. This is
an original Godot project with local sample data, hand-drawn vector artwork and
ordinary buttons. It has no capture SDK, autoload, server, private game assets,
network requests or persistent account data.

## Run locally

From the repository root, with Godot 4.4 or newer:

```sh
godot --path examples/mobile-demo
```

The layout uses a 390 × 844 portrait viewport. A deterministic starting screen
can be selected on desktop:

```sh
godot --path examples/mobile-demo -- --demo-state=error
```

Available starting states: `home`, `discover`, `detail`, `loading`, `empty`,
`error`, `saved`, `settings`, `save_modal`, `ready`. These flags are conveniences
for this demo, not a contract required by the collector.

## Explore through real UI actions

| Starting screen | Action | Result |
| --- | --- | --- |
| Home | Featured trail arrow | Trail details |
| Home | Explore | Trail list |
| Home | Saved, before saving anything | Empty collection |
| Home | You | Preferences |
| Trail details | Prepare my route | Persistent loading state |
| Loading | Connection help | Connection error |
| Error | Try again | Loading state |
| Trail details | Save | Confirmation sheet |
| Confirmation sheet | Save my plan | Saved collection |
| Saved collection | Open your plan | Itinerary |
| Preferences | Weekend reminders | Toggle a local preference |

The loader deliberately stays at 68% so a collector can reliably capture it.
“Back to trail” leaves it. The error is simulated; there is no backend or live
route planning. Reminder and saved-plan choices last only for the current run.
Different trail cards share the same sample detail route.

## Reproduce the collection fixture

After installing the demo on a dedicated Android emulator, restart **only
Fieldnotes** so it is on Home with an empty saved collection. Dismiss Android's
first-launch fullscreen notice if it appears. Visually check the Home screen
before replaying; Godot renders the app inside a canvas and its native
accessibility tree does not expose the screen's labels or button text.

Open a new session with this explicit expected inventory:

```sh
mobile-ui-loop --session .mobile-ui-loop/fieldnotes open \
  dev.mobileuiloop.fieldnotes --platform android --target emulator-5560 \
  --expect home discover detail loading empty error saved settings save-modal ready

PYTHONPATH=src python3 examples/collect-fieldnotes.py \
  --session .mobile-ui-loop/fieldnotes \
  --width 1080 --height 2340 --home-confirmed
```

Replace the emulator serial and full screenshot dimensions with your actual
target. The default 1080 × 2340 resolution was exercised on a separate Android
API 36 emulator. The script scales known coordinates from this demo's
390 × 844 canvas and requires the same portrait aspect ratio. Cropping,
rotation, system bars or layout changes invalidate that fixture.

The replay captures eleven observations covering ten expected states: Home,
detail, loading, error, empty, preferences, explore, detail again, save sheet,
saved collection and itinerary. The repeated detail capture supplies context
before opening the sheet; it does not add another expected state. The loader
is deterministic and remains visible until a button is pressed.

This example accepts only `dev.mobileuiloop.fieldnotes` in an empty Android
emulator session. Before each tap it checks the foreground package, visible
node packages and viewport; it checks screenshot dimensions after each capture.
It refuses native overlays, preserves partial evidence on failure and sends no
automatic retries. `--home-confirmed` records your visual starting-state check;
the script cannot infer a Godot screen name from structural native nodes.
Review the images before trusting the supplied state annotations or coverage.
This is a repeatable route for this fixture, not universal discovery of apps.
It installs, resets and opens no applications and performs no AI API calls.

## Export an Android debug APK

Install the Android export templates matching your Godot version. Configure the
Android SDK and Java SDK in Godot's editor settings as described in the
[Godot Android export guide](https://docs.godotengine.org/en/stable/tutorials/export/exporting_for_android.html).
The checked-in `Android` preset uses the distinct package
`dev.mobileuiloop.fieldnotes`, portrait orientation, ARM64/x86_64 and no Internet
permission. Keep signing keys and exported APKs outside version control.

```sh
mkdir -p .local
godot --headless --path examples/mobile-demo \
  --export-debug Android ../../.local/fieldnotes.apk
```

Use a dedicated emulator for collection. Installing this demo is an explicit
setup action; the collector should attach to an already installed app. Android
emulator captures demonstrate rendered states and coordinate navigation, not
physical-device performance or native accessibility coverage.
