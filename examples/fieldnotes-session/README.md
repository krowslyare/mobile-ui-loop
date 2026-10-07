# Fieldnotes collection

Real Android emulator captures from the original demo, with an external-agent
review of four selected screens and two generated visual proposals. Browse with:

```sh
mobile-ui-loop --session examples/fieldnotes-session view
```

`session.json` keeps capture provenance, hashes, the review, exact prompts and
original/proposal links. `generation-inputs.json` records each built-in Image Gen
run's ordered references. The second run also uses the generated Home proposal
as a style reference. No model identifier was exposed by that tool.

The repeated detail screenshot remains in the collection with `duplicate_of`.
All ten supplied demo states were observed. Unlisted states remain unknown.
Godot's native accessibility tree is structural; navigation used coordinates.
The loader and connection error are simulated demo states.

Device connection records, daemon state and signing files are not part of this
fixture. The source app uses original sample content and vector art; the two
proposals are generated images, not implemented app screens.
