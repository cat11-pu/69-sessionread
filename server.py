"""server.py：本机服务（路径到内核方法的映射）。"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

from sessionread import Reader

ENGINE = Reader()
ROUTES = {
    "/report": lambda payload: ENGINE.report(payload["node"], payload["applied"]),
    "/bind": lambda payload: ENGINE.bind(payload["client"], payload.get("node")),
    "/read": lambda payload: ENGINE.read(payload["client"], payload.get("required", 0)),
    "/recover": lambda payload: ENGINE.recover(),
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.reply(ENGINE.stats())

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        payload = json.loads(self.rfile.read(length) or b"{}")
        route = ROUTES.get(self.path.split("?")[0])
        self.reply(route(payload) if route else {})

    def reply(self, result):
        body = json.dumps(result).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


    def log_message(self, *args):
        pass


def serve(port: int = 0):
    return HTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print("listening on http://127.0.0.1:%d" % port)
    serve(port).serve_forever()
