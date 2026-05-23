#!/usr/bin/env python3
"""Stream `docker events` from the Pi over SSH, append normalized rows to
docker_events.csv in the session directory.

Captures container lifecycle events — start, stop, die, oom, restart, kill —
that would otherwise leave no trace if a container crashes mid-demo.

Usage:
    docker_events_collector.py --output-dir <dir> --pi-user <u> --pi-host <h>
"""
from __future__ import annotations
import argparse, csv, json, os, signal, subprocess, sys, time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--pi-user", required=True)
    p.add_argument("--pi-host", required=True)
    p.add_argument("--filter", default="type=container",
                   help="docker events --filter argument (default: container only)")
    return p.parse_args()


COLS = ["ts", "type", "action", "container", "image", "exit_code", "signal"]


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out = args.output_dir / "docker_events.csv"
    is_new = not out.exists()
    cmd = [
        "ssh", "-o", "ServerAliveInterval=10",
        f"{args.pi_user}@{args.pi_host}",
        f"docker events --format '{{{{json .}}}}' --filter '{args.filter}'",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, bufsize=1)

    def stop(_s=None, _f=None):
        try: proc.terminate()
        except Exception: pass
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    with out.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        if is_new:
            w.writeheader(); f.flush()
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.strip()
            if not line: continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            attrs = ev.get("Actor", {}).get("Attributes", {}) or {}
            row = {
                "ts": ev.get("time") or int(time.time()),
                "type": ev.get("Type", ""),
                "action": ev.get("Action", ""),
                "container": attrs.get("name", ""),
                "image": attrs.get("image", ""),
                "exit_code": attrs.get("exitCode", ""),
                "signal": attrs.get("signal", ""),
            }
            w.writerow(row); f.flush()
    return proc.wait()


if __name__ == "__main__":
    sys.exit(main())
