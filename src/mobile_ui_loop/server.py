"""Read-only loopback viewer. Session credentials are never HTTP resources."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import urllib.parse

from .session import LoopError, Session


def make_server(session: Session, port: int = 0) -> ThreadingHTTPServer:
    web = Path(__file__).parent / "web"

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            # Cross-origin websites cannot read local captures through this viewer.
            host = self.headers.get("Host", "")
            allowed_hosts = {"127.0.0.1:%d" % self.server.server_port, "localhost:%d" % self.server.server_port}
            origin = self.headers.get("Origin")
            if host not in allowed_hosts or (origin and origin not in {"http://" + item for item in allowed_hosts}):
                self.send_error(403, "Local viewer requests only")
                return
            path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
            content_type = "application/json; charset=utf-8"
            try:
                if path == "/api/session":
                    manifest = session.manifest()
                    manifest["coverage"] = session.coverage()
                    body = json.dumps(manifest, ensure_ascii=False).encode()
                elif path in ("/", "/index.html", "/app.js", "/styles.css"):
                    name = "index.html" if path == "/" else path[1:]
                    body = (web / name).read_bytes()
                    content_type = {"index.html": "text/html; charset=utf-8", "app.js": "text/javascript; charset=utf-8", "styles.css": "text/css; charset=utf-8"}[name]
                elif path.startswith("/files/"):
                    relative = path[len("/files/"):]
                    if not re.fullmatch(r"(?:captures|proposals)/[a-z0-9][a-z0-9_-]{0,100}\.png", relative):
                        self.send_error(404)
                        return
                    manifest = session.manifest()
                    known = {entry["file"] for entry in manifest["captures"] + manifest["proposals"]}
                    if relative not in known:
                        self.send_error(404)
                        return
                    body = session.file(relative).read_bytes()
                    content_type = "image/png"
                else:
                    self.send_error(404)
                    return
            except (OSError, LoopError):
                self.send_error(404, "Resource unavailable")
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)
