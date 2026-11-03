"""Run from the repository root with python -m viewer [--port 8765]."""

import argparse
import gzip
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from mimetypes import guess_type
from threading import Lock
from urllib.parse import parse_qs, urlsplit

from eml import Program
from eml.data import ROOT, Error, load, registry, schema, validator


def entries():
    result = {}
    for directory in ("exercises", "examples"):
        for path in sorted((ROOT / directory).glob("*.json")):
            doc = load(path)
            if (
                isinstance(doc, dict)
                and "eml" in doc
                and "id" in doc
                and "phases" in doc
            ):
                result[path.relative_to(ROOT).as_posix()] = {
                    "id": doc["id"],
                    "title": doc["title"],
                }
    return result


class PreviewServer(ThreadingHTTPServer):
    """Reload edited data definitions before compiling a contributor's recipe."""

    def __init__(self, address, fps):
        super().__init__(address, Viewer)
        self.fps = fps
        self.lock = Lock()
        self.signature = None

    def refresh_registry(self):
        files = sorted((ROOT / "library").glob("*.json")) + [
            ROOT / "schema/exercise-v1.schema.json",
            ROOT / "anatomy/model.json",
        ]
        signature = [(p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in files]
        with self.lock:
            if signature != self.signature:
                registry.cache_clear()
                validator.cache_clear()
                schema.cache_clear()
                self.signature = signature


class Viewer(BaseHTTPRequestHandler):
    def send(self, data, mime, status=200):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("X-Content-Type-Options", "nosniff")
        if mime == "application/json" and "gzip" in self.headers.get(
            "Accept-Encoding", ""
        ):
            data = gzip.compress(data, compresslevel=1)
            self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass  # The user may select another recipe before the first request completes.

    def json(self, value, status=200):
        self.send(
            json.dumps(value, allow_nan=False, separators=(",", ":")).encode(),
            "application/json",
            status,
        )

    def clip(self, doc, parameters=None):
        try:
            self.server.refresh_registry()
            program = Program(doc, parameters)
            if program.duration * self.server.fps + len(program.doc["phases"]) > 3600:
                return self.json(
                    {
                        "error": "Viewer preview exceeds 3,600 samples; lower --fps or shorten the cycle."
                    },
                    422,
                )
            self.json(program.compile(self.server.fps, strict=False))
        except (Error, TypeError, KeyError, ValueError) as error:
            self.json({"error": str(error)}, 422)

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == "/api/catalog":
            self.json(entries())
        elif url.path in ("/api/clip", "/api/source"):
            entry = parse_qs(url.query).get("entry", [""])[0]
            if entry not in entries():
                return self.send_error(404)
            doc = load(ROOT / entry)
            if url.path == "/api/clip":
                self.clip(doc)
            else:
                self.json(doc)
        else:
            allowed = {
                "/": "viewer/index.html",
                "/index.html": "viewer/index.html",
                "/viewer.js": "viewer/viewer.js",
                "/mesh.js": "viewer/mesh.js",
                "/style.css": "viewer/style.css",
                "/anatomy/model.json": "anatomy/model.json",
                "/anatomy/indices.bin": "anatomy/indices.bin",
                "/anatomy/vertices.bin": "anatomy/vertices.bin",
                "/credits": "anatomy/ATTRIBUTION.md",
                "/library/equipment.json": "library/equipment.json",
            }
            if url.path not in allowed:
                return self.send_error(404)
            path = ROOT / allowed[url.path]
            mime = (
                "text/plain; charset=utf-8"
                if url.path == "/credits"
                else guess_type(path)[0] or "application/octet-stream"
            )
            self.send(path.read_bytes(), mime)

    def do_POST(self):
        if self.path not in ("/api/preview", "/api/parameters"):
            return self.send_error(404)
        if self.headers.get_content_type() != "application/json":
            return self.send_error(415)
        try:
            size = int(self.headers.get("Content-Length", 0))
            if size <= 0 or size > 512_000:
                return self.send_error(413)
            from eml.data import _unique

            def reject(value):
                raise ValueError("Non-finite JSON number: " + value)

            doc = json.loads(
                self.rfile.read(size), object_pairs_hook=_unique, parse_constant=reject
            )
        except (ValueError, RecursionError) as error:
            return self.json({"error": str(error)}, 400)
        if self.path == "/api/parameters":
            if (
                not isinstance(doc, dict)
                or not isinstance(doc.get("parameters"), dict)
                or "recipe" not in doc
            ):
                return self.json(
                    {"error": "Expected recipe and parameters objects."}, 400
                )
            self.clip(doc["recipe"], doc["parameters"])
        else:
            self.clip(doc)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Review the EML catalog and local custom recipes"
    )
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--fps", type=int, choices=range(1, 31), default=12, metavar="1-30"
    )
    args = parser.parse_args()
    with PreviewServer(("127.0.0.1", args.port), args.fps) as server:
        print(
            f"Serving {len(entries())} recipes at http://127.0.0.1:{server.server_port}/",
            flush=True,
        )
        server.serve_forever()
