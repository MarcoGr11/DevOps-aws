"""HTTP-адаптер лаби 9: перетворює звичайний HTTP-запит на подію API Gateway (AWS_PROXY)
і викликає lambda_handler з лаби 8 без змін бізнес-логіки.

Лаба 10: метрики запитів у CloudWatch (CLOUDWATCH_ENABLED=1) і керована деградація
через /admin/chaos (ENABLE_CHAOS=1). Без цих змінних поведінка — як у лабі 9."""

import json
import logging
import os
import queue
import random
import re
import signal
import socket
import sys
import threading
import time
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from handler import lambda_handler, response

log = logging.getLogger("bookings.metrics")

# той самий ідентифікатор бачить і handler.health(), і заголовок X-Instance-Id
INSTANCE_ID = os.environ.setdefault("INSTANCE_ID", socket.gethostname())
PORT = int(os.environ.get("PORT", "8000"))
ID_PATH = re.compile(r"^/bookings/([^/]+)$")
NAMESPACE = os.environ.get("METRICS_NAMESPACE", "Bookings")
CHAOS_ENABLED = os.environ.get("ENABLE_CHAOS") == "1"
chaos = {"fail_rate": 0.0, "latency_ms": 0}  # замінюється цілим словником -> атомарно
publisher = None  # MetricsPublisher, створюється в main() при CLOUDWATCH_ENABLED=1


def metric_data(status, latency_ms, timestamp, instance_id):
    """Один запит -> 3 метрики, кожна двічі: без вимірів (агрегат) і з InstanceId."""
    values = [
        ("RequestCount", 1, "Count"),
        ("ErrorCount", 1 if status >= 500 else 0, "Count"),
        ("Latency", round(latency_ms, 2), "Milliseconds"),
    ]
    dims = [[], [{"Name": "InstanceId", "Value": instance_id}]]
    return [
        {"MetricName": n, "Value": v, "Unit": u, "Timestamp": timestamp, "Dimensions": d}
        for n, v, u in values
        for d in dims
    ]


class MetricsPublisher:
    """Черга + фоновий потік: запит не чекає на CloudWatch. Відправка кожні `interval` с
    або одразу, щойно в черзі `batch_size` точок; до `batch_size` точок за один виклик."""

    def __init__(self, client, namespace=NAMESPACE, interval=1.0, batch_size=20):
        self.client, self.namespace = client, namespace
        self.interval, self.batch_size = interval, batch_size
        self.queue = queue.Queue()
        self._wake = threading.Event()

    def record(self, status, latency_ms):
        now = datetime.now(UTC)
        for datum in metric_data(status, latency_ms, now, INSTANCE_ID):
            self.queue.put(datum)
        if self.queue.qsize() >= self.batch_size:
            self._wake.set()

    def flush(self):
        batch = []
        while True:
            try:
                batch.append(self.queue.get_nowait())
            except queue.Empty:
                break
        for i in range(0, len(batch), self.batch_size):
            chunk = batch[i : i + self.batch_size]
            try:
                self.client.put_metric_data(Namespace=self.namespace, MetricData=chunk)
            except Exception:  # метрики не повинні ламати API: логуємо і йдемо далі
                log.exception("put_metric_data failed, %d datapoints dropped", len(chunk))

    def start(self):
        threading.Thread(target=self._run, name="metrics", daemon=True).start()

    def _run(self):
        while True:
            self._wake.wait(self.interval)
            self._wake.clear()
            self.flush()


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


def admin_chaos(method, body):
    """GET -> поточні значення; POST {"fail_rate": 0..1, "latency_ms": N} -> змінити."""
    global chaos
    if method == "POST":
        try:
            data = json.loads(body or "{}")
            new = {
                "fail_rate": float(data.get("fail_rate", chaos["fail_rate"])),
                "latency_ms": int(data.get("latency_ms", chaos["latency_ms"])),
            }
        except (ValueError, TypeError, AttributeError):
            return response(400, {"error": "expected JSON {fail_rate: 0..1, latency_ms: int >= 0}"})
        if not (0 <= new["fail_rate"] <= 1 and new["latency_ms"] >= 0):
            return response(400, {"error": "fail_rate must be 0..1, latency_ms >= 0"})
        chaos = new
        print(f"{INSTANCE_ID} chaos set: {chaos}", flush=True)
    elif method != "GET":
        return response(405, {"error": "method not allowed"})
    return response(200, {**chaos, "instance": INSTANCE_ID})


def api(method, path, headers, body):
    current = chaos
    if current["latency_ms"]:
        time.sleep(current["latency_ms"] / 1000)
    if current["fail_rate"] and random.random() < current["fail_rate"]:
        return response(500, {"error": "chaos: injected failure"})
    return lambda_handler(to_event(method, path, headers, body), None)


def dispatch(method, path, headers, body):
    route = path.split("?", 1)[0].rstrip("/") or "/"
    if route.startswith("/admin"):  # службові маршрути: без метрик і без chaos
        found = CHAOS_ENABLED and route == "/admin/chaos"
        resp = admin_chaos(method, body) if found else response(404, {"error": "not found"})
    elif route == "/health":  # health-check балансувальника: без метрик і без chaos
        resp = lambda_handler(to_event(method, path, headers, body), None)
    else:
        start = time.perf_counter()
        resp = api(method, path, headers, body)
        if publisher:
            publisher.record(resp["statusCode"], (time.perf_counter() - start) * 1000)
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
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    global publisher
    if os.environ.get("CLOUDWATCH_ENABLED") == "1":
        import boto3  # endpoint береться з AWS_ENDPOINT_URL (LocalStack)

        publisher = MetricsPublisher(boto3.client("cloudwatch"))
        publisher.start()
        print(f"{INSTANCE_ID} metrics -> CloudWatch namespace {NAMESPACE}", flush=True)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"{INSTANCE_ID} listening on :{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
