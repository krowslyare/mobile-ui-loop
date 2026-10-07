"""A session is a local evidence directory, shared by CLI, MCP, and viewer."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
from typing import Any
import uuid


class LoopError(ValueError):
    """An actionable failure that is safe to show to a caller."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_json(path: Path, value: Any, private: bool = False) -> None:
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            if private:
                os.chmod(temporary, 0o600)
            json.dump(value, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LoopError("Cannot read " + path.name + "; check the session directory") from exc
    if not isinstance(value, dict):
        raise LoopError(path.name + " must contain a JSON object")
    return value


def slug(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-")[:60]
    if not clean:
        raise LoopError("Use a label containing letters or numbers")
    return clean.lower()


def png_size(path: Path) -> list[int]:
    if path.stat().st_size > 32 * 1024 * 1024:
        raise LoopError("PNG exceeds the 32 MiB capture limit")
    with path.open("rb") as stream:
        header = stream.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise LoopError("Capture must be a PNG with a valid IHDR header")
    width, height = struct.unpack(">II", header[16:24])
    if not 0 < width <= 8192 or not 0 < height <= 8192:
        raise LoopError("Capture dimensions must be between 1 and 8192 pixels")
    return [width, height]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Session:
    def __init__(self, directory: str | Path):
        self.root = Path(directory).expanduser().resolve()
        self.manifest_path = self.root / "session.json"

    def manifest(self) -> dict:
        data = read_json(self.manifest_path)
        if data.get("schema_version") != 1:
            raise LoopError("Unsupported session schema")
        return data

    def file(self, relative: str) -> Path:
        candidate = (self.root / relative).resolve()
        if not candidate.is_relative_to(self.root):
            raise LoopError("Session file escapes its directory")
        return candidate

    @contextmanager
    def lock(self):
        path = self.root / ".operation.lock"
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise LoopError("Another operation owns this session; finish it before continuing") from exc
        try:
            os.write(fd, str(os.getpid()).encode())
            yield
        finally:
            os.close(fd)
            path.unlink(missing_ok=True)

    def request(self, method: str, **params) -> dict:
        config = read_json(self.root / "device.json")
        adapter = Path(__file__).parent / "runtime" / "agent-device.mjs"
        payload = json.dumps({"config": config, "method": method, "params": params})
        # This adapter promises local device work. Do not inherit an upstream
        # remote-daemon/provider configuration from an unrelated shell session.
        env = {key: value for key, value in os.environ.items()
               if not key.startswith("AGENT_DEVICE_") and key != "OPENAI_API_KEY"}
        env["AGENT_DEVICE_NO_UPDATE_NOTIFIER"] = "1"
        try:
            response = subprocess.run(["node", str(adapter)], input=payload, capture_output=True,
                                      text=True, timeout=90, env=env)
            if len(response.stdout) > 2 * 1024 * 1024:
                raise LoopError("Device response is too large")
            result = json.loads(response.stdout)
        except subprocess.TimeoutExpired:
            raise LoopError("Device operation timed out; dispatch outcome is unknown. Inspect before retrying.") from None
        except (OSError, ValueError) as exc:
            raise LoopError("Device runtime unavailable; run npm ci and check Node 22.12+") from exc
        if not isinstance(result, dict) or not result.get("ok"):
            if isinstance(result, dict):
                raise LoopError("%s: %s (dispatched: %s)" % (result.get("code", "DEVICE_ERROR"), result.get("error", "Device request failed"), result.get("dispatched", "unknown")))
            raise LoopError("Invalid device response")
        if not isinstance(result.get("result"), dict):
            raise LoopError("Device response must be an object")
        return result["result"]

    def trace(self, action: str, data: dict) -> None:
        with (self.root / "actions.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"at": now(), "action": action, **data}, ensure_ascii=False) + "\n")

    def inspect(self) -> dict:
        return self.request("inspect")

    def press(self, ref: str = "", selector: str = "", x=None, y=None) -> dict:
        choices = bool(ref) + bool(selector) + (x is not None or y is not None)
        if choices != 1:
            raise LoopError("Choose exactly one ref, selector, or coordinate point")
        params = {"ref": ref} if ref else {"selector": selector} if selector else {"x": x, "y": y}
        with self.lock():
            result = self.request("press", **params)
            self.trace("press", params)
            return result

    def scroll(self, direction: str) -> dict:
        if direction not in ("up", "down", "left", "right"):
            raise LoopError("Use up, down, left, or right")
        with self.lock():
            result = self.request("scroll", direction=direction)
            self.trace("scroll", {"direction": direction})
            return result

    def back(self) -> dict:
        with self.lock():
            result = self.request("back")
            self.trace("back", {})
            return result

    def capture(self, label: str, description: str = "", state_id: str = "", title: str = "") -> dict:
        with self.lock():
            manifest = self.manifest()
            identifier = "%04d-%s" % (len(manifest["captures"]) + 1, slug(label))
            filename = identifier + ".png"
            result = self.request("capture", filename=filename)
            if result.get("file") != "captures/" + filename:
                raise LoopError("Runtime returned an unexpected capture path")
            path = self.file(result["file"])
            dimensions = png_size(path)
            snapshot = result.get("snapshot", {})
            snapshot["image_viewport"] = dimensions
            # A screenshot and accessibility tree can describe different moments.
            # Preserve the producer's viewport and timing rather than inventing agreement.
            digest = sha256(path)
            duplicate = next((item["id"] for item in manifest["captures"] if item["sha256"] == digest), None)
            entry = {"id": identifier, "file": result["file"], "state_id": slug(state_id or label),
                     "title": title or label, "description": description, "kind": "observed",
                     "sha256": digest, "image_size": dimensions, "captured_at": now(),
                     "snapshot": snapshot, "runtime": result.get("runtime", {})}
            if duplicate:
                entry["duplicate_of"] = duplicate
            manifest["captures"].append(entry)
            write_json(self.manifest_path, manifest)
            self.trace("capture", {"capture_id": identifier, "state_id": entry["state_id"], "kind": "observed"})
            return entry

    def import_capture(self, image: str | Path, label: str, description: str = "", state_id: str = "", title: str = "") -> dict:
        """Ingest existing agent-device artifacts; preserve their external provenance."""
        source = Path(image).expanduser().resolve()
        png_size(source)
        with self.lock():
            manifest = self.manifest()
            identifier = "%04d-%s" % (len(manifest["captures"]) + 1, slug(label))
            relative = "captures/" + identifier + ".png"
            target = self.file(relative)
            target.parent.mkdir(exist_ok=True)
            shutil.copyfile(source, target)
            entry = {"id": identifier, "file": relative, "state_id": slug(state_id or label),
                     "title": title or label, "description": description, "kind": "imported",
                     "sha256": sha256(target), "image_size": png_size(target), "captured_at": now(),
                     "snapshot": {"controls": [], "metadata_timing": "external capture; original time unknown"}}
            manifest["captures"].append(entry)
            write_json(self.manifest_path, manifest)
            return entry

    def coverage(self) -> dict:
        manifest = self.manifest()
        known = [item["id"] for item in manifest["registered_states"]]
        seen = {item["state_id"] for item in manifest["captures"]}
        return {"registered": known, "captured": [item for item in known if item in seen],
                "missing": [item for item in known if item not in seen],
                "scope": "Expected state inventory only; unlisted and unvisited states are unknown."}

    def selected(self, identifiers: list[str] | None = None, minimum: int = 2) -> list[dict]:
        captures = self.manifest()["captures"]
        by_id = {item["id"]: item for item in captures}
        identifiers = list(by_id) if identifiers is None else identifiers
        if len(identifiers) != len(set(identifiers)) or not set(identifiers).issubset(by_id):
            raise LoopError("Choose unique capture IDs from this session")
        if not minimum <= len(identifiers) <= 16:
            raise LoopError("Choose between %d and 16 captures; narrow the context explicitly" % minimum)
        selected = []
        for identifier in identifiers:
            entry = dict(by_id[identifier])
            path = self.file(entry["file"])
            if sha256(path) != entry["sha256"]:
                raise LoopError("Capture changed after collection: " + identifier)
            entry["image_path"] = path
            entry["controls"] = entry.get("snapshot", {}).get("controls", [])
            selected.append(entry)
        return selected

    def bundle(self, destination: str | Path, identifiers: list[str] | None, theme: str, audience: str, constraints: list[str]) -> dict:
        if not theme.strip() or not audience.strip():
            raise LoopError("Provide both theme and audience")
        with self.lock():
            selected = self.selected(identifiers)
            target = Path(destination).expanduser().resolve()
            if target.exists():
                raise LoopError("Bundle destination already exists; choose a new directory")
            if target.is_relative_to(self.root / "captures"):
                raise LoopError("Bundle cannot be placed inside the capture directory")
            target.mkdir(parents=True)
            (target / "references").mkdir()
            references = []
            for entry in selected:
                relative = "references/" + entry["id"] + ".png"
                shutil.copyfile(entry["image_path"], target / relative)
                references.append({key: entry[key] for key in ("id", "title", "state_id", "description", "kind", "sha256", "image_size")})
                references[-1]["file"] = relative
                references[-1]["controls"] = entry["snapshot"].get("controls", [])
                references[-1]["metadata_timing"] = entry["snapshot"].get("metadata_timing", "unknown")
                references[-1]["semantic_viewport"] = entry["snapshot"].get("viewport")
            manifest = self.manifest()
            bundle = {"schema_version": 1, "project_name": manifest["project_name"], "theme": theme, "audience": audience,
                      "constraints": constraints, "references": references, "coverage": self.coverage(),
                      "excluded_capture_ids": [item["id"] for item in manifest["captures"] if item["id"] not in {ref["id"] for ref in references}]}
            write_json(target / "bundle.json", bundle)
            lines = ["# Visual review brief", "", "Theme: " + theme, "Audience: " + audience, "",
                     "Evaluate this collection as one mobile app. Ground observations in capture IDs.",
                     "Preserve the app's actions, content, state distinctions, and phone framing.",
                     "Choose one coherent visual direction, then write a generation prompt for each selected state.",
                     "Generated images are design proposals; implementation and interaction checks happen separately.", "", "## Constraints", ""]
            lines.extend("- " + item for item in constraints or ["Keep all existing actions and meaningful content."])
            lines.extend(["", "## References", ""])
            lines.extend("- %s: %s (%s). %s" % (ref["id"], ref["title"], ref["kind"], ref["description"]) for ref in references)
            lines.extend(["", "## Coverage", "", json.dumps(bundle["coverage"], ensure_ascii=False), ""])
            (target / "brief.md").write_text("\n".join(lines), encoding="utf-8")
            return {"directory": str(target), "references": len(references), "brief": str(target / "brief.md")}

    def evaluate(self, identifiers: list[str] | None, theme: str, audience: str, constraints: list[str], model: str, transport=None) -> dict:
        from .provider import evaluate
        with self.lock():
            selected = self.selected(identifiers)
            review = evaluate(selected, theme, audience, constraints, model, transport=transport)
            manifest = self.manifest()
            review.update({"id": "review-%03d" % (len(manifest["reviews"]) + 1), "theme": theme, "audience": audience,
                           "constraints": constraints, "model": model, "created_at": now(),
                           "capture_ids": [entry["id"] for entry in selected],
                           "capture_hashes": {entry["id"]: entry["sha256"] for entry in selected}})
            manifest["reviews"].append(review)
            write_json(self.manifest_path, manifest)
            self.trace("evaluate", {"review_id": review["id"], "capture_ids": review["capture_ids"], "model": model})
            return review

    def import_review(self, document: dict, identifiers: list[str], theme: str, audience: str, constraints: list[str]) -> dict:
        from .provider import validate_evaluation
        if not theme.strip() or not audience.strip():
            raise LoopError("Provide both theme and audience")
        with self.lock():
            selected = self.selected(identifiers)
            review = validate_evaluation(document, [entry["id"] for entry in selected])
            manifest = self.manifest()
            review.update({"id": "review-%03d" % (len(manifest["reviews"]) + 1), "theme": theme, "audience": audience,
                           "constraints": constraints, "model": "external-agent", "created_at": now(),
                           "capture_ids": [entry["id"] for entry in selected],
                           "capture_hashes": {entry["id"]: entry["sha256"] for entry in selected}})
            manifest["reviews"].append(review)
            write_json(self.manifest_path, manifest)
            self.trace("import_review", {"review_id": review["id"], "capture_ids": review["capture_ids"]})
            return review

    def generate(self, capture_id: str, review_id: str, model: str, transport=None) -> dict:
        from .provider import generate
        with self.lock():
            manifest = self.manifest()
            review = next((item for item in manifest["reviews"] if item["id"] == review_id), None)
            if review is None or capture_id not in review["capture_ids"]:
                raise LoopError("Choose a reviewed capture and an existing review ID")
            prompt = next(item["prompt"] for item in review["prompts"] if item["capture_id"] == capture_id)
            order = [capture_id] + [identifier for identifier in review["capture_ids"] if identifier != capture_id]
            references = self.selected(order)
            if any(entry["sha256"] != review["capture_hashes"][entry["id"]] for entry in references):
                raise LoopError("Review references no longer match the captured evidence")
            result = generate([entry["image_path"] for entry in references],
                              prompt, model, transport=transport)
            return self._proposal(capture_id, result["image_bytes"], prompt, "openai", model, review_id,
                                  {key: result[key] for key in ("request_id", "usage") if key in result})

    def import_proposal(self, capture_id: str, image: str | Path, prompt: str, review_id: str = "") -> dict:
        with self.lock():
            if review_id:
                review = next((item for item in self.manifest()["reviews"] if item["id"] == review_id), None)
                if review is None or capture_id not in review["capture_ids"]:
                    raise LoopError("Choose a reviewed capture and an existing review ID")
                if any(entry["sha256"] != review["capture_hashes"][entry["id"]]
                       for entry in self.selected(review["capture_ids"])):
                    raise LoopError("Review references no longer match the captured evidence")
            return self._proposal(capture_id, Path(image).read_bytes(), prompt, "external", "", review_id, {})

    def _proposal(self, capture_id: str, image: bytes, prompt: str, provider: str, model: str, review_id: str, metadata: dict) -> dict:
        manifest = self.manifest()
        if capture_id not in {entry["id"] for entry in manifest["captures"]}:
            raise LoopError("Unknown capture ID")
        if len(image) > 32 * 1024 * 1024 or not prompt.strip():
            raise LoopError("Provide a prompt and a PNG smaller than 32 MiB")
        identifier = "proposal-%03d" % (len(manifest["proposals"]) + 1)
        relative = "proposals/" + identifier + ".png"
        path = self.file(relative)
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(image)
        try:
            dimensions = png_size(path)
        except (OSError, LoopError):
            path.unlink(missing_ok=True)
            raise
        entry = {"id": identifier, "capture_id": capture_id, "file": relative, "prompt": prompt, "provider": provider,
                 "model": model, "review_id": review_id, "created_at": now(), "sha256": sha256(path),
                 "image_size": dimensions, **metadata}
        manifest["proposals"].append(entry)
        write_json(self.manifest_path, manifest)
        self.trace("proposal", {"proposal_id": identifier, "capture_id": capture_id, "provider": provider})
        return entry

    def stop(self) -> dict:
        with self.lock():
            result = self.request("stop")
            (self.root / "device.json").unlink(missing_ok=True)
            self.trace("stop", {})
            return result


def initialize(directory: str | Path, project_name: str, expected_states: list[str] | None = None) -> Session:
    session = Session(directory)
    if session.root.exists() and any(session.root.iterdir()):
        raise LoopError("Session directory is not empty; use a new directory")
    expected = expected_states or []
    if len(expected) != len(set(expected)) or any(slug(item) != item for item in expected):
        raise LoopError("Expected state IDs must be unique lowercase slugs")
    session.root.mkdir(parents=True, exist_ok=True)
    (session.root / "captures").mkdir()
    write_json(session.manifest_path, {"schema_version": 1, "session_id": uuid.uuid4().hex,
        "project_name": project_name, "created_at": now(),
        "registered_states": [{"id": item, "title": item} for item in expected],
        "captures": [], "reviews": [], "proposals": []})
    return session


def launch(app: str, directory: str | Path, platform: str, target: str,
           expected_states: list[str] | None = None) -> dict:
    if platform not in ("android", "ios") or not target.strip() or not app.strip():
        raise LoopError("Provide app ID, android/ios platform, and an explicit device serial/UDID")
    session = initialize(directory, app, expected_states)
    manifest = session.manifest()
    config = {"directory": str(session.root), "platform": platform, "target": target,
              "app": app, "session": "ui-loop-" + manifest["session_id"][:12]}
    write_json(session.root / "device.json", config, private=True)
    try:
        opened = session.request("open")
    except (LoopError, OSError):
        write_json(session.root / "launch-status.json", {"status": "failed", "dispatch_outcome": "unknown"})
        raise
    session.trace("open", {"platform": platform, "app": app, "target": target})
    return {"session": str(session.root), "device": {"platform": platform, "target": target}, "opened": opened}
