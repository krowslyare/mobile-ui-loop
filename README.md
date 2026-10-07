# mobile-ui-loop

I kept using Image Gen to rethink the UI of my mobile prototypes, so I made a
small tool around that workflow.

An agent walks the app, collects screens and states, reviews them together,
then writes its own Image Gen prompts based on the app and the direction you
want. You get the originals and proposals side by side, with the prompts saved.

[agent-device](https://github.com/callstack/agent-device) handles navigation and
screenshots. This repo keeps the collection, review and design loop together.

| Android capture | Image Gen proposal |
| --- | --- |
| <img src="examples/fieldnotes-session/captures/0001-home.png" width="240" alt="Fieldnotes Home captured from Android"> | <img src="examples/fieldnotes-session/proposals/proposal-001.png" width="240" alt="Generated Fieldnotes Home proposal"> |

That proposal used four screens from the app as context. The
[example collection](examples/fieldnotes-session) includes the exact prompts.

## Try it

Python 3.9+ is enough to open the included collection:

```sh
git clone https://github.com/krowslyare/mobile-ui-loop.git
cd mobile-ui-loop
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
mobile-ui-loop --session examples/fieldnotes-session view
```

Open the URL it prints. Pick a screen to compare it with its proposal. Keep the
terminal running; Ctrl+C stops the viewer. No device or API key needed here.

## Let your agent use it

Copy the master prompt: **[English](prompts/mobile-ui-loop.en.md)** ·
**[Español](prompts/mobile-ui-loop.es.md)**. Fill in your app, device and visual
brief. You can also use it to audit this repo first.

The agent can work through the CLI or MCP, use its own vision and Image Gen
tools, and save the results here. The viewer only displays the collection;
your agent runs the loop. There is no fixed design prompt for every app.

To capture your own app, install the device runtime with `npm ci` and follow
[device setup](docs/agent-device.md). You'll need Node 22.12+, an explicit device
and the app installed on it. Start each run in a new collection directory.

More detail: [agent workflow, MCP and optional API loop](docs/agent-workflow.md)
· [viewer](docs/gallery.md) · [contributing guidance](AGENTS.md).

## Does it work?

The [Godot demo](examples/mobile-demo/README.md) was run on an Android emulator:
10 supplied states, 11 real captures and two real Image Gen proposals.
[Run evidence](docs/evidence.md) has the details. Coverage is measured against
the states you supply; an unlisted state stays unknown.

40 Python tests + 6 Node tests cover collection integrity, device sessions,
review references, MCP, the viewer and provider failure handling. The standalone
paid API, iOS and physical-device paths haven't been live-tested yet.

To run the checks, use Node 22.12+ alongside the Python environment above:

```sh
python -m unittest discover -s tests -v
npm ci
npm test
```

Still an experiment I use for prototypes. Generated designs need review and
implementation in the app. MIT licensed.
