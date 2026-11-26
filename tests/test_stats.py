"""Лаба 10: чисті функції stats.py (частка помилок, зважена затримка, підсумок по фазі)."""

from datetime import UTC, datetime

import pytest

import stats


def row(minute, requests, errors, lat_avg, lat_max, lat_n=None):
    t = datetime(2026, 11, 26, 6, minute, tzinfo=UTC)
    return {"t": t, "requests": requests, "errors": errors, "lat_avg": lat_avg, "lat_max": lat_max,
            "lat_n": requests if lat_n is None else lat_n}  # fmt: skip


def test_error_pct():
    assert stats.error_pct(120, 30) == 25.0
    assert stats.error_pct(0, 0) == 0.0  # хвилина без запитів — не ділення на нуль


def test_weighted_latency_is_not_average_of_averages():
    rows = [row(0, 100, 0, 10.0, 50.0), row(1, 300, 0, 50.0, 90.0)]
    # (10*100 + 50*300) / 400 = 40, а просте середнє середніх дало б 30
    assert stats.weighted_latency(rows) == pytest.approx(40.0)
    assert stats.weighted_latency([]) is None
    assert stats.weighted_latency([row(0, 0, 0, None, None)]) is None


def test_summarize_phase():
    rows = [row(0, 120, 0, 5.0, 20.0), row(1, 120, 30, 15.0, 400.0), row(2, 60, 6, 5.0, 30.0)]
    s = stats.summarize(rows)
    assert (s["minutes"], s["requests"], s["errors"]) == (3, 300, 36)
    assert s["per_minute"] == pytest.approx(100.0)
    assert s["error_pct"] == pytest.approx(12.0)
    assert s["lat_avg"] == pytest.approx((5 * 120 + 15 * 120 + 5 * 60) / 300)
    assert s["lat_max"] == 400.0


def test_in_phase_uses_half_open_minute_interval():
    rows = [row(m, 1, 0, 1.0, 1.0) for m in range(5)]
    phase = {"start": "2026-11-26T06:01:00Z", "end": "2026-11-26T06:03:00Z"}
    assert [r["t"].minute for r in stats.in_phase(rows, phase)] == [1, 2]


def test_reaction_time_from_chaos_start_and_end():
    p = {
        "alarm": "bookings-high-errors",
        "chaos_at": "2026-11-26T06:00:00Z",
        "end": "2026-11-26T06:03:00Z",
        "alarm_at": "2026-11-26T06:01:17Z",
        "ok_at": "2026-11-26T06:06:20Z",
    }
    assert stats.reaction(p) == "high-errors ALARM +77 с, OK +200 с"
    assert stats.reaction({**p, "alarm_at": None, "ok_at": None}) == "high-errors ALARM —, OK —"
    assert stats.reaction({"title": "1 норма"}) == ""
