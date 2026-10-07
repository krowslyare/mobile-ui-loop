import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

from mobile_ui_loop.server import make_server
from mobile_ui_loop.session import LoopError


class ViewerSession:
    def __init__(self, root):
        self.root = root
        self.image_file = "captures/home.png"

    def manifest(self):
        return {"schema_version": 1, "session_id": "viewer-test", "project_name": "Original demo",
                "captures": [{"id": "home", "file": self.image_file}], "proposals": [], "reviews": []}

    def coverage(self):
        return {"missing": ["loading"], "scope": "Expected states only; unvisited states are unknown."}

    def file(self, relative):
        result = (self.root / relative).resolve()
        if not result.is_relative_to(self.root):
            raise LoopError("Session file escapes its directory")
        return result


class ViewerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name).resolve()
        (root / "captures").mkdir()
        (root / "captures/home.png").write_bytes(b"original-png-evidence")
        (root / "connection.json").write_text('{"token":"private-session-token"}')
        (root / "launch.json").write_text('{"project":"private-local-project-path"}')
        (root / "device.json").write_text('{"session":"private-device-identity"}')
        self.session = ViewerSession(root)
        self.server = make_server(self.session)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()
        self.addCleanup(self.close)

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def get(self, path, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=2)
        try:
            connection.request("GET", path, headers={} if headers is None else headers)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_only_manifest_images_are_served_and_credentials_stay_private(self):
        status, headers, body = self.get("/files/captures/home.png")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"original-png-evidence")
        self.assertEqual(headers["Content-Type"], "image/png")
        for path in ("/connection.json", "/launch.json", "/device.json", "/files/connection.json", "/files/launch.json",
                     "/files/device.json", "/files/%2e%2e/connection.json", "/files/captures/missing.png"):
            with self.subTest(path=path):
                status, _headers, body = self.get(path)
                self.assertEqual(status, 404)
                self.assertNotIn(b"private-session-token", body)
                self.assertNotIn(b"private-local-project-path", body)

    def test_non_image_manifest_entry_cannot_expose_device_or_launch_configuration(self):
        for name in ("connection.json", "launch.json", "device.json"):
            with self.subTest(name=name):
                self.session.image_file = name
                status, _headers, body = self.get("/files/" + name)
                self.assertEqual(status, 404)
                self.assertNotIn(b"private-session-token", body)
                self.assertNotIn(b"private-local-project-path", body)
                self.assertNotIn(b"private-device-identity", body)

    def test_viewer_api_contains_evidence_and_truthful_coverage_only(self):
        status, headers, body = self.get("/api/session")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["captures"][0]["id"], "home")
        self.assertEqual(data["coverage"]["missing"], ["loading"])
        self.assertNotIn(b"private-session-token", body)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])

    def test_wrong_host_or_cross_origin_cannot_read_local_evidence(self):
        for headers in ({"Host": "attacker.example"}, {"Origin": "https://attacker.example"}, {"Origin": "null"}):
            with self.subTest(headers=headers):
                self.assertEqual(self.get("/api/session", headers)[0], 403)
        own_origin = "http://127.0.0.1:" + str(self.server.server_port)
        self.assertEqual(self.get("/api/session", {"Origin": own_origin})[0], 200)

    def test_manifest_cannot_make_a_symlink_escape_readable(self):
        with tempfile.TemporaryDirectory() as external_directory:
            outside = Path(external_directory) / "private.png"
            outside.write_bytes(b"outside-session-secret")
            (self.session.root / "captures/escape.png").symlink_to(outside)
            self.session.image_file = "captures/escape.png"
            status, _headers, body = self.get("/files/captures/escape.png")
        self.assertEqual(status, 404)
        self.assertNotIn(b"outside-session-secret", body)


if __name__ == "__main__":
    unittest.main()
