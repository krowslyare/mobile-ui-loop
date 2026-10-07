# Device runtime

Mobile UI Loop uses the pinned public `agent-device` SDK for opening an app,
snapshots, screenshots, presses, scrolling, and back navigation. It does not
implement a second device driver. Node 22.12+ and the platform's normal tooling
are required. Install local dependencies with `npm ci`.

## Prepare a device

These steps are unnecessary for browsing the included collection.

### Android

Install the Android SDK and Platform-Tools through Android Studio's SDK Manager
or the [official Platform-Tools distribution](https://developer.android.com/tools/releases/platform-tools).
Make `adb` available in the terminal running this tool. With Android Studio's
default macOS SDK location, a shell-local setup is:

```sh
export PATH="$HOME/Library/Android/sdk/platform-tools:$PATH"
node --version
npm ci
adb version
adb devices -l
```

Node must be 22.12 or newer. Start your emulator, or connect your own Android
device with USB debugging enabled and approve its debugging prompt. Wait until
the intended app is usable. Copy the exact serial from the first column of
`adb devices -l`; `emulator-5554` below is an example, not an automatically chosen
device. If the device is `offline` or `unauthorized`, finish device setup first.
See the [official ADB guide](https://developer.android.com/tools/adb).

Install your APK on that selected device if it is not already installed:

```sh
adb -s emulator-5554 install /PATH/TO/your-app.apk
mobile-ui-loop --session .mobile-ui-loop/my-app open com.example.myapp \
  --platform android --target emulator-5554
```

Replace the serial, APK path and package ID with your own values. Use a new
collection directory for each run; `open` preserves existing directories by
refusing to overwrite them. Godot's package ID is configured in its Android
export preset. This tool attaches to the installed app; it does not export or
install it automatically.

### iOS

Install Xcode and the required simulator runtime, boot the intended simulator
and install your app there. List simulator UDIDs with:

```sh
xcrun simctl list devices available
```

Use the intended simulator's full UDID as `--target` and its installed bundle ID
with `--platform ios`. Physical-device pairing/signing requirements are in
[agent-device's installation guide](https://oss.callstack.com/agent-device/docs/installation).
Mobile UI Loop's live evidence currently covers Android emulation; the iOS and
physical-device paths remain unverified.

## Session behavior

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
