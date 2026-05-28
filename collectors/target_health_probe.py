#!/usr/bin/env python3
"""HTTP availability probe for Esc3's target Flask server.

Probes GET <target_url> every <interval> seconds and writes one CSV row per
probe. Also polls Esc3's /api/export_state to tag each row with the current
phase (idle | ataque | protegido), derived from the orchestrator's attacking
and protection flags.

The point of this probe is to make the DoS scenario's headline metric — the
target's disponibilidad over time — visible as a clean time series, instead of
having to reconstruct it from Node-RED middleware logs of the orchestrator
(which is NOT the target).

Usage:
    target_health_probe.py --output-dir <dir> [options]

Options:
    --target-url URL         default http://192.168.1.10:5000/
    --orchestrator-url URL   default http://192.168.1.10:1883
    --interval FLOAT         seconds between probes (default 1.0)
    --timeout FLOAT          per-probe HTTP timeout (default 2.0)
    --phase-poll-interval N  poll orchestrator every N probes for phase
                             (default 5 — i.e. every 5 s when interval=1.0)
"""
from __future__ import annotations
import argparse, csv, signal, sys, time, urllib.request, urllib.error, json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--target-url", default="http://192.168.1.10:5000/")
    p.add_argument("--orchestrator-url", default="http://192.168.1.10:1883")
    p.add_argument("--interval", type=float, default=1.0)
    p.add_argument("--timeout", type=float, default=2.0)
    p.add_argument("--phase-poll-interval", type=int, default=5)
    return p.parse_args()


def probe(url: str, timeout: float) -> tuple[int, float]:
    """Return (status_code, response_ms). status_code=0 on connection error,
    -1 on timeout, -2 on any other error."""
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            r.read(1)  # touch the body so we measure full RTT, not just headers
            return r.getcode(), (time.perf_counter() - t0) * 1000.0
    except urllib.error.HTTPError as e:
        return e.code, (time.perf_counter() - t0) * 1000.0
    except urllib.error.URLError as e:
        # ConnectionRefused, DNS, etc.
        if "timed out" in str(e.reason).lower():
            return -1, (time.perf_counter() - t0) * 1000.0
        return 0, (time.perf_counter() - t0) * 1000.0
    except Exception:
        return -2, (time.perf_counter() - t0) * 1000.0


def fetch_phase(orchestrator_url: str, timeout: float) -> str:
    """Read attacking/protection from /api/export_state. Returns one of
    idle, ataque, protegido, unknown."""
    try:
        req = urllib.request.Request(f"{orchestrator_url.rstrip('/')}/api/export_state")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:
        return "unknown"
    snaps = data.get("tables", {}).get("esc3_stats_snapshot") or []
    if not snaps:
        return "unknown"
    last = snaps[-1]
    attacking = bool(last.get("attacking"))
    protection = bool(last.get("protection"))
    if attacking and protection: return "protegido"
    if attacking:                return "ataque"
    return "idle"


_STOP = False
def _sigterm(_signum, _frame):
    global _STOP
    _STOP = True
signal.signal(signal.SIGTERM, _sigterm)
signal.signal(signal.SIGINT, _sigterm)


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out = args.output_dir / "target_health.csv"
    is_new = not out.exists()
    with out.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if is_new:
            w.writerow(["ts", "status_code", "response_ms", "phase"])
            f.flush()
        phase = "unknown"
        i = 0
        next_tick = time.monotonic()
        while not _STOP:
            ts = time.time()
            code, ms = probe(args.target_url, args.timeout)
            if i % max(1, args.phase_poll_interval) == 0:
                phase = fetch_phase(args.orchestrator_url, args.timeout)
            w.writerow([f"{ts:.3f}", code, f"{ms:.2f}", phase])
            f.flush()
            i += 1
            next_tick += args.interval
            sleep_for = next_tick - time.monotonic()
            if sleep_for > 0:
                time.sleep(sleep_for)
            else:
                # we fell behind — resync to wall clock
                next_tick = time.monotonic()
    return 0


if __name__ == "__main__":
    sys.exit(main())
