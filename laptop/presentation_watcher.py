#!/usr/bin/env python3
"""Vigilante de escenarios para la presentacion.

Detecta automaticamente cuando cada escenario queda LISTO (dashboard responde
HTTP 200), sin importar como se levante (ops-console, SSH o presentation.sh).
Cuando un escenario pasa a listo, lee el StartedAt real de su contenedor
Node-RED en el Pi y registra en la bitacora la hora de inicio y el tiempo de
montaje (segundos desde que arranco el contenedor hasta que respondio).

Escribe filas (mismo formato que bitacora.csv):
    ts,iso,hito,escenario,notas
con hito 'scenario_ready' (notas: deploy_seconds=NN) o 'scenario_down'.

Uso:
  python3 presentation_watcher.py --bitacora <ruta> [--pi-host ..] [--pi-user ..]
                                  [--ssh-key ..] [--interval 1.5]
"""
import argparse
import csv
import signal
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

PORTS = {"esc1": 1881, "esc2": 1882, "esc3": 1883}
CONTAINER = {"esc1": "esc1-nodered", "esc2": "jp-esc2-nodered", "esc3": "esc3-nodered"}
_stop = False


def _sig(*_):
    global _stop
    _stop = True


def is_ready(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def container_started_epoch(user, host, key, container) -> float | None:
    """StartedAt (epoch) del contenedor via docker inspect por SSH."""
    cmd = ["ssh", "-o", "StrictHostKeyChecking=accept-new", "-o", "BatchMode=yes",
           "-o", "ConnectTimeout=6"]
    if key:
        cmd += ["-i", key]
    cmd += [f"{user}@{host}",
            f"docker inspect --format '{{{{.State.StartedAt}}}}' {container} 2>/dev/null"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=12).stdout.strip()
        if not out:
            return None
        # ISO ej: 2026-05-20T01:23:45.678901234Z  -> recortar a microsegundos
        s = out.replace("Z", "+00:00")
        if "." in s:
            head, frac = s.split(".", 1)
            tz = ""
            if "+" in frac:
                frac, tz = frac.split("+", 1); tz = "+" + tz
            frac = frac[:6]
            s = f"{head}.{frac}{tz}"
        return datetime.fromisoformat(s).timestamp()
    except Exception:
        return None


def append(bitacora: Path, ts: float, hito: str, esc: str, notas: str):
    iso = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    with open(bitacora, "a", newline="") as f:
        csv.writer(f).writerow([int(ts), iso, hito, esc, notas])
    print(f"[watcher] {hito} {esc} {notas}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bitacora", required=True)
    p.add_argument("--pi-host", default="192.168.1.10")
    p.add_argument("--pi-user", default="raspberry1")
    p.add_argument("--ssh-key", default="")
    p.add_argument("--interval", type=float, default=1.5)
    args = p.parse_args()

    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)
    bit = Path(args.bitacora)

    # Estado inicial silencioso: si un escenario ya esta arriba, no lo contamos
    # como recien montado.
    ready = {s: is_ready(args.pi_host, PORTS[s]) for s in PORTS}
    for s, r in ready.items():
        if r:
            print(f"[watcher] {s} ya estaba listo al iniciar (no se mide montaje)")

    while not _stop:
        for s in PORTS:
            now_ready = is_ready(args.pi_host, PORTS[s])
            if now_ready and not ready[s]:
                ts = time.time()
                started = container_started_epoch(args.pi_user, args.pi_host, args.ssh_key, CONTAINER[s])
                if started:
                    secs = max(0, round(ts - started))
                    append(bit, ts, "scenario_ready", s, f"deploy_seconds={secs}")
                else:
                    append(bit, ts, "scenario_ready", s, "deploy_seconds=? (sin StartedAt)")
            elif not now_ready and ready[s]:
                append(bit, time.time(), "scenario_down", s, "")
            ready[s] = now_ready
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
