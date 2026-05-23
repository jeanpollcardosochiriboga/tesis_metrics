#!/usr/bin/env python3
"""Poll OpenWrt router via SSH for traffic, associated devices, and own resources.

Each cycle (default 5 s) one SSH round-trip collects everything and writes three
CSVs in <output-dir>:

  router.csv            — agregado de tráfico e interfaces (compatibilidad histórica)
    ts, associated_stations, wifi_rx_kbps, wifi_tx_kbps, lan_rx_kbps, lan_tx_kbps

  router_devices.csv    — un equipo por fila (T2): cruza `iw station dump` con las
                          leases DHCP para dar MAC → IP → hostname.
    ts, mac, ip, hostname, signal_dbm, connected_s, rx_kbps, tx_kbps

  router_resources.csv  — CPU y RAM del propio router (T3), desde /proc (sin busybox top).
    ts, cpu_pct, mem_used_mb, mem_total_mb

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
DEV_HEADER = ["ts", "mac", "ip", "hostname", "signal_dbm", "connected_s",
              "rx_kbps", "tx_kbps"]
RES_HEADER = ["ts", "cpu_pct", "mem_used_mb", "mem_total_mb"]
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


def _parse_stations(dump_output: str) -> dict[str, dict]:
    """Parse `iw dev <iface> station dump` into {mac: {signal, rx, tx, conn}}."""
    stations: dict[str, dict] = {}
    cur = None
    for ln in dump_output.splitlines():
        s = ln.strip()
        if s.startswith("Station "):
            cur = s.split()[1].lower()
            stations[cur] = {"signal": None, "rx": 0, "tx": 0, "conn": 0}
        elif cur is None:
            continue
        elif s.startswith("rx bytes:"):
            stations[cur]["rx"] = int(s.split(":", 1)[1].strip().split()[0])
        elif s.startswith("tx bytes:"):
            stations[cur]["tx"] = int(s.split(":", 1)[1].strip().split()[0])
        elif s.startswith("signal:"):
            tok = s.split(":", 1)[1].strip().split()[0]
            try:
                stations[cur]["signal"] = int(tok)
            except ValueError:
                pass
        elif s.startswith("connected time:"):
            stations[cur]["conn"] = int(s.split(":", 1)[1].strip().split()[0])
    return stations


def _parse_leases(text: str) -> dict[str, tuple[str, str]]:
    """Parse /tmp/dhcp.leases into {mac: (ip, hostname)}.

    Line format: <expiry> <mac> <ip> <hostname> <clientid>
    """
    leases: dict[str, tuple[str, str]] = {}
    for ln in text.splitlines():
        p = ln.split()
        if len(p) >= 4:
            mac = p[1].lower()
            ip = p[2]
            hostname = p[3] if p[3] != "*" else ""
            leases[mac] = (ip, hostname)
    return leases


def _parse_cpu(stat_line: str) -> tuple[int, int]:
    """From the 'cpu ...' line of /proc/stat return (idle, total) jiffies."""
    p = stat_line.split()
    if not p or p[0] != "cpu":
        return 0, 0
    nums = [int(x) for x in p[1:] if x.isdigit()]
    if len(nums) < 4:
        return 0, 0
    idle = nums[3] + (nums[4] if len(nums) > 4 else 0)  # idle + iowait
    return idle, sum(nums)


def _parse_meminfo(text: str) -> tuple[float, float]:
    """Return (mem_used_mb, mem_total_mb) from /proc/meminfo (kB values)."""
    vals = {}
    for ln in text.splitlines():
        m = re.match(r"(\w+):\s+(\d+)", ln)
        if m:
            vals[m.group(1)] = int(m.group(2))
    total = vals.get("MemTotal", 0)
    avail = vals.get("MemAvailable")
    if avail is None:
        avail = vals.get("MemFree", 0) + vals.get("Buffers", 0) + vals.get("Cached", 0)
    used = max(total - avail, 0)
    return used / 1024.0, total / 1024.0


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

    def _open(name, header):
        path = out_dir / name
        is_new = not path.exists()
        f = open(path, "a", newline="", buffering=1)
        w = csv.writer(f)
        if is_new:
            w.writerow(header)
        return f, w

    f_router, w_router = _open("router.csv", HEADER)
    f_dev, w_dev = _open("router_devices.csv", DEV_HEADER)
    f_res, w_res = _open("router_resources.csv", RES_HEADER)

    # One remote command per cycle, sections split by markers.
    remote_cmd = (
        f"cat /proc/net/dev; echo '===STATIONS==='; "
        f"iw dev {args.wifi_iface} station dump 2>/dev/null; "
        f"echo '===LEASES==='; cat /tmp/dhcp.leases 2>/dev/null; "
        f"echo '===STAT==='; head -1 /proc/stat 2>/dev/null; "
        f"echo '===MEM==='; cat /proc/meminfo 2>/dev/null"
    )

    prev_wifi = None      # (rx, tx)
    prev_lan = None
    prev_ts = None
    prev_dev: dict[str, tuple[int, int]] = {}   # mac -> (rx, tx)
    prev_cpu = None       # (idle, total)

    try:
        while not _stop:
            t0 = time.time()
            ts = round(t0, 3)

            out = _ssh(args.host, args.user, password, remote_cmd)
            if not out:
                time.sleep(args.interval)
                continue

            # Split by markers (each marker on its own line).
            proc_part, _, rest = out.partition("===STATIONS===")
            stations_part, _, rest = rest.partition("===LEASES===")
            leases_part, _, rest = rest.partition("===STAT===")
            stat_part, _, mem_part = rest.partition("===MEM===")

            # --- router.csv (aggregate traffic) ---
            wifi_rx, wifi_tx = _parse_proc_net_dev(proc_part, args.wifi_iface)
            lan_rx, lan_tx = _parse_proc_net_dev(proc_part, args.lan_iface)
            stations = _parse_stations(stations_part)
            leases = _parse_leases(leases_part)

            if prev_ts is not None:
                dt = max(t0 - prev_ts, 1e-3)
                wifi_rx_kbps = max(wifi_rx - prev_wifi[0], 0) / 1024.0 / dt
                wifi_tx_kbps = max(wifi_tx - prev_wifi[1], 0) / 1024.0 / dt
                lan_rx_kbps = max(lan_rx - prev_lan[0], 0) / 1024.0 / dt
                lan_tx_kbps = max(lan_tx - prev_lan[1], 0) / 1024.0 / dt
                w_router.writerow([ts, len(stations),
                                   round(wifi_rx_kbps, 2), round(wifi_tx_kbps, 2),
                                   round(lan_rx_kbps, 2), round(lan_tx_kbps, 2)])

                # --- router_devices.csv (one row per associated device) ---
                for mac, st in stations.items():
                    ip, host = leases.get(mac, ("", ""))
                    pr = prev_dev.get(mac)
                    if pr is not None:
                        rx_kbps = max(st["rx"] - pr[0], 0) / 1024.0 / dt
                        tx_kbps = max(st["tx"] - pr[1], 0) / 1024.0 / dt
                    else:
                        rx_kbps = tx_kbps = 0.0
                    w_dev.writerow([ts, mac, ip, host,
                                    st["signal"] if st["signal"] is not None else "",
                                    st["conn"], round(rx_kbps, 2), round(tx_kbps, 2)])

                # --- router_resources.csv (CPU/RAM of the router) ---
                idle, total = _parse_cpu(stat_part.strip())
                cpu_pct = ""
                if prev_cpu is not None and total > prev_cpu[1]:
                    d_idle = idle - prev_cpu[0]
                    d_total = total - prev_cpu[1]
                    cpu_pct = round(max(0.0, (1.0 - d_idle / d_total)) * 100.0, 2)
                mem_used_mb, mem_total_mb = _parse_meminfo(mem_part)
                w_res.writerow([ts, cpu_pct, round(mem_used_mb, 1), round(mem_total_mb, 1)])

            prev_wifi = (wifi_rx, wifi_tx)
            prev_lan = (lan_rx, lan_tx)
            prev_ts = t0
            prev_dev = {mac: (st["rx"], st["tx"]) for mac, st in stations.items()}
            prev_cpu = _parse_cpu(stat_part.strip())

            elapsed = time.time() - t0
            time.sleep(max(args.interval - elapsed, 0))
    finally:
        f_router.close()
        f_dev.close()
        f_res.close()


if __name__ == "__main__":
    main()
