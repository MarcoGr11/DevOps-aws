#!/usr/bin/env python3
"""Графіки експерименту лаби 10 (PNG, matplotlib Agg). Дані — лише з CloudWatch:
GetMetricStatistics (агрегат), GetMetricData (за InstanceId), DescribeAlarmHistory (стани alarm).

    .venv/bin/python scripts/lab10/plot.py --phases reports/lab10-phases.json --out reports/graphs
"""

import argparse
import json
import os
from datetime import datetime, timedelta

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from stats import INSTANCES, client, error_pct, parse_time, per_instance, per_minute  # noqa: E402

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": "#c3c2b7", "axes.labelcolor": "#52514e",
    "xtick.color": "#52514e", "ytick.color": "#52514e", "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#e8e7e3", "grid.linewidth": 0.6, "axes.axisbelow": True,
    "figure.facecolor": "white", "axes.titlesize": 10, "axes.titleweight": "bold",
})  # fmt: skip
SERIES = ("#2a78d6", "#eb6834", "#1baf7a")  # категоріальні слоти 1–3 (довідкова палітра)
CRITICAL, THRESHOLD, BAND = "#d03b3b", "#52514e", "#f1f0ec"
LINE = {"lw": 2, "marker": "o", "ms": 4}
HALF = timedelta(seconds=30)  # точка хвилини [t, t+60) малюється по центру


def alarm_spans(cw, name, start, end):
    """Інтервали стану ALARM з DescribeAlarmHistory. Час переходу — queryDate з HistoryData
    (Timestamp у LocalStack 4.9.2 для повторних переходів неточний, див. LAB10.md)."""
    items = cw.describe_alarm_history(AlarmName=name, HistoryItemType="StateUpdate", MaxRecords=100)
    changes = []
    for it in items["AlarmHistoryItems"]:
        data = json.loads(it["HistoryData"])
        q = data["newState"].get("stateReasonData", {}).get("queryDate")
        t = datetime.strptime(q, "%Y-%m-%dT%H:%M:%S%z") if q else it["Timestamp"]
        changes.append((t, data["newState"]["stateValue"]))
    changes.sort()
    spans, began = [], None
    for t, state in changes:
        if state == "ALARM" and began is None:
            began = t
        elif state != "ALARM" and began is not None:
            spans.append((began, t))
            began = None
    if began is not None:
        spans.append((began, end))
    return [(max(a, start), min(b, end)) for a, b in spans if b > start and a < end]


def exact(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def decorate(ax, phases, top=False):
    lo, hi = ax.get_ylim()
    ax.set_ylim(min(lo, 0), hi * 1.45)  # запас зверху: легенда і смуга ALARM не закривають дані
    for i, p in enumerate(phases):
        a, b = exact(p["start"]), exact(p["end"])
        if i % 2 == 0:
            ax.axvspan(a, b, color=BAND, zorder=0, lw=0)
        if top:
            ax.text(a + (b - a) / 2, 1.02, p["title"], transform=ax.get_xaxis_transform(),
                    ha="center", va="bottom", fontsize=7.5, color="#52514e")  # fmt: skip
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=_tz()))
    ax.xaxis.set_major_locator(mdates.MinuteLocator(byminute=range(0, 60, 2), tz=_tz()))


def _tz():
    return datetime.now().astimezone().tzinfo


def mark_alarm(ax, spans, label):
    for a, b in spans:
        ax.axvspan(a, b, ymin=0.95, ymax=1.0, color=CRITICAL, lw=0, zorder=3)
    return Patch(color=CRITICAL, label=f"{label}: стан ALARM") if spans else None


def legend(ax, extra=None):
    handles, labels = ax.get_legend_handles_labels()
    if extra:
        handles.append(extra)
        labels.append(extra.get_label())
    ax.legend(
        handles, labels, loc="upper left", bbox_to_anchor=(0, 0.93), fontsize=7.5, frameon=False, ncol=3
    )


def save(fig, out, name):
    path = os.path.join(out, name)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  {path}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--phases", required=True)
    ap.add_argument("--out", default="reports/graphs")
    args = ap.parse_args(argv)
    with open(args.phases) as f:
        phases = [p for p in json.load(f)["phases"] if p.get("start") and p.get("end")]
    start, end = parse_time(phases[0]["start"]), parse_time(phases[-1]["end"])
    os.makedirs(args.out, exist_ok=True)

    cw = client()
    rows = [r for r in per_minute(cw, start, end) if start <= r["t"] < end]
    inst = per_instance(cw, start, end)
    err_spans = alarm_spans(cw, "bookings-high-errors", start, end)
    lat_spans = alarm_spans(cw, "bookings-high-latency", start, end)
    x = [r["t"] + HALF for r in rows]
    width = timedelta(seconds=48)

    # 1. запити за хвилину
    fig, ax = plt.subplots(figsize=(9, 3.4))
    ax.bar(x, [r["requests"] for r in rows], width=width, color=SERIES[0], label="Sum(RequestCount) / хв")
    decorate(ax, phases, top=True)
    ax.set_ylabel("запитів / хв")
    ax.set_xlabel("час (локальний)")
    legend(ax)
    save(fig, args.out, "lab10-requests.png")

    # 2. помилки: абсолютні (поріг alarm) і частка, %
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(9, 5), sharex=True, height_ratios=(1, 1))
    a1.bar(x, [r["errors"] for r in rows], width=width, color=SERIES[1], label="Sum(ErrorCount) за хвилину")
    a1.axhline(10, color=THRESHOLD, ls="--", lw=1, label="поріг bookings-high-errors: > 10")
    decorate(a1, phases, top=True)
    legend(a1, mark_alarm(a1, err_spans, "bookings-high-errors"))
    a1.set_ylabel("помилок / хв")
    a2.plot(x, [error_pct(r["requests"], r["errors"]) for r in rows], color=SERIES[0], lw=2, marker="o", ms=4,
            label="частка помилок = ErrorCount / RequestCount")  # fmt: skip
    decorate(a2, phases)
    legend(a2)
    a2.set_ylabel("помилки, %")
    a2.set_xlabel("час (локальний)")
    save(fig, args.out, "lab10-errors.png")

    # 3. затримка: середня і максимальна
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.plot(x, [r["lat_avg"] for r in rows], color=SERIES[0], label="Average(Latency)", **LINE)
    ax.plot(x, [r["lat_max"] for r in rows], color=SERIES[1], label="Maximum(Latency)", **LINE)
    ax.axhline(200, color=THRESHOLD, ls="--", lw=1, label="поріг bookings-high-latency: Average > 200 мс")
    decorate(ax, phases, top=True)
    legend(ax, mark_alarm(ax, lat_spans, "bookings-high-latency"))
    ax.set_ylabel("затримка, мс")
    ax.set_xlabel("час (локальний)")
    save(fig, args.out, "lab10-latency.png")

    # 4. за екземплярами (GetMetricData, вимір InstanceId)
    fig, (b1, b2) = plt.subplots(2, 1, figsize=(9, 5), sharex=True)
    for color, name in zip(SERIES, INSTANCES, strict=True):
        for ax, metric in ((b1, "RequestCount"), (b2, "ErrorCount")):
            pts = sorted((t, v) for t, v in inst[name][metric].items() if start <= t < end)
            ax.plot([t + HALF for t, _ in pts], [v for _, v in pts], color=color, label=name, **LINE)
    decorate(b1, phases, top=True)
    decorate(b2, phases)
    b1.set_ylabel("запитів / хв")
    b2.set_ylabel("помилок / хв")
    b2.set_xlabel("час (локальний)")
    legend(b1)
    legend(b2)
    save(fig, args.out, "lab10-instances.png")


if __name__ == "__main__":
    main()
