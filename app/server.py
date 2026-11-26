"""HTTP-адаптер лаби 9: перетворює звичайний HTTP-запит на подію API Gateway (AWS_PROXY)
і викликає lambda_handler з лаби 8 без змін бізнес-логіки."""

import os
import re
import signal
import socket
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from handler import lambda_handler

# той самий ідентифікатор бачить і handler.health(), і заголовок X-Instance-Id
INSTANCE_ID = os.environ.setdefault("INSTANCE_ID", socket.gethostname())
PORT = int(os.environ.get("PORT", "8000"))
ID_PATH = re.compile(r"^/bookings/([^/]+)$")


def to_event(method, path, headers, body):
    """HTTP-запит -> event у форматі API Gateway proxy (як у Lambda лаби 8)."""
    path = path.split("?", 1)[0].rstrip("/") or "/"
    match = ID_PATH.match(path)
    resource, params = ("/bookings/{id}", {"id": match.group(1)}) if match else (path, None)
    return {
        "httpMethod": method,
        "resource": resource,
        "path": path,
        "pathParameters": params,
        "headers": dict(headers),
        "body": body or None,
    }


def dispatch(method, path, headers, body):
    resp = lambda_handler(to_event(method, path, headers, body), None)
    out_headers = {**resp.get("headers", {}), "X-Instance-Id": INSTANCE_ID}
    return resp["statusCode"], out_headers, resp.get("body") or ""


class Handler(BaseHTTPRequestHandler):
    server_version = "bookings-app"

    def _serve(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode("utf-8") if length else None
        status, headers, payload = dispatch(self.command, self.path, self.headers, body)
        data = payload.encode("utf-8")
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = do_POST = do_DELETE = _serve


def main():
    # PID 1 у контейнері ігнорує SIGTERM без обробника -> docker stop чекав би 10 с
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"{INSTANCE_ID} listening on :{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
