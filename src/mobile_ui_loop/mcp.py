"""Minimal MCP stdio transport around the same session operations as the CLI.

One JSON-RPC message per line; stdout contains protocol messages only.
"""

from __future__ import annotations

import base64
import math
import json
import sys
from pathlib import Path

from . import __version__
from .session import LoopError, Session


def tool(name, description, properties=None, required=None, read_only=False):
    return {"name": name, "description": description,
            "inputSchema": {"type": "object", "properties": properties or {}, "required": required or [], "additionalProperties": False},
            "annotations": {"readOnlyHint": read_only, "destructiveHint": False, "openWorldHint": name in ("evaluate_collection", "generate_proposal")}}


STRING = {"type": "string", "minLength": 1}
IDS = {"type": "array", "items": STRING, "minItems": 1, "maxItems": 16, "uniqueItems": True}
TOOLS = [
    tool("inspect_app", "Inspect active app accessibility nodes and refs. Sparse semantic data does not prove an empty UI.", read_only=True),
    tool("press_control", "Act using a current ref, selector, or screenshot coordinate. Exactly one target mode; uses agent-device.",
         {"ref": STRING, "selector": STRING, "x": {"type": "number"}, "y": {"type": "number"}}),
    tool("scroll_app", "Scroll the active app through agent-device.", {"direction": {"type": "string", "enum": ["up", "down", "left", "right"]}}, ["direction"]),
    tool("back", "Navigate back within the selected device session."),
    tool("capture_state", "Collect a rendered screen and state context. Returns PNG for inspection; semantic context is sampled afterwards.",
         {"label": STRING, "description": {"type": "string"}, "state_id": STRING, "title": STRING}, ["label"]),
    tool("list_captures", "List evidence IDs, missing expected states, and saved review IDs. Coverage is never exhaustive.", read_only=True),
    tool("read_capture", "Read one collected PNG and its metadata.", {"capture_id": STRING}, ["capture_id"], True),
    tool("read_review", "Read a saved grounded visual review and its per-state Image Gen prompts.", {"review_id": STRING}, ["review_id"], True),
    tool("prepare_bundle", "Export 2-16 references, theme, audience, and a brief for your existing design agent. No API call.",
         {"destination": STRING, "capture_ids": IDS, "theme": STRING, "audience": STRING,
          "constraints": {"type": "array", "items": STRING}}, ["destination", "theme", "audience"]),
    tool("record_review", "Save your own visual evaluation and per-state Image Gen prompts without an API call. Document requires summary, observations, direction, prompts; see review schema in docs.",
         {"document": {"type": "object"}, "capture_ids": IDS, "theme": STRING, "audience": STRING,
          "constraints": {"type": "array", "items": STRING}}, ["document", "capture_ids", "theme", "audience"]),
    tool("record_proposal", "Import a PNG produced by your existing Image Gen tool, preserving its prompt and original capture link. image_path is a local generated file; no provider call.",
         {"capture_id": STRING, "image_path": STRING, "prompt": STRING, "review_id": STRING}, ["capture_id", "image_path", "prompt"]),
    tool("evaluate_collection", "Use OpenAI vision to review 2-16 screens together and self-prompt redesigns. Requires OPENAI_API_KEY; consumes API usage.",
         {"capture_ids": IDS, "theme": STRING, "audience": STRING, "constraints": {"type": "array", "items": STRING}, "model": STRING}, ["theme", "audience", "model"]),
    tool("generate_proposal", "Use OpenAI image edits with target first and collection context. Requires OPENAI_API_KEY; consumes API usage.",
         {"capture_id": STRING, "review_id": STRING, "model": STRING}, ["capture_id", "review_id", "model"]),
]


def validate_arguments(spec: dict, arguments: dict):
    if not isinstance(arguments, dict):
        raise LoopError("Tool arguments must be an object")
    schema = spec["inputSchema"]
    if set(arguments) - set(schema["properties"]) or not set(schema["required"]).issubset(arguments):
        raise LoopError("Unknown or missing tool arguments")
    for key, value in arguments.items():
        rule = schema["properties"][key]
        if rule["type"] == "string" and (not isinstance(value, str) or (rule.get("minLength") and not value.strip())):
            raise LoopError(key + " must be a non-empty string")
        if "enum" in rule and value not in rule["enum"]:
            raise LoopError("Invalid " + key)
        if rule["type"] == "number" and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
            raise LoopError(key + " must be a finite number")
        if rule["type"] == "object" and not isinstance(value, dict):
            raise LoopError(key + " must be an object")
        if rule["type"] == "array":
            if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
                raise LoopError(key + " must be an array of strings")
            if len(value) < rule.get("minItems", 0) or len(value) > rule.get("maxItems", 100):
                raise LoopError(key + " contains too many or too few values")
            if rule.get("uniqueItems") and len(value) != len(set(value)):
                raise LoopError(key + " must contain unique values")


def dispatch(session: Session, name: str, arguments: dict) -> dict:
    if not isinstance(name, str):
        raise LoopError("Tool name must be a string")
    spec = next((item for item in TOOLS if item["name"] == name), None)
    if spec is None:
        raise LoopError("Unknown tool: " + name)
    validate_arguments(spec, arguments)
    image_path = None
    if name == "inspect_app":
        result = session.inspect()
    elif name == "press_control":
        result = session.press(arguments.get("ref", ""), arguments.get("selector", ""), arguments.get("x"), arguments.get("y"))
    elif name == "scroll_app":
        result = session.scroll(arguments["direction"])
    elif name == "back":
        result = session.back()
    elif name == "capture_state":
        result = session.capture(arguments["label"], arguments.get("description", ""), arguments.get("state_id", ""), arguments.get("title", ""))
        image_path = session.file(result["file"])
    elif name == "list_captures":
        manifest = session.manifest()
        result = {"captures": [{key: entry[key] for key in ("id", "state_id", "title", "description", "kind", "file", "image_size")} for entry in manifest["captures"]],
                  "coverage": session.coverage(), "reviews": [entry["id"] for entry in manifest["reviews"]]}
    elif name == "read_capture":
        result = session.selected([arguments["capture_id"]], minimum=1)[0]
        image_path = result.pop("image_path")
    elif name == "read_review":
        result = next((item for item in session.manifest()["reviews"] if item["id"] == arguments["review_id"]), None)
        if result is None:
            raise LoopError("Unknown review ID")
    elif name == "prepare_bundle":
        result = session.bundle(arguments["destination"], arguments.get("capture_ids"), arguments["theme"], arguments["audience"], arguments.get("constraints", []))
    elif name == "evaluate_collection":
        result = session.evaluate(arguments.get("capture_ids"), arguments["theme"], arguments["audience"], arguments.get("constraints", []), arguments["model"])
    elif name == "record_review":
        result = session.import_review(arguments["document"], arguments["capture_ids"], arguments["theme"], arguments["audience"], arguments.get("constraints", []))
    elif name == "record_proposal":
        result = session.import_proposal(arguments["capture_id"], Path(arguments["image_path"]), arguments["prompt"], arguments.get("review_id", ""))
        image_path = session.file(result["file"])
    else:
        result = session.generate(arguments["capture_id"], arguments["review_id"], arguments["model"])
        image_path = session.file(result["file"])
    content = [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]
    if image_path:
        content.append({"type": "image", "mimeType": "image/png", "data": base64.b64encode(image_path.read_bytes()).decode()})
    return {"content": content, "isError": bool(isinstance(result, dict) and result.get("ok") is False)}


def handle(session: Session, request: dict) -> dict | None:
    if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid request"}}
    if "id" not in request:
        return None
    identifier, method = request["id"], request.get("method")
    params = request.get("params", {})
    if not isinstance(params, dict):
        return {"jsonrpc": "2.0", "id": identifier, "error": {"code": -32602, "message": "Params must be an object"}}
    if method == "initialize":
        requested = params.get("protocolVersion", "2024-11-05")
        supported = ("2024-11-05", "2025-03-26", "2025-06-18")
        result = {"protocolVersion": requested if requested in supported else supported[-1], "capabilities": {"tools": {}},
                  "serverInfo": {"name": "mobile_ui_loop", "version": __version__},
                  "instructions": "Inspect before acting. Capture several states, including transitions and failure states. Coverage is declared, never exhaustive. Review evidence before generating designs."}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        try:
            result = dispatch(session, params.get("name", ""), params.get("arguments", {}))
        except (ValueError, OSError) as exc:
            result = {"content": [{"type": "text", "text": str(exc)}], "isError": True}
    else:
        return {"jsonrpc": "2.0", "id": identifier, "error": {"code": -32601, "message": "Method not found"}}
    return {"jsonrpc": "2.0", "id": identifier, "result": result}


def serve(session: Session, stdin=None, stdout=None):
    stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
    session.manifest()
    for line in stdin:
        if len(line) > 1024 * 1024:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Request exceeds 1 MiB"}}
        else:
            try:
                response = handle(session, json.loads(line))
            except json.JSONDecodeError:
                response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        if response is not None:
            stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            stdout.flush()
