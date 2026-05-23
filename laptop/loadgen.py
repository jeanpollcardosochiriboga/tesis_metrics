#!/usr/bin/env python3
"""Synthetic concurrent load generator with asyncio + httpx.

Ramps the concurrency level in stages defined by the YAML config; at each stage
it sustains the load for N seconds, then records:
  ts_start, ts_end, concurrency, requests, errors, rps,
  latency_p50_ms, latency_p95_ms, latency_p99_ms, latency_max_ms

Writes a single CSV row per stage to <output-dir>/loadtest.csv.

Run only from the lab — never against a venue with real public traffic.

Example config (config/esc1.yaml):
  load_test:
    target: http://192.168.1.10:1881/
    ramp_concurrency: [10, 25, 50, 100, 200]
    hold_s_per_step: 60
    request_timeout_s: 5.0
"""
import argparse
import asyncio
import csv
import math
import statistics
import time
from pathlib import Path

import httpx
import yaml


async def _worker(client: httpx.AsyncClient, target: str, timeout: float,
                  stop_at: float, latencies: list, errors: list):
    """One virtual user: fire requests back-to-back until stop_at."""
    while True:
        if time.time() >= stop_at:
            return
        t0 = time.perf_counter()
        try:
            r = await client.get(target, timeout=timeout)
            dt = (time.perf_counter() - t0) * 1000.0
            if r.status_code >= 500 or r.status_code == 0:
                errors.append(1)
            else:
                latencies.append(dt)
        except Exception:
            errors.append(1)


async def _run_stage(target: str, concurrency: int, hold_s: float, timeout: float) -> dict:
    """Run one concurrency stage; return aggregate metrics."""
    latencies: list = []
    errors: list = []
    ts_start = time.time()
    stop_at = ts_start + hold_s
    limits = httpx.Limits(max_connections=concurrency * 2,
                          max_keepalive_connections=concurrency * 2)
    async with httpx.AsyncClient(limits=limits) as client:
        workers = [asyncio.create_task(_worker(client, target, timeout, stop_at,
                                               latencies, errors))
                   for _ in range(concurrency)]
        await asyncio.gather(*workers, return_exceptions=True)
    ts_end = time.time()
    dur = max(ts_end - ts_start, 1e-3)
    total_req = len(latencies) + len(errors)
    err_rate = (len(errors) / total_req) if total_req else 0.0
    return {
        "ts_start": round(ts_start, 3),
        "ts_end": round(ts_end, 3),
        "concurrency": concurrency,
        "requests": total_req,
        "errors": len(errors),
        "error_rate": round(err_rate, 4),
        "rps": round(total_req / dur, 2),
        "latency_p50_ms": round(_pct(latencies, 50), 1) if latencies else 0.0,
        "latency_p95_ms": round(_pct(latencies, 95), 1) if latencies else 0.0,
        "latency_p99_ms": round(_pct(latencies, 99), 1) if latencies else 0.0,
        "latency_max_ms": round(max(latencies), 1) if latencies else 0.0,
    }


def _pct(values: list, p: int) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p / 100.0
    f = int(math.floor(k))
    c = int(math.ceil(k))
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text())
    lt = cfg["load_test"]
    target = lt["target"]
    ramp = lt["ramp_concurrency"]
    hold = float(lt.get("hold_s_per_step", 60))
    timeout = float(lt.get("request_timeout_s", 5.0))

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "loadtest.csv"
    is_new = not csv_path.exists()

    # 'knee' = primer escalón que degrada el servicio: error_rate > 1% o p95 > 1 s
    # (criterio del §4.2b del marco). Se marca aquí, junto al CSV, no solo en el notebook.
    KNEE_ERR_RATE = 0.01
    KNEE_P95_MS = 1000.0
    fieldnames = ["ts_start", "ts_end", "concurrency", "requests", "errors",
                  "error_rate", "rps", "latency_p50_ms", "latency_p95_ms",
                  "latency_p99_ms", "latency_max_ms", "knee"]
    knee_found = False
    with open(csv_path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if is_new:
            w.writeheader()
        f.flush()
        for c in ramp:
            print(f"[loadgen] stage c={c} hold={hold}s target={target}")
            row = asyncio.run(_run_stage(target, int(c), hold, timeout))
            is_knee = (not knee_found and
                       (row["error_rate"] > KNEE_ERR_RATE or
                        row["latency_p95_ms"] > KNEE_P95_MS))
            row["knee"] = "true" if is_knee else "false"
            if is_knee:
                knee_found = True
            print(f"          rps={row['rps']} err_rate={row['error_rate']}"
                  f" p50={row['latency_p50_ms']}ms p95={row['latency_p95_ms']}ms"
                  f"{'  <-- KNEE' if is_knee else ''}")
            w.writerow(row)
            f.flush()
    if not knee_found:
        print("[loadgen] no se alcanzó el knee en la rampa (servidor no degradó).")


if __name__ == "__main__":
    main()
