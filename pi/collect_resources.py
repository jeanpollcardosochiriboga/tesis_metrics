#!/usr/bin/env python3
"""Sample host (psutil) and container (docker SDK) resources on the Pi.

Writes one CSV row per source per second to <output-dir>/resources.csv.
Columns: ts, source, cpu_pct, mem_mb, net_rx_kbps, net_tx_kbps

Stops cleanly on SIGINT/SIGTERM.
"""
import argparse
import csv
import os
import signal
import sys
import time
from pathlib import Path

import psutil

try:
    import docker
except ImportError:
    docker = None


HEADER = ["ts", "source", "cpu_pct", "mem_mb", "net_rx_kbps", "net_tx_kbps"]
_stop = False


def _handle_signal(signum, frame):
    global _stop
    _stop = True


def _container_cpu_pct(stats: dict) -> float:
    """Compute CPU% from a docker stats dict (Linux)."""
    try:
        cpu = stats["cpu_stats"]
        precpu = stats["precpu_stats"]
        cpu_delta = cpu["cpu_usage"]["total_usage"] - precpu["cpu_usage"]["total_usage"]
        sys_delta = cpu["system_cpu_usage"] - precpu.get("system_cpu_usage", 0)
        online = cpu.get("online_cpus") or len(cpu["cpu_usage"].get("percpu_usage", [1]))
        if sys_delta > 0 and cpu_delta >= 0:
            return (cpu_delta / sys_delta) * online * 100.0
    except (KeyError, TypeError, ZeroDivisionError):
        pass
    return 0.0


def _container_net_kbps(stats: dict, prev_net: dict, dt: float) -> tuple[float, float, dict]:
    """Sum all interfaces' rx/tx, compute KB/s versus prev snapshot.

    Returns (0, 0, {}) when stats['networks'] is None (container uses
    network_mode: host -- its traffic is reported under the host counters).
    """
    nets = stats.get("networks")
    if not nets:
        return 0.0, 0.0, {}
    rx = sum(n.get("rx_bytes", 0) for n in nets.values())
    tx = sum(n.get("tx_bytes", 0) for n in nets.values())
    rx_kbps = (rx - prev_net.get("rx", rx)) / 1024.0 / dt if dt > 0 else 0.0
    tx_kbps = (tx - prev_net.get("tx", tx)) / 1024.0 / dt if dt > 0 else 0.0
    return rx_kbps, tx_kbps, {"rx": rx, "tx": tx}


def _container_mem_mb(stats: dict, pid: int) -> float:
    """Container RSS in MB.

    Strategy:
      1. Try docker's `memory_stats.usage` (cgroup v1).
      2. Try sum of anon+file from `memory_stats.stats` (cgroup v2 with memory
         controller enabled).
      3. Fall back to psutil reading /proc/<pid>/status for the main process
         and all its children (works even when the kernel's memory cgroup
         controller is disabled, which is the default on Raspberry Pi OS).
    """
    ms = stats.get("memory_stats") or {}
    usage = ms.get("usage")
    if usage:
        return usage / 1024 / 1024
    sub = ms.get("stats") or {}
    anon = sub.get("anon", 0) or 0
    file_ = sub.get("file", 0) or 0
    if anon or file_:
        return (anon + file_) / 1024 / 1024
    if pid:
        try:
            p = psutil.Process(pid)
            rss = p.memory_info().rss
            for ch in p.children(recursive=True):
                try:
                    rss += ch.memory_info().rss
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            return rss / 1024 / 1024
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return 0.0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", required=True, help="Directory where resources.csv is written")
    p.add_argument("--containers", default="", help="Comma-separated container names to sample")
    p.add_argument("--interval", type=float, default=1.0, help="Sampling interval in seconds")
    args = p.parse_args()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "resources.csv"
    is_new = not csv_path.exists()

    targets = [c.strip() for c in args.containers.split(",") if c.strip()]
    cli = docker.from_env() if (docker and targets) else None

    # Prime psutil counters
    psutil.cpu_percent(interval=None)
    host_prev_net = psutil.net_io_counters()
    host_prev_ts = time.time()
    container_prev_net: dict[str, dict] = {}

    with open(csv_path, "a", newline="", buffering=1) as f:
        w = csv.writer(f)
        if is_new:
            w.writerow(HEADER)

        while not _stop:
            t0 = time.time()
            ts = round(t0, 3)

            # HOST sample (psutil)
            host_cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            host_net = psutil.net_io_counters()
            dt = max(t0 - host_prev_ts, 1e-3)
            host_rx_kbps = (host_net.bytes_recv - host_prev_net.bytes_recv) / 1024.0 / dt
            host_tx_kbps = (host_net.bytes_sent - host_prev_net.bytes_sent) / 1024.0 / dt
            host_prev_net = host_net
            host_prev_ts = t0
            w.writerow([ts, "host", round(host_cpu, 2), round(mem.used / 1024 / 1024, 1),
                        round(host_rx_kbps, 2), round(host_tx_kbps, 2)])

            # CONTAINER samples (docker SDK)
            if cli is not None:
                for name in targets:
                    try:
                        c = cli.containers.get(name)
                        pid = (c.attrs.get("State") or {}).get("Pid") or 0
                        s = c.stats(stream=False)
                        cpu = _container_cpu_pct(s)
                        mem_mb = _container_mem_mb(s, pid)
                        rx_kbps, tx_kbps, prev = _container_net_kbps(
                            s, container_prev_net.get(name, {}), dt)
                        container_prev_net[name] = prev
                        w.writerow([ts, name, round(cpu, 2), round(mem_mb, 1),
                                    round(rx_kbps, 2), round(tx_kbps, 2)])
                    except Exception as e:
                        print(f"[warn] {name}: {e}", file=sys.stderr)

            # Sleep the remainder
            elapsed = time.time() - t0
            time.sleep(max(args.interval - elapsed, 0))


if __name__ == "__main__":
    main()
