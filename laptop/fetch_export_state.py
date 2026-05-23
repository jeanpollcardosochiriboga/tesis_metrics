#!/usr/bin/env python3
"""Fetch GET /api/export_state from a scenario's Node-RED and dump each
table as a CSV in the session directory.

Usage:
    fetch_export_state.py <nodered_base_url> <output_dir>

Example:
    fetch_export_state.py http://192.168.1.10:1883 ./sessions/esc3_2026-05-18_1830
"""
from __future__ import annotations
import csv, json, sys, urllib.request
from pathlib import Path


def fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def dump_table(rows: list[dict], out: Path) -> int:
    if not rows:
        return 0
    # union of keys across rows, stable order: first-seen
    cols: list[str] = []
    seen = set()
    for r in rows:
        for k in r.keys():
            if k not in seen:
                cols.append(k); seen.add(k)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if v is None else v) for k, v in r.items()})
    return len(rows)


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__); return 2
    base, outdir = sys.argv[1].rstrip("/"), Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)
    try:
        payload = fetch(f"{base}/api/export_state")
    except Exception as e:
        print(f"[export_state] FETCH FAILED: {e}")
        return 1
    tables = payload.get("tables", {})
    if not tables:
        print("[export_state] no tables in payload (empty session)")
        return 0
    for name, rows in tables.items():
        if not isinstance(rows, list):
            print(f"[export_state] skip {name}: not a list"); continue
        out = outdir / f"{name}.csv"
        n = dump_table(rows, out)
        print(f"[export_state] {name}.csv: {n} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
