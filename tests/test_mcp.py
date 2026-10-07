import base64
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from mobile_ui_loop import mcp
from mobile_ui_loop.provider import ProviderError
from mobile_ui_loop.session import initialize


class MCPTests(unittest.TestCase):
    def setUp(self):
        self.session = mock.Mock()
        self.session.manifest.return_value = {"captures": [], "reviews": []}
        self.session.inspect.return_value = {"viewport": [390, 844], "nodes": []}

    def call(self, name, arguments=None):
        return mcp.handle(self.session, {"jsonrpc": "2.0", "id": 17, "method": "tools/call", "params": {
            "name": name, "arguments": {} if arguments is None else arguments,
        }})

    def test_initialization_negotiates_protocol_and_exposes_tools(self):
        initialized = mcp.handle(self.session, {"jsonrpc": "2.0", "id": "init", "method": "initialize", "params": {
            "protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "test-agent", "version": "1"},
        }})
        self.assertEqual(initialized["id"], "init")
        self.assertEqual(initialized["result"]["protocolVersion"], "2025-03-26")
        self.assertIn("tools", initialized["result"]["capabilities"])
        listing = mcp.handle(self.session, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        by_name = {tool["name"]: tool for tool in listing["result"]["tools"]}
        self.assertIn("inspect_app", by_name)
        for name in ("evaluate_collection", "generate_proposal"):
            self.assertTrue(by_name[name]["annotations"]["openWorldHint"])
            self.assertIn("API", by_name[name]["description"])
        self.session.inspect.assert_not_called()

    def test_unknown_and_invalid_arguments_never_dispatch(self):
        invalid_calls = (
            ("execute_shell", {}),
            (None, {}),
            (["inspect_app"], {}),
            ("inspect_app", {"command": "delete-everything"}),
            ("evaluate_collection", {"theme": "Game", "audience": "Players"}),
            ("evaluate_collection", {"theme": "Game", "audience": "Players", "model": "test", "capture_ids": ["home", "home"]}),
            ("evaluate_collection", {"theme": "Game", "audience": "Players", "model": "test", "capture_ids": list(range(2))}),
            ("inspect_app", []),
            ("record_review", {"document": [], "capture_ids": ["home", "loading"], "theme": "Game", "audience": "Players"}),
            ("record_review", {"document": None, "capture_ids": ["home", "loading"], "theme": "Game", "audience": "Players"}),
        )
        for name, arguments in invalid_calls:
            with self.subTest(name=name, arguments=arguments):
                response = self.call(name, arguments)
                self.assertTrue(response["result"]["isError"])
                self.assertEqual(response["id"], 17)
        self.session.inspect.assert_not_called()
        self.session.evaluate.assert_not_called()
        self.session.import_review.assert_not_called()

    def test_external_review_and_proposal_cycle_preserves_evidence_and_rejects_foreign_reviews(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "generated.png"
            image = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")
            source.write_bytes(image)
            self.session = initialize(Path(directory) / "session", "Original trail demo")
            captures = [self.session.import_capture(source, name) for name in ("home", "loading", "modal")]
            identifiers = [capture["id"] for capture in captures[:2]]
            document = {"summary": "A consistent direction for the selected screens.", "observations": [],
                        "direction": {"name": "Warm trails", "palette": ["#153820"], "typography": "Readable sans serif",
                                      "principles": ["One primary action"]},
                        "prompts": [{"capture_id": identifier, "prompt": "Preserve the visible actions in image 1."}
                                    for identifier in identifiers]}
            with mock.patch("mobile_ui_loop.provider._dispatch", side_effect=AssertionError("provider dispatch")), \
                 mock.patch("mobile_ui_loop.session.subprocess.run", side_effect=AssertionError("device dispatch")):
                response = self.call("record_review", {"document": document, "capture_ids": identifiers,
                                     "theme": "Nature exploration", "audience": "Mobile players"})
                self.assertFalse(response["result"]["isError"])
                review = json.loads(response["result"]["content"][0]["text"])
                self.assertEqual(review["capture_ids"], identifiers)
                self.assertEqual(review["capture_hashes"], {capture["id"]: capture["sha256"] for capture in captures[:2]})
                self.assertEqual(self.session.manifest()["reviews"], [review])
                for capture_id, review_id in ((captures[2]["id"], review["id"]), (captures[0]["id"], "review-other-session")):
                    with self.subTest(capture_id=capture_id, review_id=review_id):
                        rejected = self.call("record_proposal", {"capture_id": capture_id, "image_path": str(source),
                                             "prompt": "Preserve the visible actions.", "review_id": review_id})
                        self.assertTrue(rejected["result"]["isError"])
                        self.assertEqual(self.session.manifest()["proposals"], [])
                response = self.call("record_proposal", {"capture_id": identifiers[0], "image_path": str(source),
                                     "prompt": document["prompts"][0]["prompt"], "review_id": review["id"]})
            self.assertFalse(response["result"]["isError"])
            proposal = json.loads(response["result"]["content"][0]["text"])
            self.assertEqual(proposal["capture_id"], identifiers[0])
            self.assertEqual(proposal["review_id"], review["id"])
            self.assertEqual(proposal["provider"], "external")
            self.assertEqual(proposal["prompt"], document["prompts"][0]["prompt"])
            self.assertEqual(base64.b64decode(response["result"]["content"][1]["data"]), image)
            self.assertEqual(self.session.manifest()["proposals"], [proposal])

    def test_protocol_errors_and_notifications_stay_separate_from_tools(self):
        for request in ([], {"jsonrpc": "1.0", "id": 1, "method": "ping"}):
            with self.subTest(request=request):
                self.assertEqual(mcp.handle(self.session, request)["error"]["code"], -32600)
        params_error = mcp.handle(self.session, {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": []})
        self.assertEqual(params_error["error"]["code"], -32602)
        method_error = mcp.handle(self.session, {"jsonrpc": "2.0", "id": 2, "method": "invented/method"})
        self.assertEqual(method_error["error"]["code"], -32601)
        self.assertIsNone(mcp.handle(self.session, {"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_stdio_parse_errors_do_not_corrupt_the_following_request(self):
        source = io.StringIO("{broken-json\n" + json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
                             + json.dumps({"jsonrpc": "2.0", "id": "ping", "method": "ping"}) + "\n")
        destination = io.StringIO()
        mcp.serve(self.session, source, destination)
        messages = [json.loads(line) for line in destination.getvalue().splitlines()]
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["error"]["code"], -32700)
        self.assertEqual(messages[1], {"jsonrpc": "2.0", "id": "ping", "result": {}})

    def test_provider_failure_is_an_mcp_tool_error(self):
        self.session.evaluate.side_effect = ProviderError("OpenAI request failed with HTTP 429; no automatic retry was made")
        response = self.call("evaluate_collection", {"theme": "Game", "audience": "Players", "model": "test-model"})
        self.assertTrue(response["result"]["isError"])
        self.assertIn("HTTP 429", response["result"]["content"][0]["text"])
        self.session.evaluate.assert_called_once()

    def test_read_capture_returns_png_and_grounding_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "home.png"
            image = b"test-image-evidence"
            path.write_bytes(image)
            self.session.selected.return_value = [{"id": "capture-home", "state_id": "home", "kind": "observed",
                                                   "description": "Menu after launch", "image_path": path}]
            response = self.call("read_capture", {"capture_id": "capture-home"})
        content = response["result"]["content"]
        metadata = json.loads(content[0]["text"])
        self.assertEqual(metadata["id"], "capture-home")
        self.assertEqual(metadata["kind"], "observed")
        self.assertNotIn("image_path", metadata)
        self.assertEqual(base64.b64decode(content[1]["data"]), image)
        self.session.selected.assert_called_once_with(["capture-home"], minimum=1)


if __name__ == "__main__":
    unittest.main()
