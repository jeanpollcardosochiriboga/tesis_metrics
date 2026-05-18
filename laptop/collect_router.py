#!/usr/bin/env python3
"""Poll OpenWrt router via SSH for associated stations + interface bytes.

Each cycle (default 5 s):
  - `iw dev <wifi_iface> station dump | grep -c '^Station'`   -> associated_stations
  - `cat /proc/net/dev`                                       -> bytes RX/TX por iface

Computes KB/s by delta vs previous cycle. Writes append to
<output-dir>/router.csv with columns:
  ts, associated_stations, wifi_rx_kbps, wifi_tx_kbps, lan_rx_kbps, lan_tx_kbps

Auth: password via sshpass; password from env var ROUTER_PASS.
"""
import argparse
import csv
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

HEADER = ["ts", "associated_stations", "wifi_rx_kbps", "wifi_tx_kbps",
          "lan_rx_kbps", "lan_tx_kbps"]
_stop = False


def _handle_signal(signum, frame):
    global _stop
    _stop = True


def _ssh(host: str, user: str, password: str, remote_cmd: str, timeout: int = 8) -> str:
    """Run a remote command via sshpass; return stdout (str), '' on error."""
    cmd = [
        "sshpass", "-e",
        "ssh", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=no",
        f"{user}@{host}", remote_cmd,
    ]
    env = {**os.environ, "SSHPASS": password}
    try:
        out = subprocess.run(cmd, capture_output=True, text=True,
                             timeout=timeout, env=env)
        if out.returncode != 0:
            print(f"[warn] ssh rc={out.returncode}: {out.stderr.strip()[:120]}", file=sys.stderr)
        return out.stdout
    except subprocess.TimeoutExpired:
        print("[warn] ssh timeout", file=sys.stderr)
        return ""


def _parse_proc_net_dev(text: str, iface: str) -> tuple[int, int]:
    """Return (rx_bytes, tx_bytes) for the given iface, or (0, 0) if not found."""
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith(iface + ":"):
            continue
        parts = re.split(r"\s+", line.split(":", 1)[1].strip())
        if len(parts) >= 9:
            return int(parts[0]), int(parts[8])
    return 0, 0


def _count_stations(dump_output: str) -> int:
    """Count '^Station' lines from iw dev <iface> station dump."""
    return sum(1 for ln in dump_output.splitlines() if ln.startswith("Station "))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", required=True)
    p.add_argument("--host", default="192.168.1.1")
    p.add_argument("--user", default="root")
    p.add_argument("--wifi-iface", default="wlan1", help="public WiFi interface (radio 2.4GHz)")
    p.add_argument("--lan-iface", default="br-lan", help="LAN interface that talks to Pi")
    p.add_argument("--interval", type=float, default=5.0)
    args = p.parse_args()

    password = os.environ.get("ROUTER_PASS")
    if not password:
        print("ERROR: set ROUTER_PASS env var (router SSH password)", file=sys.stderr)
        sys.exit(2)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "router.csv"
    is_new = not csv_path.exists()

    # Build a single remote command per cycle to amortize SSH overhead
    remote_cmd = (
        f"cat /proc/net/dev; echo '===STATIONS==='; "
        f"iw dev {args.wifi_iface} station dump 2>/dev/null"
    )

    prev_wifi = None      # (rx, tx)
    prev_lan = None
    prev_ts = None

    with open(csv_path, "a", newline="", buffering=1) as f:
        w = csv.writer(f)
        if is_new:
            w.writerow(HEADER)

        while not _stop:
            t0 = time.time()
            ts = round(t0, 3)

            out = _ssh(args.host, args.user, password, remote_cmd)
            if not out:
                time.sleep(args.interval)
                continue

            proc_part, _, stations_part = out.partition("===STATIONS===")
            wifi_rx, wifi_tx = _parse_proc_net_dev(proc_part, args.wifi_iface)
            lan_rx, lan_tx = _parse_proc_net_dev(proc_part, args.lan_iface)
            stations = _count_stations(stations_part)

            if prev_ts is not None:
                dt = max(t0 - prev_ts, 1e-3)
                wifi_rx_kbps = max(wifi_rx - prev_wifi[0], 0) / 1024.0 / dt
                wifi_tx_kbps = max(wifi_tx - prev_wifi[1], 0) / 1024.0 / dt
                lan_rx_kbps = max(lan_rx - prev_lan[0], 0) / 1024.0 / dt
                lan_tx_kbps = max(lan_tx - prev_lan[1], 0) / 1024.0 / dt
                w.writerow([ts, stations,
                            round(wifi_rx_kbps, 2), round(wifi_tx_kbps, 2),
                            round(lan_rx_kbps, 2), round(lan_tx_kbps, 2)])

            prev_wifi = (wifi_rx, wifi_tx)
            prev_lan = (lan_rx, lan_tx)
            prev_ts = t0

            elapsed = time.time() - t0
            time.sleep(max(args.interval - elapsed, 0))


if __name__ == "__main__":
    main()
