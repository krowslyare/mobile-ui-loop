import base64
import copy
import io
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock
import zlib

from mobile_ui_loop.provider import MAX_PROMPT_CHARACTERS, ProviderError
from mobile_ui_loop.session import LoopError, initialize, sha256, write_json


def png(red):
    def chunk(name, data):
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes((0, red, 128, 64)))) + chunk(b"IEND", b""))


class SessionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name).resolve()
        self.session = initialize(self.directory / "session", "Original trail demo", ["home", "loading", "error"])
        self.source = self.directory / "source.png"

    def add_capture(self, label, red=10, state_id=""):
        self.source.write_bytes(png(red))
        return self.session.import_capture(self.source, label, "Manually exported from a device", state_id=state_id)

    def seed_collection(self):
        home = self.add_capture("home", 10)
        loading = self.add_capture("loading", 20)
        manifest = self.session.manifest()
        manifest["captures"][0]["snapshot"]["controls"] = [{"type": "Button", "text": "Explore trail"}]
        write_json(self.session.manifest_path, manifest)
        return home, loading

    def review(self, identifiers):
        return {
            "summary": "A shared visual language can improve the selected states.",
            "observations": [{"capture_id": identifiers[0], "issue": "The primary action is visually weak.",
                              "suggestion": "Give it a warmer accent color."}],
            "direction": {"name": "Warm trails", "palette": ["#153820", "#F3EDDB"], "typography": "Readable sans serif",
                          "principles": ["A clear primary action"]},
            "prompts": [{"capture_id": identifier, "prompt": "Redesign image 1 with warm green surfaces, preserving this state's visible content."}
                        for identifier in identifiers],
        }

    def evaluate(self, entries):
        identifiers = [entry["id"] for entry in entries]
        return self.session.evaluate(identifiers, "Nature exploration", "Casual mobile players", ["Keep actions"], "vision-test",
                                     lambda *_args: {"output_text": json.dumps(self.review(identifiers))})

    def test_initialize_preserves_existing_work_and_validates_expected_inventory(self):
        existing = self.directory / "existing"
        existing.mkdir()
        (existing / "keep.txt").write_text("unrelated work")
        with self.assertRaisesRegex(LoopError, "not empty"):
            initialize(existing, "Demo")
        self.assertEqual((existing / "keep.txt").read_text(), "unrelated work")
        for states in (["home", "home"], ["Home"], ["../escape"]):
            path = self.directory / "invalid"
            with self.subTest(states=states), self.assertRaises(LoopError):
                initialize(path, "Demo", states)
            self.assertFalse(path.exists())

    def test_file_paths_and_symlinks_cannot_escape_the_session(self):
        outside = self.directory / "outside.png"
        outside.write_bytes(png(30))
        for relative in ("../outside.png", str(outside)):
            with self.subTest(relative=relative), self.assertRaisesRegex(LoopError, "escapes"):
                self.session.file(relative)
        (self.session.root / "captures/link.png").symlink_to(outside)
        with self.assertRaisesRegex(LoopError, "escapes"):
            self.session.file("captures/link.png")
        self.assertEqual(self.session.file("captures/home.png"), self.session.root / "captures/home.png")

    def test_capture_records_runtime_evidence_without_inventing_snapshot_agreement(self):
        def runtime(method, **params):
            self.assertEqual(method, "capture")
            relative = "captures/" + params["filename"]
            self.session.file(relative).write_bytes(png(40))
            return {"file": relative, "snapshot": {"viewport": [390, 844], "nodes": [],
                    "metadata_timing": "snapshot captured after screenshot"}, "runtime": {"backend": "agent-device"}}

        with mock.patch.object(self.session, "request", side_effect=runtime):
            entry = self.session.capture("Loader", "Shown while a level is loading", state_id="loading", title="Loading trail")
        self.assertEqual(entry["state_id"], "loading")
        self.assertEqual(entry["title"], "Loading trail")
        self.assertEqual(entry["kind"], "observed")
        self.assertEqual(entry["image_size"], [1, 1])
        self.assertEqual(entry["snapshot"]["viewport"], [390, 844])
        self.assertEqual(entry["snapshot"]["image_viewport"], [1, 1])
        self.assertEqual(entry["snapshot"]["metadata_timing"], "snapshot captured after screenshot")
        self.assertEqual(entry["sha256"], sha256(self.session.file(entry["file"])))
        self.assertEqual(self.session.manifest()["captures"], [entry])

    def test_runtime_cannot_register_an_unexpected_capture_path(self):
        with mock.patch.object(self.session, "request", return_value={"file": "../outside.png", "snapshot": {}}), \
             self.assertRaisesRegex(LoopError, "unexpected capture path"):
            self.session.capture("home")
        self.assertEqual(self.session.manifest()["captures"], [])

    def test_device_dispatch_ignores_ambient_remote_settings_and_keeps_keys_private(self):
        write_json(self.session.root / "device.json", {"session": "local-test", "platform": "android", "target": "emulator-5560"})
        ambient = {"AGENT_DEVICE_DAEMON_BASE_URL": "https://unrelated.example",
                   "AGENT_DEVICE_AUTH_TOKEN": "unrelated-device-token", "AGENT_DEVICE_SESSION": "unrelated-session",
                   "OPENAI_API_KEY": "fake-private-openai-token"}
        calls = []

        def runtime(_command, **arguments):
            calls.append(arguments)
            return mock.Mock(stdout=json.dumps({"ok": True, "result": {"nodes": []}}),
                             stderr="fake-private-openai-token")

        with mock.patch.dict(os.environ, ambient), \
             mock.patch("mobile_ui_loop.session.subprocess.run", side_effect=runtime), \
             mock.patch("sys.stdout", new_callable=io.StringIO) as output, \
             mock.patch("sys.stderr", new_callable=io.StringIO) as errors:
            result = self.session.request("inspect")
            self.assertEqual(os.environ["OPENAI_API_KEY"], ambient["OPENAI_API_KEY"])
        self.assertEqual(result, {"nodes": []})
        self.assertEqual(len(calls), 1)
        child_environment = calls[0]["env"]
        self.assertEqual({key: value for key, value in child_environment.items() if key.startswith("AGENT_DEVICE_")},
                         {"AGENT_DEVICE_NO_UPDATE_NOTIFIER": "1"})
        self.assertNotIn("OPENAI_API_KEY", child_environment)
        self.assertTrue(calls[0]["capture_output"])
        for secret in (ambient["OPENAI_API_KEY"], ambient["AGENT_DEVICE_AUTH_TOKEN"]):
            self.assertNotIn(secret, output.getvalue() + errors.getvalue() + json.dumps(result))

    def test_imported_evidence_has_explicit_external_provenance_and_missing_coverage(self):
        self.add_capture("Home", state_id="home")
        self.add_capture("unlisted-result", 20)
        manifest = self.session.manifest()
        self.assertEqual(manifest["captures"][0]["kind"], "imported")
        self.assertIn("unknown", manifest["captures"][0]["snapshot"]["metadata_timing"])
        coverage = self.session.coverage()
        self.assertEqual(coverage["registered"], ["home", "loading", "error"])
        self.assertEqual(coverage["captured"], ["home"])
        self.assertEqual(coverage["missing"], ["loading", "error"])
        self.assertIn("unvisited", coverage["scope"])
        self.assertIn("unknown", coverage["scope"])

    def test_selected_requires_multiple_explicit_valid_captures_and_checks_hashes(self):
        entries = self.seed_collection()
        for identifiers in ([entries[0]["id"]], [entries[0]["id"], entries[0]["id"]], [entries[0]["id"], "unknown"]):
            with self.subTest(identifiers=identifiers), self.assertRaises(LoopError):
                self.session.selected(identifiers)
        selected = self.session.selected()
        self.assertTrue(all(entry["image_path"].is_absolute() for entry in selected))
        self.session.file(entries[0]["file"]).write_bytes(png(99))
        with self.assertRaisesRegex(LoopError, "changed after collection"):
            self.session.selected()

    def test_context_never_silently_drops_the_seventeenth_capture(self):
        for index in range(17):
            self.add_capture("state-" + str(index), index)
        with self.assertRaisesRegex(LoopError, "16 captures"):
            self.session.selected()
        self.assertEqual(len(self.session.selected([entry["id"] for entry in self.session.manifest()["captures"][:2]])), 2)

    def test_bundle_copies_selected_evidence_and_reports_exclusions(self):
        entries = self.seed_collection()
        excluded = self.add_capture("error", 30)
        target = self.directory / "review-bundle"
        result = self.session.bundle(target, [entry["id"] for entry in entries], "Nature exploration", "Players", ["Keep portrait"])
        bundle = json.loads((target / "bundle.json").read_text())
        self.assertEqual(result["references"], 2)
        self.assertEqual(bundle["excluded_capture_ids"], [excluded["id"]])
        self.assertEqual(bundle["references"][0]["controls"][0]["text"], "Explore trail")
        for reference in bundle["references"]:
            self.assertEqual(sha256(target / reference["file"]), reference["sha256"])
            self.assertEqual(reference["kind"], "imported")
        brief = (target / "brief.md").read_text()
        self.assertIn("design proposals", brief)
        self.assertIn("Keep portrait", brief)
        with self.assertRaisesRegex(LoopError, "already exists"):
            self.session.bundle(target, None, "Nature exploration", "Players", [])

    def test_review_persists_exact_evidence_and_sends_control_metadata(self):
        entries = self.seed_collection()
        identifiers = [entry["id"] for entry in entries]
        calls = []

        def fake(_method, _url, _headers, body):
            calls.append(json.loads(body))
            return {"output_text": json.dumps(self.review(identifiers))}

        review = self.session.evaluate(identifiers, "Nature exploration", "Players", ["Keep actions"], "vision-test", fake)
        self.assertEqual(review["capture_ids"], identifiers)
        self.assertEqual(review["capture_hashes"], {entry["id"]: entry["sha256"] for entry in entries})
        self.assertEqual(self.session.manifest()["reviews"], [review])
        request_text = json.dumps(calls[0]["input"])
        self.assertIn("Explore trail", request_text)
        self.assertIn("Nature exploration", request_text)

    def test_invalid_review_is_never_persisted_as_design_evidence(self):
        entries = self.seed_collection()
        identifiers = [entry["id"] for entry in entries]
        review = copy.deepcopy(self.review(identifiers))
        review["observations"][0]["capture_id"] = "unobserved-secret-screen"
        with self.assertRaises(ProviderError):
            self.session.evaluate(identifiers, "Nature", "Players", [], "vision-test",
                                  lambda *_args: {"output_text": json.dumps(review)})
        self.assertEqual(self.session.manifest()["reviews"], [])
        self.assertFalse((self.session.root / ".operation.lock").exists())

    def test_generation_puts_target_first_and_persists_review_provenance(self):
        entries = self.seed_collection()
        review = self.evaluate(entries)
        generated = png(80)
        calls = []

        def fake(_method, _url, _headers, body):
            calls.append(body)
            return {"data": [{"b64_json": base64.b64encode(generated).decode("ascii")}], "_request_id": "req_proposal_test"}

        proposal = self.session.generate(entries[1]["id"], review["id"], "image-test", fake)
        body = calls[0]
        self.assertEqual(body.count(b'name="image[]"'), 2)
        self.assertLess(body.index(self.session.file(entries[1]["file"]).read_bytes()),
                        body.index(self.session.file(entries[0]["file"]).read_bytes()))
        self.assertEqual(proposal["capture_id"], entries[1]["id"])
        self.assertEqual(proposal["review_id"], review["id"])
        self.assertEqual(proposal["provider"], "openai")
        self.assertEqual(proposal["request_id"], "req_proposal_test")
        self.assertEqual(self.session.file(proposal["file"]).read_bytes(), generated)
        self.assertEqual(self.session.manifest()["proposals"], [proposal])

    def test_generation_rejects_replaced_review_evidence_even_if_manifest_hash_is_updated(self):
        entries = self.seed_collection()
        review = self.evaluate(entries)
        manifest = self.session.manifest()
        capture = manifest["captures"][0]
        self.session.file(capture["file"]).write_bytes(png(100))
        capture["sha256"] = sha256(self.session.file(capture["file"]))
        write_json(self.session.manifest_path, manifest)
        fake = mock.Mock()
        with self.assertRaisesRegex(LoopError, "no longer match"):
            self.session.generate(entries[1]["id"], review["id"], "image-test", fake)
        fake.assert_not_called()
        self.assertEqual(self.session.manifest()["proposals"], [])

    def test_maximum_valid_review_prompt_reaches_image_transport_unchanged(self):
        entries = self.seed_collection()
        identifiers = [entry["id"] for entry in entries]
        document = self.review(identifiers)
        prompt = "Preserve this state. " + "a" * (MAX_PROMPT_CHARACTERS - len("Preserve this state. "))
        document["prompts"][0]["prompt"] = prompt
        review = self.session.import_review(document, identifiers, "Nature", "Players", ["Keep actions"])
        bodies = []

        def fake(_method, _url, _headers, body):
            bodies.append(body)
            return {"data": [{"b64_json": base64.b64encode(png(80)).decode("ascii")}]}

        proposal = self.session.generate(identifiers[0], review["id"], "image-test", fake)
        self.assertEqual(len(bodies), 1)
        uploaded_prompt = bodies[0].split(b'name="prompt"\r\n\r\n', 1)[1].split(b"\r\n--", 1)[0].decode("utf-8")
        self.assertEqual(uploaded_prompt, prompt)
        self.assertEqual(proposal["prompt"], prompt)
        self.assertEqual(self.session.manifest()["proposals"], [proposal])

    def test_failed_generation_and_invalid_proposal_leave_no_success_record(self):
        entries = self.seed_collection()
        review = self.evaluate(entries)
        with self.assertRaises(ProviderError):
            self.session.generate(entries[0]["id"], review["id"], "image-test", lambda *_args: {"error": {"message": "failure"}})
        self.source.write_bytes(b"not a PNG")
        with self.assertRaises(LoopError):
            self.session.import_proposal(entries[0]["id"], self.source, "Preserve the actions")
        self.assertEqual(self.session.manifest()["proposals"], [])
        self.assertEqual(list((self.session.root / "proposals").glob("*.png")), [])

    def test_session_lock_prevents_simultaneous_mutations_and_releases_on_failure(self):
        with self.session.lock():
            with self.assertRaisesRegex(LoopError, "Another operation"):
                self.session.capture("home")
        self.assertFalse((self.session.root / ".operation.lock").exists())
        with mock.patch.object(self.session, "request", side_effect=LoopError("Device unavailable")), self.assertRaises(LoopError):
            self.session.capture("home")
        self.assertFalse((self.session.root / ".operation.lock").exists())


if __name__ == "__main__":
    unittest.main()
