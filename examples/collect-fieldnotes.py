#!/usr/bin/env python3
"""Replay the original Fieldnotes demo fixture through an existing device session.

This is a documented example route, not automatic screen discovery. The demo's
Godot canvas has no labelled native accessibility controls, so a human must
visually confirm Home before this coordinate replay begins.
"""

from __future__ import annotations

import argparse
import json
import sys

from mobile_ui_loop.session import LoopError, Session, read_json


APP = "dev.mobileuiloop.fieldnotes"
DESIGN_WIDTH, DESIGN_HEIGHT = 390, 844
EXPECTED = ["home", "discover", "detail", "loading", "empty", "error",
            "saved", "settings", "save-modal", "ready"]

# Points are centres inside this demo's 390 x 844 Godot canvas. Two revisited
# screens provide navigation context; Home is not recaptured, detail is.
FLOW = [
    ((320, 512), "detail", "detail", "Trail details", "Original Cerro Azul sample route."),
    ((138, 688.5), "loading", "loading", "Loading", "Deterministic loader held at 68%; no live backend."),
    ((195, 760), "error", "error", "Connection error", "Simulated failure reached through Connection help."),
    ((195, 686), None, None, None, None),  # Error -> Home.
    ((238, 784.5), "empty", "empty", "Empty collection", "Saved tab before a plan has been saved this run."),
    ((325, 784.5), "settings", "settings", "Preferences", "Local profile and reminder preference."),
    ((151, 784.5), "discover", "discover", "Explore", "Original local sample trail list."),
    ((195, 400), "detail-context", "detail", "Trail details before saving", "Repeated detail screen retained as navigation context."),
    ((315, 688.5), "save-modal", "save-modal", "Save confirmation", "Confirmation sheet with underlying controls disabled."),
    ((195, 700), "saved", "saved", "Saved weekend plan", "One sample plan saved for this run."),
    ((195, 479), "ready", "ready", "Itinerary", "Local sample Saturday itinerary."),
]


def checked_snapshot(snapshot: dict, width: int, height: int) -> None:
    """Refuse foreign apps, native overlays, and changed coordinate spaces."""
    if snapshot.get("appBundleId") != APP:
        raise LoopError("Foreground snapshot is not Fieldnotes; no coordinate action was sent")
    visible = [node for node in snapshot.get("nodes", []) if node.get("visibleToUser") is not False]
    packages = {node.get("bundleId") for node in visible if node.get("bundleId")}
    if packages != {APP}:
        raise LoopError("Snapshot contains another app or system overlay; inspect before continuing")
    if any(node.get("label") or node.get("value") for node in visible):
        raise LoopError("Unexpected native labelled UI; dismiss first-launch dialogs and inspect the demo")
    if snapshot.get("viewport") != [width, height]:
        raise LoopError("Snapshot dimensions differ from --width/--height; no scaled action was sent")


def checked_capture(session: Session, width: int, height: int, **values) -> dict:
    entry = session.capture(**values)
    if entry.get("image_size") != [width, height]:
        raise LoopError("Screenshot dimensions changed; collection stopped before the next action")
    checked_snapshot(entry.get("snapshot", {}), width, height)
    print(json.dumps({"capture": entry["id"], "file": str(session.file(entry["file"]))}), flush=True)
    return entry


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True, help="Existing fresh Fieldnotes Android emulator session")
    parser.add_argument("--width", type=int, default=1080, help="Actual full screenshot width, default 1080")
    parser.add_argument("--height", type=int, default=2340, help="Actual full screenshot height, default 2340")
    parser.add_argument("--home-confirmed", action="store_true", help="I visually checked the demo is on Home with no dialog")
    args = parser.parse_args(argv)
    if not args.home_confirmed:
        parser.error("Visually check the Fieldnotes Home screen, then pass --home-confirmed")
    if not (0 < args.width <= 8192 and 0 < args.height <= 8192):
        parser.error("Screenshot dimensions must be between 1 and 8192 pixels")
    if abs((args.width / args.height) / (DESIGN_WIDTH / DESIGN_HEIGHT) - 1) > 0.01:
        parser.error("This fixture needs the demo's portrait aspect ratio, without cropping or system bars")

    session = Session(args.session)
    try:
        manifest = session.manifest()
        config = read_json(session.root / "device.json")
        if (config.get("app") != APP or config.get("platform") != "android"
                or not str(config.get("target", "")).startswith("emulator-")):
            raise LoopError("This example accepts only the Fieldnotes demo on an explicit Android emulator")
        if any(manifest.get(key) for key in ("captures", "reviews", "proposals")):
            raise LoopError("Use a newly opened empty session; this script never resets existing evidence")
        inventory = [state["id"] for state in manifest.get("registered_states", [])]
        if len(inventory) != len(EXPECTED) or set(inventory) != set(EXPECTED):
            raise LoopError("Open the session with the ten --expect state IDs listed in the demo README")

        checked_snapshot(session.inspect(), args.width, args.height)
        checked_capture(session, args.width, args.height, label="home", state_id="home",
                        title="Home", description="Home visually confirmed by the operator before replay.")
        for point, label, state_id, title, description in FLOW:
            # Recheck app ownership immediately before each gesture. The snapshot
            # validates app identity and framing, not the Godot screen's content.
            checked_snapshot(session.inspect(), args.width, args.height)
            session.press(x=round(point[0] * args.width / DESIGN_WIDTH),
                          y=round(point[1] * args.height / DESIGN_HEIGHT))
            if label:
                checked_capture(session, args.width, args.height, label=label, state_id=state_id,
                                title=title, description=description)
        print(json.dumps({"coverage": session.coverage(), "captures": 11,
                          "scope": "Observed replay of the known Fieldnotes fixture; inspect screenshots to verify labels."}))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc), "next": "Inspect the partial evidence before starting a new session; do not blindly retry."}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
