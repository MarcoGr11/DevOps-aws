"""Лаба 10: публікація метрик у CloudWatch і /admin/chaos (без мережі, фейковий клієнт)."""

import json

import pytest
from test_handler import FakeTable

import handler
import server

BOOKING = json.dumps({"user": "olena", "room": "A-101", "date": "2026-12-01", "slot": "10:00-12:00"})


class FakeCloudWatch:
    def __init__(self, fail=False):
        self.calls, self.fail = [], fail

    def put_metric_data(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("cloudwatch down")


@pytest.fixture
def cw(monkeypatch):
    monkeypatch.setattr(handler, "_table", FakeTable())
    monkeypatch.setattr(server, "INSTANCE_ID", "instance-7")
    monkeypatch.setattr(server, "CHAOS_ENABLED", True)
    monkeypatch.setattr(server, "chaos", {"fail_rate": 0.0, "latency_ms": 0})
    client = FakeCloudWatch()
    monkeypatch.setattr(server, "publisher", server.MetricsPublisher(client, namespace="Bookings"))
    return client


def sent(client):
    server.publisher.flush()
    return [d for call in client.calls for d in call["MetricData"]]


def test_request_publishes_three_metrics_with_and_without_instance_dimension(cw):
    status, _, _ = server.dispatch("POST", "/bookings", {}, BOOKING)
    assert status == 201
    data = sent(cw)
    assert {c["Namespace"] for c in cw.calls} == {"Bookings"}
    assert len(data) == 6
    by_key = {(d["MetricName"], bool(d["Dimensions"])): d for d in data}
    names = ("RequestCount", "ErrorCount", "Latency")
    assert set(by_key) == {(m, dim) for m in names for dim in (False, True)}
    for (name, has_dim), d in by_key.items():
        assert d["Unit"] == {"RequestCount": "Count", "ErrorCount": "Count", "Latency": "Milliseconds"}[name]
        assert d["Dimensions"] == ([{"Name": "InstanceId", "Value": "instance-7"}] if has_dim else [])
        assert d["Timestamp"].tzinfo is not None
    assert by_key[("RequestCount", False)]["Value"] == 1
    assert by_key[("ErrorCount", False)]["Value"] == 0
    assert by_key[("Latency", False)]["Value"] >= 0


def test_health_and_admin_are_not_measured(cw):
    server.dispatch("GET", "/health", {}, None)
    server.dispatch("GET", "/admin/chaos", {}, None)
    server.dispatch("POST", "/admin/chaos", {}, '{"fail_rate": 0}')
    assert sent(cw) == []


def test_batches_are_at_most_batch_size(cw):
    for _ in range(4):  # 4 запити x 6 точок = 24 -> виклики по 20 і 4
        server.dispatch("GET", "/bookings", {}, None)
    sent(cw)
    assert [len(c["MetricData"]) for c in cw.calls] == [20, 4]


def test_cloudwatch_error_is_swallowed(monkeypatch, cw):
    client = FakeCloudWatch(fail=True)
    monkeypatch.setattr(server, "publisher", server.MetricsPublisher(client))
    assert server.dispatch("GET", "/bookings", {}, None)[0] == 200
    server.publisher.flush()  # не кидає виняток
    assert len(client.calls) == 1


def test_chaos_failures_count_as_errors(cw):
    assert server.dispatch("POST", "/admin/chaos", {}, '{"fail_rate": 1}')[0] == 200
    status, _, body = server.dispatch("GET", "/bookings", {}, None)
    assert status == 500 and json.loads(body) == {"error": "chaos: injected failure"}
    assert server.dispatch("GET", "/health", {}, None)[0] == 200  # health не зачеплено
    errors = [d["Value"] for d in sent(cw) if d["MetricName"] == "ErrorCount"]
    assert errors == [1, 1]


def test_chaos_latency_is_included_in_metric(cw):
    server.dispatch("POST", "/admin/chaos", {}, '{"latency_ms": 50}')
    server.dispatch("GET", "/bookings", {}, None)
    latency = [d["Value"] for d in sent(cw) if d["MetricName"] == "Latency"]
    assert len(latency) == 2 and min(latency) >= 50


def test_chaos_get_defaults_and_validation(cw):
    status, _, body = server.dispatch("GET", "/admin/chaos", {}, None)
    assert status == 200 and json.loads(body) == {"fail_rate": 0.0, "latency_ms": 0, "instance": "instance-7"}
    for bad in ('{"fail_rate": 2}', '{"latency_ms": -1}', "not json", '{"fail_rate": "x"}'):
        assert server.dispatch("POST", "/admin/chaos", {}, bad)[0] == 400
    assert server.chaos == {"fail_rate": 0.0, "latency_ms": 0}


def test_chaos_disabled_returns_404(monkeypatch, cw):
    monkeypatch.setattr(server, "CHAOS_ENABLED", False)
    assert server.dispatch("POST", "/admin/chaos", {}, '{"fail_rate": 1}')[0] == 404
    assert server.chaos["fail_rate"] == 0.0


def test_no_publisher_means_no_metrics(monkeypatch):
    monkeypatch.setattr(handler, "_table", FakeTable())
    monkeypatch.setattr(server, "publisher", None)
    assert server.dispatch("GET", "/bookings", {}, None)[0] == 200  # як у лабі 9
