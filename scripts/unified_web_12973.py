#!/usr/bin/env python3
"""Small same-origin SPA server and reverse proxy for the 12973 deployment."""

from __future__ import annotations

import argparse
import http.server
import urllib.error
import urllib.request
from pathlib import Path


class Handler(http.server.SimpleHTTPRequestHandler):
    root: Path
    backend: str

    def _proxy(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else None
        target = self.backend + self.path
        headers = {k: v for k, v in self.headers.items()
                   if k.lower() not in {"host", "connection", "content-length"}}
        try:
            with urllib.request.urlopen(urllib.request.Request(
                target, data=body, headers=headers, method=self.command
            ), timeout=3600) as response:
                self.send_response(response.status)
                for key, value in response.headers.items():
                    if key.lower() not in {"transfer-encoding", "connection"}:
                        self.send_header(key, value)
                self.end_headers()
                self.wfile.write(response.read())
        except urllib.error.HTTPError as exc:
            self.send_response(exc.code)
            self.end_headers()
            self.wfile.write(exc.read())

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/api/"):
            return self._proxy()
        requested = (self.root / self.path.lstrip("/").split("?", 1)[0]).resolve()
        try:
            requested.relative_to(self.root)
        except ValueError:
            self.send_error(400)
            return
        if not requested.is_file():
            self.path = "/index.html"
        return super().do_GET()

    do_POST = _proxy
    do_PUT = _proxy
    do_PATCH = _proxy
    do_DELETE = _proxy


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--backend", required=True)
    ap.add_argument("--port", type=int, default=12973)
    args = ap.parse_args()
    Handler.root = Path(args.root).resolve()
    Handler.backend = args.backend.rstrip("/")
    factory = lambda *a, **kw: Handler(*a, directory=str(Handler.root), **kw)  # noqa: E731
    http.server.ThreadingHTTPServer(("0.0.0.0", args.port), factory).serve_forever()


if __name__ == "__main__":
    main()
