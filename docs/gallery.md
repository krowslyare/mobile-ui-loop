# Reviewing a collection locally

Start the read-only viewer from an existing session:

```sh
mobile-ui-loop --session .mobile-ui-loop/session view
```

Open the localhost URL printed by the command. The viewer uses plain HTML, CSS,
and JavaScript, with no frontend build or external fonts and assets. It fetches
only the selected session from the local server. Use **Refresh** after an agent
or CLI operation adds captures, evaluations, or proposals.

## Collect, then compare

- Browse the collected mobile states, search by title, state ID, capture ID, or
  description, and filter observed captures from imported images.
- Select captures and use **Copy capture IDs** to get a JSON array for an agent
  tool’s `capture_ids` argument (CLI: `--ids`). Selection persists through filters and refreshes while
  those capture IDs remain in the session.
- Open a capture to compare the original with a visual proposal. If several
  proposals exist, choose one from the proposal selector. Images retain their
  original proportions; screenshots are never stretched into a phone shape.
- Read the evaluation’s app theme, audience, summary, shared visual direction,
  and per-screen observations. With several evaluations, use the evaluation
  selector to choose which notes and image briefs to inspect.
- Use **Copy prompt** in a capture’s detail to copy its recorded proposal prompt
  or the selected evaluation’s brief. Keep relevant collection images alongside
  the brief when generating outside the CLI.

Each detail also retains capture provenance, dimensions, timestamp, file hash,
and the available device snapshot. A visual proposal is labeled **Concept**.
Evaluations and image concepts are suggestions, not evidence that an
implementation works or that a physical device was tested.

## What the counts mean

The gallery shows every capture record, including separate captures of the same
state. **Captured from inventory** counts distinct expected state IDs with at
least one capture, within the state inventory explicitly supplied by the user.
It is not automatic discovery of every screen in the app. Without an inventory,
the count is unknown and the viewer says so. Observed and imported captures keep
their separate source labels.

Empty sessions, absent evaluations, absent proposals, unavailable images, and
connection errors have explicit empty or error states. The viewer never fills
missing evidence with generated placeholder screens. When the connection fails
after a successful load, previously loaded records stay visible and the error
identifies that they could not be refreshed.

## Keyboard and local behavior

All filters, selection controls, capture buttons, and selectors are reachable
with the keyboard. Opening a screen uses a native modal dialog; **Escape** or
the close button dismisses it. The clipboard buttons show a selectable text
fallback if browser clipboard access is unavailable.

The viewer has no write endpoints and cannot navigate the app, generate images,
or call a provider. Those operations belong to the agent tools and CLI. Treat
session content as local project evidence, and only publish captures after
checking that they contain no private app data.
