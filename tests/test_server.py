import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest
from test_handler import FakeTable

import handler
import server


@pytest.fixture(autouse=True)
def instance(monkeypatch):
    monkeypatch.setattr(handler, "_table", FakeTable())
    monkeypatch.setenv("INSTANCE_ID", "instance-7")
    monkeypatch.setattr(server, "INSTANCE_ID", "instance-7")


def test_to_event_maps_id_route_and_strips_query():
    event = server.to_event("GET", "/bookings/abc-1/?x=1", {"Accept": "*/*"}, None)
    assert event["httpMethod"] == "GET"
    assert event["resource"] == "/bookings/{id}"
    assert event["pathParameters"] == {"id": "abc-1"}
    assert event["headers"] == {"Accept": "*/*"}
    assert event["body"] is None


def test_to_event_collection_route_keeps_body():
    event = server.to_event("POST", "/bookings", {}, '{"a": 1}')
    assert (event["resource"], event["pathParameters"], event["body"]) == ("/bookings", None, '{"a": 1}')


def test_health_reports_instance_in_body_and_header():
    status, headers, body = server.dispatch("GET", "/health", {}, None)
    assert status == 200
    assert headers["X-Instance-Id"] == "instance-7"
    assert json.loads(body) == {"status": "ok", "instance": "instance-7"}


def test_unknown_route_is_404_with_instance_header():
    status, headers, _ = server.dispatch("PUT", "/nope", {}, None)
    assert status == 404 and headers["X-Instance-Id"] == "instance-7"


def test_real_http_roundtrip():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        body = json.dumps({"user": "olena", "room": "A-101", "date": "2026-12-01", "slot": "10:00-12:00"})
        req = urllib.request.Request(f"{base}/bookings", data=body.encode(), method="POST")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 201
            assert resp.headers["X-Instance-Id"] == "instance-7"
            created = json.load(resp)
        with urllib.request.urlopen(f"{base}/bookings/{created['id']}") as resp:
            assert resp.status == 200 and json.load(resp) == created
            assert resp.headers["Content-Type"] == "application/json"
    finally:
        httpd.shutdown()
