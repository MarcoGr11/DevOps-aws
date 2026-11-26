#!/usr/bin/env python3
"""Керований генератор навантаження для лаби 10 (лише stdlib).

Запити відправляються за розкладом (rate запитів/с), кожен у пулі потоків, тож повільні
відповіді не зменшують фактичний rate. Суміш: POST /bookings, GET /bookings (список),
решта — GET /bookings/{id} для id, створених цим же генератором.

    .venv/bin/python scripts/lab10/loadgen.py --rate 2 --duration 60
    .venv/bin/python scripts/lab10/loadgen.py --rate 6 --until 1764135600 --post 0.2 --list 0.05
"""

import argparse
import json
import random
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="controlled HTTP load for the bookings API")
    p.add_argument("--url", default="http://localhost:8080")
    p.add_argument("--rate", type=float, default=2.0, help="запитів за секунду")
    p.add_argument("--duration", type=float, default=60.0, help="тривалість, с")
    p.add_argument("--until", type=float, help="unix-час завершення (замість --duration)")
    p.add_argument("--post", type=float, default=0.2, help="частка POST /bookings")
    p.add_argument("--list", type=float, default=0.05, help="частка GET /bookings")
    p.add_argument("--report", type=float, default=10.0, help="проміжний підсумок кожні N с (0 = ні)")
    p.add_argument("--label", default="", help="мітка в рядках виводу (назва фази)")
    return p.parse_args(argv)


class Stats:
    def __init__(self):
        self.lock = threading.Lock()
        self.codes, self.instances, self.times = Counter(), Counter(), []

    def add(self, code, instance, seconds):
        with self.lock:
            self.codes[code] += 1
            self.instances[instance] += 1
            self.times.append(seconds)

    def snapshot(self):
        with self.lock:
            return Counter(self.codes), Counter(self.instances), list(self.times)


def request(url, method="GET", body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.headers.get("X-Instance-Id", "-"), resp.read()
    except urllib.error.HTTPError as err:
        return err.code, err.headers.get("X-Instance-Id", "-"), err.read()
    except OSError:
        return 0, "-", b""  # немає з'єднання / таймаут


def one(args, ids, stats, n):
    r = random.random()
    if r < args.post or not ids:
        h = n % 23
        slot = f"{h:02d}:00-{h + 1:02d}:00"
        body = {"user": f"load-{n}", "room": f"R-{n % 50}", "date": "2026-12-01", "slot": slot}
        method, url = "POST", f"{args.url}/bookings"
    elif r < args.post + args.list:
        method, url, body = "GET", f"{args.url}/bookings", None
    else:
        method, url, body = "GET", f"{args.url}/bookings/{random.choice(ids)}", None
    start = time.perf_counter()
    code, instance, payload = request(url, method, body)
    stats.add(code, instance, time.perf_counter() - start)
    if method == "POST" and code == 201:
        ids.append(json.loads(payload)["id"])


def line(stats, elapsed, label):
    codes, _, times = stats.snapshot()
    n = sum(codes.values())
    err = sum(v for k, v in codes.items() if k >= 500 or k == 0)
    avg = 1000 * sum(times) / n if n else 0
    return f"  {label}t={elapsed:4.0f}с запитів={n} 5xx={err} сер.={avg:.0f} мс"


def summary(stats, elapsed, rate):
    codes, instances, times = stats.snapshot()
    n = sum(codes.values())
    if not n:
        return "  запитів не було"
    err = sum(v for k, v in codes.items() if k >= 500 or k == 0)
    times.sort()
    p95 = times[min(n - 1, int(0.95 * n))]
    out = [
        f"  Підсумок loadgen: {n} запитів за {elapsed:.0f} с (план {rate:g}/с, факт {n / elapsed:.2f}/с)",
        "  коди: " + ", ".join(f"{k or '000'}={v}" for k, v in sorted(codes.items())),
        "  екземпляри: " + ", ".join(f"{k}={v}" for k, v in sorted(instances.items())),
        f"  помилки 5xx: {err} ({100 * err / n:.1f}%)",
        f"  час відповіді (клієнт): сер. {1000 * sum(times) / n:.1f} мс, p95 {1000 * p95:.1f} мс, "
        f"макс. {1000 * times[-1]:.1f} мс",
    ]
    return "\n".join(out)


def main(argv=None):
    args = parse_args(argv)
    t0 = time.time()
    end = args.until if args.until else t0 + args.duration
    stats, ids = Stats(), []
    label = f"[{args.label}] " if args.label else ""
    interval, n, next_report = 1 / args.rate, 0, t0 + args.report
    with ThreadPoolExecutor(max_workers=64) as pool:
        while (now := time.time()) < end:
            due = t0 + n * interval
            if due > now:
                time.sleep(min(due - now, end - now))
                continue
            pool.submit(one, args, ids, stats, n)
            n += 1
            if args.report and now >= next_report:
                print(line(stats, now - t0, label), flush=True)
                next_report += args.report
    print(summary(stats, time.time() - t0, args.rate), flush=True)


if __name__ == "__main__":
    main()
