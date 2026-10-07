"""CLI for collection, thematic evaluation, and linked image proposals."""

import argparse
import json
from pathlib import Path
import sys

from . import __version__
from .session import Session, initialize, launch, read_json


def parser():
    root = argparse.ArgumentParser(prog="mobile-ui-loop", description="Collect app screens with agent-device, evaluate them together, and generate visual proposals.")
    root.add_argument("--version", action="version", version=__version__)
    root.add_argument("--session", default=".mobile-ui-loop/session", help="Local collection directory")
    commands = root.add_subparsers(dest="command", required=True)
    start = commands.add_parser("open", help="Open an installed mobile app using agent-device")
    start.add_argument("app", help="Installed app package/bundle ID")
    start.add_argument("--platform", choices=["android", "ios"], required=True)
    start.add_argument("--target", required=True, help="Exact Android serial or iOS UDID")
    start.add_argument("--expect", nargs="*", default=[], help="Expected state inventory; never a discovery claim")
    init = commands.add_parser("init", help="Create an offline collection for existing capture artifacts")
    init.add_argument("--name", required=True)
    init.add_argument("--expect", nargs="*", default=[])
    commands.add_parser("inspect", help="Inspect the active app's accessibility snapshot")
    press = commands.add_parser("press", help="Act through an inspected ref, selector, or screenshot coordinate")
    group = press.add_mutually_exclusive_group(required=True)
    group.add_argument("--ref")
    group.add_argument("--selector")
    group.add_argument("--point", nargs=2, type=float, metavar=("X", "Y"))
    scroll = commands.add_parser("scroll", help="Scroll the app through agent-device")
    scroll.add_argument("direction", choices=["up", "down", "left", "right"])
    commands.add_parser("back", help="Navigate back in the active device session")
    capture = commands.add_parser("capture", help="Capture the current rendered screen with context")
    imported = commands.add_parser("import-capture", help="Collect an existing PNG with external provenance")
    imported.add_argument("image")
    for command in (capture, imported):
        command.add_argument("--label", required=True)
        command.add_argument("--state", default="")
        command.add_argument("--title", default="")
        command.add_argument("--description", default="")
    commands.add_parser("list", help="List evidence IDs and declared coverage")
    bundle = commands.add_parser("bundle", help="Export multiple references and a brief, without an API call")
    bundle.add_argument("destination")
    review = commands.add_parser("evaluate", help="Evaluate several screens together; uses OpenAI API credits")
    loop = commands.add_parser("loop", help="Evaluate context, self-prompt, and generate selected proposals; uses API credits")
    external = commands.add_parser("import-review", help="Validate and import a review written by your existing agent")
    external.add_argument("document")
    for command in (bundle, review, loop, external):
        command.add_argument("--ids", nargs="+", required=command is external)
        command.add_argument("--theme", required=True)
        command.add_argument("--audience", required=True)
        command.add_argument("--constraint", action="append", default=[])
    review.add_argument("--model", required=True)
    loop.add_argument("--model", required=True, help="Vision-capable Responses model")
    loop.add_argument("--image-model", required=True)
    loop.add_argument("--targets", nargs="+", required=True, help="Capture IDs to redesign (maximum four)")
    generate = commands.add_parser("generate", help="Generate one reviewed state using collection context; uses API credits")
    generate.add_argument("capture_id")
    generate.add_argument("--review", required=True)
    generate.add_argument("--model", required=True)
    proposal = commands.add_parser("import-proposal", help="Link an external Image Gen PNG to its original state")
    proposal.add_argument("capture_id")
    proposal.add_argument("image")
    proposal.add_argument("--prompt-file", required=True)
    proposal.add_argument("--review", default="", help="Link the proposal to an existing review")
    viewer = commands.add_parser("view", help="Serve the local collection and comparison viewer")
    viewer.add_argument("--port", type=int, default=0)
    commands.add_parser("mcp", help="Expose navigation, collection, and review tools over MCP stdio")
    commands.add_parser("close", help="Release only this upstream device session")
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    session = Session(args.session)
    try:
        if args.command == "open":
            result = launch(args.app, args.session, args.platform, args.target, args.expect)
        elif args.command == "init":
            result = {"session": str(initialize(args.session, args.name, args.expect).root)}
        elif args.command == "inspect":
            result = session.inspect()
        elif args.command == "press":
            point = args.point or [None, None]
            result = session.press(args.ref or "", args.selector or "", *point)
        elif args.command == "scroll":
            result = session.scroll(args.direction)
        elif args.command == "back":
            result = session.back()
        elif args.command in ("capture", "import-capture"):
            values = (args.label, args.description, args.state, args.title)
            result = session.capture(*values) if args.command == "capture" else session.import_capture(args.image, *values)
        elif args.command == "list":
            manifest = session.manifest()
            result = {"captures": manifest["captures"], "reviews": [entry["id"] for entry in manifest["reviews"]], "coverage": session.coverage()}
        elif args.command == "bundle":
            result = session.bundle(args.destination, args.ids, args.theme, args.audience, args.constraint)
        elif args.command == "evaluate":
            result = session.evaluate(args.ids, args.theme, args.audience, args.constraint, args.model)
        elif args.command == "loop":
            selected = session.selected(args.ids)
            if not 1 <= len(args.targets) <= 4 or len(set(args.targets)) != len(args.targets) or not set(args.targets).issubset({item["id"] for item in selected}):
                raise ValueError("Choose one to four unique targets from the selected collection")
            review = session.evaluate(args.ids, args.theme, args.audience, args.constraint, args.model)
            proposals = []
            for identifier in args.targets:
                proposals.append(session.generate(identifier, review["id"], args.image_model))
            result = {"review": review, "proposals": proposals}
        elif args.command == "import-review":
            result = session.import_review(read_json(Path(args.document)), args.ids, args.theme, args.audience, args.constraint)
        elif args.command == "generate":
            result = session.generate(args.capture_id, args.review, args.model)
        elif args.command == "import-proposal":
            result = session.import_proposal(args.capture_id, args.image, Path(args.prompt_file).read_text(encoding="utf-8"), args.review)
        elif args.command == "close":
            result = session.stop()
        elif args.command == "mcp":
            from .mcp import serve
            serve(session)
            return 0
        else:
            from .server import make_server
            session.manifest()
            server = make_server(session, args.port)
            print(json.dumps({"url": "http://127.0.0.1:%d" % server.server_port, "session": str(session.root)}), flush=True)
            try:
                server.serve_forever()
            finally:
                server.server_close()
            return 0
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
