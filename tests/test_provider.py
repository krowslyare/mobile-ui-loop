import base64
import copy
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

from mobile_ui_loop import provider


def png(red):
    def chunk(name, data):
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes((0, red, 64, 128)))) + chunk(b"IEND", b""))


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.paths = [Path(self.directory.name) / "home.png", Path(self.directory.name) / "loading.png"]
        for index, path in enumerate(self.paths):
            path.write_bytes(png(index * 64))
        self.captures = [{
            "id": identity,
            "title": title,
            "state_id": state,
            "description": "Captured in the original mobile demo",
            "image_path": path,
            "controls": [{"type": "Button", "text": "Continue", "visible": True}],
        } for identity, title, state, path in zip(
            ("capture-home", "capture-loading"), ("Home", "Loading"), ("home", "loading"), self.paths)]
        self.review = {
            "summary": "The selected screens can share a stronger hierarchy.",
            "observations": [{"capture_id": "capture-home", "issue": "The primary action blends into the surface.",
                              "suggestion": "Increase its visual prominence with the shared accent."}],
            "direction": {"name": "Warm trails", "palette": ["#203527", "#F5EEDD", "#E2A24C"],
                          "typography": "Readable rounded sans serif", "principles": ["One primary action per state"]},
            "prompts": [{"capture_id": capture["id"], "prompt": "Improve the first reference screen using warm green and amber, preserving its visible actions."}
                        for capture in self.captures],
        }

    def evaluate(self, review=None, transport=None):
        if transport is None:
            transport = lambda *_args: {"status": "completed", "output": [{"type": "message", "content": [
                {"type": "output_text", "text": json.dumps(self.review if review is None else review)},
            ]}]}
        return provider.evaluate(self.captures, "A nature exploration game", "Casual mobile players",
                                 ["Portrait layout", "Preserve every action"], "vision-test-model", transport)

    def test_review_sends_all_images_with_identity_and_thematic_context(self):
        calls = []

        def fake(method, url, headers, body):
            calls.append((method, url, headers, json.loads(body)))
            return {"status": "completed", "output_text": json.dumps(self.review)}

        # A fake request must never read an ambient real key or touch HTTP.
        with mock.patch.object(provider.os.environ, "get", side_effect=AssertionError("environment access")), \
             mock.patch.object(provider.urllib.request, "build_opener", side_effect=AssertionError("network access")):
            self.assertEqual(self.evaluate(transport=fake), self.review)
        self.assertEqual(len(calls), 1)
        method, url, headers, body = calls[0]
        self.assertEqual((method, url), ("POST", provider.RESPONSES_URL))
        self.assertNotIn("Authorization", headers)
        self.assertFalse(body["store"])
        self.assertEqual(body["model"], "vision-test-model")
        self.assertEqual(body["text"]["format"]["type"], "json_schema")
        self.assertTrue(body["text"]["format"]["strict"])
        schema = body["text"]["format"]["schema"]
        self.assertEqual(schema["properties"]["prompts"]["items"]["properties"]["capture_id"]["enum"],
                         [capture["id"] for capture in self.captures])
        content = body["input"][0]["content"]
        image_inputs = [item for item in content if item["type"] == "input_image"]
        self.assertEqual(len(image_inputs), 2)
        for image_input, path in zip(image_inputs, self.paths):
            data_url = image_input["image_url"]
            self.assertTrue(data_url.startswith("data:image/png;base64,"))
            self.assertEqual(base64.b64decode(data_url.split(",", 1)[1]), path.read_bytes())
        text_inputs = "\n".join(item["text"] for item in content if item["type"] == "input_text")
        for value in ("A nature exploration game", "Casual mobile players", "Portrait layout", "Continue", "capture-loading"):
            self.assertIn(value, text_inputs)
        self.assertNotIn(self.directory.name, text_inputs)

    def test_unseen_capture_cannot_become_an_observation(self):
        review = copy.deepcopy(self.review)
        review["observations"][0]["capture_id"] = "invented-settings-screen"
        with self.assertRaisesRegex(provider.ProviderError, "outside the selected evidence"):
            self.evaluate(review)

    def test_review_keeps_screenshot_and_later_semantic_metadata_distinguishable(self):
        self.captures[0].update({"kind": "observed", "image_size": [1, 1], "snapshot": {
            "viewport": [390, 844], "metadata_timing": "snapshot captured after screenshot"}})
        self.captures[1].update({"kind": "imported", "image_size": [1, 1], "snapshot": {
            "metadata_timing": "external capture; original time unknown"}})
        calls = []

        def fake(_method, _url, _headers, body):
            calls.append(json.loads(body))
            return {"output_text": json.dumps(self.review)}

        self.evaluate(transport=fake)
        references = [json.loads(item["text"].removeprefix("Reference map: "))
                      for item in calls[0]["input"][0]["content"]
                      if item["type"] == "input_text" and item["text"].startswith("Reference map: ")]
        self.assertEqual(references[0]["capture_id"], self.captures[0]["id"])
        self.assertEqual(references[0]["provenance"], {"kind": "observed", "image_size": [1, 1],
                         "semantic_viewport": [390, 844], "metadata_timing": "snapshot captured after screenshot"})
        self.assertEqual(references[1]["provenance"], {"kind": "imported", "image_size": [1, 1],
                         "semantic_viewport": None, "metadata_timing": "external capture; original time unknown"})

    def test_prompt_provenance_covers_each_capture_once(self):
        mutations = []
        missing = copy.deepcopy(self.review)
        missing["prompts"].pop()
        mutations.append(missing)
        repeated = copy.deepcopy(self.review)
        repeated["prompts"][1]["capture_id"] = "capture-home"
        mutations.append(repeated)
        ungrounded = copy.deepcopy(self.review)
        del ungrounded["prompts"][0]["capture_id"]
        mutations.append(ungrounded)
        for review in mutations:
            with self.subTest(review=review), self.assertRaises(provider.ProviderError):
                self.evaluate(review)

    def test_invalid_output_is_rejected_without_leaking_response(self):
        outputs = (
            {"output_text": "provider-secret-contents"},
            {"status": "incomplete", "output_text": json.dumps(self.review)},
            {"output": [{"content": [{"type": "refusal", "refusal": "provider-secret-contents"}]}]},
            {"error": {"message": "provider-secret-contents"}},
        )
        for output in outputs:
            with self.subTest(output=output), self.assertRaises(provider.ProviderError) as caught:
                self.evaluate(transport=lambda *_args: output)
            self.assertNotIn("provider-secret-contents", str(caught.exception))

    def test_context_and_prompt_limits_fail_before_dispatch(self):
        fake = mock.Mock()
        for captures in ([self.captures[0]], self.captures * 9):
            with self.subTest(count=len(captures)), self.assertRaisesRegex(provider.ProviderError, "2 to 16"):
                provider.evaluate(captures, "Game", "Players", [], "vision-test-model", fake)
        self.assertEqual(fake.call_count, 0)
        review = copy.deepcopy(self.review)
        review["prompts"][0]["prompt"] = "a" * (provider.MAX_PROMPT_CHARACTERS + 1)
        with self.assertRaisesRegex(provider.ProviderError, "at most"):
            self.evaluate(review)

    def test_duplicate_capture_ids_fail_before_dispatch(self):
        fake = mock.Mock()
        self.captures[1]["id"] = self.captures[0]["id"]
        with self.assertRaisesRegex(provider.ProviderError, "unique"):
            self.evaluate(transport=fake)
        fake.assert_not_called()

    def test_edit_uploads_multiple_local_references_target_first(self):
        generated = png(255)
        calls = []

        def fake(method, url, headers, body):
            calls.append((method, url, headers, body))
            return {"data": [{"b64_json": base64.b64encode(generated).decode("ascii")}],
                    "_request_id": "req_test123", "usage": {"total_tokens": 10, "unknown": "discard me"}}

        with mock.patch.object(provider.os.environ, "get", side_effect=AssertionError("environment access")), \
             mock.patch.object(provider.urllib.request, "build_opener", side_effect=AssertionError("network access")):
            result = provider.generate(self.paths, "Use the first image as target and the second for context", "image-test-model", fake)
        self.assertEqual(result, {"image_bytes": generated, "model": "image-test-model", "request_id": "req_test123",
                                  "usage": {"total_tokens": 10}})
        self.assertEqual(len(calls), 1)
        method, url, headers, body = calls[0]
        self.assertEqual((method, url), ("POST", provider.EDITS_URL))
        self.assertNotIn("Authorization", headers)
        self.assertIn("multipart/form-data; boundary=", headers["Content-Type"])
        self.assertEqual(body.count(b'name="image[]"'), 2)
        self.assertIn(b'name="output_format"\r\n\r\npng\r\n', body)
        self.assertIn(b'name="n"\r\n\r\n1\r\n', body)
        self.assertIn(b'name="model"\r\n\r\nimage-test-model\r\n', body)
        self.assertLess(body.index(self.paths[0].read_bytes()), body.index(self.paths[1].read_bytes()))
        self.assertNotIn(self.directory.name.encode("utf-8"), body)

    def test_edit_rejects_invalid_base64_and_does_not_fetch_provider_urls(self):
        fake = mock.Mock(return_value={"data": [{"url": "https://invalid.example/private-result"}]})
        with mock.patch.object(provider.urllib.request, "build_opener", side_effect=AssertionError("network access")), \
             self.assertRaises(provider.ProviderError):
            provider.generate(self.paths, "Preserve the actions", "image-test-model", fake)
        fake.assert_called_once()
        for encoded in ("not-base64!", base64.b64encode(b"not an image").decode("ascii")):
            with self.subTest(encoded=encoded), self.assertRaises(provider.ProviderError):
                provider.generate(self.paths, "Preserve the actions", "image-test-model",
                                  lambda *_args: {"data": [{"b64_json": encoded}]})

    def test_reference_and_output_sizes_are_bounded(self):
        fake = mock.Mock()
        with mock.patch.object(provider, "MAX_IMAGE_BYTES", 4), self.assertRaisesRegex(provider.ProviderError, "input limit"):
            provider.generate(self.paths, "Preserve the actions", "image-test-model", fake)
        fake.assert_not_called()
        with mock.patch.object(provider, "MAX_TOTAL_INPUT_BYTES", len(self.paths[0].read_bytes())), \
             self.assertRaisesRegex(provider.ProviderError, "combined input limit"):
            provider.generate(self.paths, "Preserve the actions", "image-test-model", fake)
        with mock.patch.object(provider, "MAX_IMAGE_BYTES", 100), self.assertRaisesRegex(provider.ProviderError, "output limit"):
            provider.generate(self.paths, "Preserve the actions", "image-test-model",
                              lambda *_args: {"data": [{"b64_json": "A" * 200}]})

    def test_dispatch_errors_are_redacted_and_never_retried(self):
        fake = mock.Mock(side_effect=RuntimeError("Authorization: Bearer secret-provider-body"))
        with self.assertRaisesRegex(provider.ProviderError, "no automatic retry") as caught:
            provider.generate(self.paths, "Preserve the actions", "image-test-model", fake)
        fake.assert_called_once()
        self.assertNotIn("secret-provider-body", str(caught.exception))

    def test_default_dispatch_requires_key_and_sanitizes_http_errors(self):
        with mock.patch.object(provider.os.environ, "get", return_value=None), \
             mock.patch.object(provider.urllib.request, "build_opener") as network, \
             self.assertRaisesRegex(provider.ProviderError, "set OPENAI_API_KEY"):
            provider.generate(self.paths, "Preserve the actions", "image-test-model")
        network.assert_not_called()
        error = provider.urllib.error.HTTPError(provider.EDITS_URL, 429, "secret token", {}, None)
        opener = mock.Mock()
        opener.open.side_effect = error
        with mock.patch.object(provider.os.environ, "get", return_value="fake-test-token"), \
             mock.patch.object(provider.urllib.request, "build_opener", return_value=opener), \
             self.assertRaisesRegex(provider.ProviderError, "HTTP 429") as caught:
            provider.generate(self.paths, "Preserve the actions", "image-test-model")
        self.assertNotIn("secret token", str(caught.exception))
        self.assertNotIn("fake-test-token", str(caught.exception))
        opener.open.assert_called_once()


if __name__ == "__main__":
    unittest.main()
