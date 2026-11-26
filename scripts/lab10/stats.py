#!/usr/bin/env python3
"""Статистика метрик Bookings з CloudWatch (LocalStack): лише GetMetricStatistics і GetMetricData.

    .venv/bin/python scripts/lab10/stats.py --minutes 5            # останні 5 хв
    .venv/bin/python scripts/lab10/stats.py --phases reports/lab10-phases.json --instances \\
        --json reports/lab10-stats.json                              # по фазах експерименту

Формули (за хвилину і за інтервал):
  запитів      = Sum(RequestCount)
  частка помилок, % = 100 * Sum(ErrorCount) / Sum(RequestCount)
  сер. затримка = sum(Average_i * SampleCount_i) / sum(SampleCount_i)  (зважена, не середнє середніх)
"""

import argparse
import json
import os
from datetime import UTC, datetime, timedelta

NS = os.environ.get("METRICS_NAMESPACE", "Bookings")
PERIOD = 60
INSTANCES = ("instance-1", "instance-2", "instance-3")


# ---------- чисті функції (тестуються без CloudWatch) ----------
def error_pct(requests, errors):
    return 100.0 * errors / requests if requests else 0.0


def weighted_latency(rows):
    """Середня затримка за інтервал: середні по хвилинах зважені кількістю вимірів."""
    pairs = [(r["lat_avg"], r["lat_n"]) for r in rows if r.get("lat_avg") is not None and r.get("lat_n")]
    total = sum(n for _, n in pairs)
    return sum(avg * n for avg, n in pairs) / total if total else None


def summarize(rows):
    requests = sum(r["requests"] for r in rows)
    errors = sum(r["errors"] for r in rows)
    maxima = [r["lat_max"] for r in rows if r.get("lat_max") is not None]
    return {
        "minutes": len(rows),
        "requests": requests,
        "per_minute": requests / len(rows) if rows else 0.0,
        "errors": errors,
        "error_pct": error_pct(requests, errors),
        "lat_avg": weighted_latency(rows),
        "lat_max": max(maxima) if maxima else None,
    }


def in_phase(rows, phase):
    start, end = parse_time(phase["start"]), parse_time(phase["end"])
    return [r for r in rows if start <= r["t"] < end]


# ---------- CloudWatch ----------
def client():
    import boto3

    return boto3.client(
        "cloudwatch",
        endpoint_url=os.environ.get("CW_ENDPOINT", "http://localhost:4567"),
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),  # фіктивні ключі LocalStack
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
    )


def minute(t):
    return t.astimezone(UTC).replace(second=0, microsecond=0)


def parse_time(value):
    return minute(datetime.fromisoformat(value.replace("Z", "+00:00"))) if isinstance(value, str) else value


def statistics(cw, metric, stats, start, end, dims=()):
    """GetMetricStatistics -> {хвилина: datapoint}."""
    resp = cw.get_metric_statistics(
        Namespace=NS, MetricName=metric, Dimensions=list(dims),
        StartTime=start, EndTime=end, Period=PERIOD, Statistics=list(stats),
    )  # fmt: skip
    return {minute(dp["Timestamp"]): dp for dp in resp["Datapoints"]}


def per_minute(cw, start, end):
    """Агрегат без вимірів: Sum(RequestCount), Sum(ErrorCount), Average/Maximum/SampleCount(Latency)."""
    req = statistics(cw, "RequestCount", ["Sum"], start, end)
    err = statistics(cw, "ErrorCount", ["Sum"], start, end)
    lat = statistics(cw, "Latency", ["Average", "Maximum", "SampleCount"], start, end)
    return [
        {
            "t": t,
            "requests": req.get(t, {}).get("Sum", 0.0),
            "errors": err.get(t, {}).get("Sum", 0.0),
            "lat_avg": lat.get(t, {}).get("Average"),
            "lat_max": lat.get(t, {}).get("Maximum"),
            "lat_n": lat.get(t, {}).get("SampleCount", 0.0),
        }
        for t in sorted(set(req) | set(err) | set(lat))
    ]


def per_instance(cw, start, end):
    """Приклад GetMetricData: 9 рядів (3 метрики x InstanceId) одним викликом.
    -> {instance: {"RequestCount"|"ErrorCount"|"Latency": {хвилина: значення}}}"""
    metrics = (("RequestCount", "Sum"), ("ErrorCount", "Sum"), ("Latency", "Average"))
    queries = [
        {
            "Id": f"m{i}_{j}",
            "Label": f"{inst}|{name}",
            "MetricStat": {
                "Metric": {
                    "Namespace": NS,
                    "MetricName": name,
                    "Dimensions": [{"Name": "InstanceId", "Value": inst}],
                },
                "Period": PERIOD,
                "Stat": stat,
            },
        }
        for i, inst in enumerate(INSTANCES)
        for j, (name, stat) in enumerate(metrics)
    ]
    resp = cw.get_metric_data(
        MetricDataQueries=queries, StartTime=start, EndTime=end, ScanBy="TimestampAscending"
    )
    out = {inst: {name: {} for name, _ in metrics} for inst in INSTANCES}
    for res, q in zip(resp["MetricDataResults"], queries, strict=True):
        inst, name = q["Label"].split("|")
        out[inst][name] = {minute(t): v for t, v in zip(res["Timestamps"], res["Values"], strict=True)}
    return out


# ---------- вивід ----------
def fmt_ms(v):
    return "—" if v is None else f"{v:.1f}"


def local(t):
    return t.astimezone().strftime("%H:%M")


def phase_of(t, phases):
    return next((p["id"] for p in phases if parse_time(p["start"]) <= t < parse_time(p["end"])), "")


# таблиці вужчі за 62 символи — щоб без переносів читалися у вузькому терміналі
def print_minutes(rows, phases):
    print(f"{'хв':>5} {'запитів':>7} {'5xx':>5} {'5xx,%':>6} {'сер.,мс':>8} {'макс.,мс':>9} {'фаза':>5}")
    for r in rows:
        pct = error_pct(r["requests"], r["errors"])
        print(
            f"{local(r['t']):>5} {r['requests']:7.0f} {r['errors']:5.0f} {pct:6.1f} "
            f"{fmt_ms(r['lat_avg']):>8} {fmt_ms(r['lat_max']):>9} {phase_of(r['t'], phases):>5}"
        )


def print_summary(s, label="Разом"):
    print(
        f"{label}: {s['minutes']} хв, {s['requests']:.0f} запитів ({s['per_minute']:.1f}/хв), "
        f"{s['errors']:.0f} помилок ({s['error_pct']:.1f}%),\n  сер. затримка {fmt_ms(s['lat_avg'])} мс "
        f"(зважена), макс. {fmt_ms(s['lat_max'])} мс"
    )


def reaction(p):
    """'high-errors ALARM +50 с, OK +200 с' — від початку chaos і від його зняття (кінця фази)."""
    if not p.get("alarm"):
        return ""

    def since(key, ref):
        if not p.get(key):
            return "—"
        return f"+{(datetime.fromisoformat(p[key]) - datetime.fromisoformat(p[ref])).total_seconds():.0f} с"

    name = p["alarm"].removeprefix("bookings-")
    return f"{name} ALARM {since('alarm_at', 'chaos_at')}, OK {since('ok_at', 'end')}"


def print_phases(rows, phases):
    print(f"{'фаза':<17} {'хв':>2} {'запитів':>7} {'/хв':>5} {'5xx':>4} {'%':>5} {'сер.':>6} {'макс.':>6}")
    result = []
    for p in phases:
        s = summarize(in_phase(rows, p))
        result.append({**{k: p.get(k) for k in ("id", "title", "start", "end", "chaos", "rate")}, **s,
                       "reaction": reaction(p)})  # fmt: skip
        print(
            f"{p['title']:<17} {s['minutes']:>2} {s['requests']:7.0f} {s['per_minute']:5.0f} "
            f"{s['errors']:4.0f} {s['error_pct']:5.1f} {fmt_ms(s['lat_avg']):>6} {fmt_ms(s['lat_max']):>6}"
        )
    print("(сер./макс. — затримка, мс)")
    reactions = [f"  фаза {r['id']}: {r['reaction']}" for r in result if r["reaction"]]
    if reactions:
        print("Реакція alarm (ALARM — від початку chaos, OK — після зняття):", *reactions, sep="\n")
    return result


def print_instances(data):
    print(f"{'екземпляр':<11} {'запитів':>8} {'помилок':>8} {'помилки,%':>10} {'сер.,мс':>8}")
    for inst, m in data.items():
        req, err = sum(m["RequestCount"].values()), sum(m["ErrorCount"].values())
        # вага хвилинного Average(Latency) = кількість запитів за ту хвилину (= SampleCount)
        rows = [{"lat_avg": v, "lat_n": m["RequestCount"].get(t, 0)} for t, v in m["Latency"].items()]
        avg = weighted_latency(rows)
        print(f"{inst:<11} {req:8.0f} {err:8.0f} {error_pct(req, err):10.1f} {fmt_ms(avg):>8}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--minutes", type=int, default=10, help="останні N хвилин (якщо без --phases)")
    ap.add_argument("--phases", help="JSON фаз експерименту (experiment.sh)")
    ap.add_argument("--instances", action="store_true", help="таблиця за InstanceId (GetMetricData)")
    ap.add_argument("--no-minutes", action="store_true", help="не друкувати похвилинну таблицю")
    ap.add_argument("--json", help="зберегти підсумок по фазах у файл")
    args = ap.parse_args(argv)

    phases = []
    if args.phases:
        with open(args.phases) as f:
            phases = [p for p in json.load(f)["phases"] if p.get("start") and p.get("end")]
        start, end = parse_time(phases[0]["start"]), parse_time(phases[-1]["end"])
    else:
        end = minute(datetime.now(UTC)) + timedelta(minutes=1)
        start = end - timedelta(minutes=args.minutes + 1)

    cw = client()
    rows = per_minute(cw, start, end)
    print(f"GetMetricStatistics: namespace {NS}, period {PERIOD} с, {local(start)}–{local(end)}")
    if not args.no_minutes:
        print_minutes(rows, phases)
    print_summary(summarize(in_phase(rows, {"start": start, "end": end})))
    result = None
    if phases:
        print("\nПо фазах (лише повні хвилини всередині фази):")
        result = print_phases(rows, phases)
    if args.instances:
        print("\nGetMetricData за InstanceId (Sum, Sum, Average):")
        print_instances(per_instance(cw, start, end))
    if args.json and result is not None:
        with open(args.json, "w") as f:
            json.dump(result, f, ensure_ascii=False, indent=1, default=str)


if __name__ == "__main__":
    main()
