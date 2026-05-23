#!/usr/bin/env python3
"""Mide el tiempo de despliegue de un escenario en el Pi (§4.4 del marco teórico).

Levanta el escenario desde frío con `docker compose up -d` en el Pi (vía SSH) y
cronometra desde ese instante hasta que el dashboard del escenario responde
HTTP 200. Escribe una fila a deploy.csv en el directorio de la sesión.

Es la mitad automatizable del §4.4. La otra mitad —el tiempo de montaje físico
(conectar router + Pi + laptop)— la mide el operador con cronómetro y se anota
con `session.sh log montaje_fisico_s <n>`.

Por defecto baja el escenario primero (`docker compose down`) para que la medición
sea de un arranque en frío; usar --no-cold para cronometrar tal cual está.

Uso:
    measure_deploy.py --scenario esc1 --output-dir sessions/2026-05-22_esc1
    measure_deploy.py --scenario esc3 --output-dir <dir> --pi-host 192.168.1.10

Auth SSH: usa la llave (~/.ssh/id_ed25519) si existe; si no, sshpass con PI_PASS.
"""
from __future__ import annotations
import argparse
import csv
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# Directorio del docker-compose y puerto del dashboard, por escenario.
SCENARIOS = {
    "esc1": {"dir": "tesis_escenario1", "port": 1881},
    "esc2": {"dir": "tesis_escenario2", "port": 1882},
    "esc3": {"dir": "tesis_escenario3", "port": 1883},
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--scenario", required=True, choices=sorted(SCENARIOS))
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--pi-host", default="192.168.1.10")
    p.add_argument("--pi-user", default="raspberry1")
    p.add_argument("--pi-home", default="/home/raspberry1",
                   help="ruta base donde viven las carpetas tesis_escenarioN en el Pi")
    p.add_argument("--cold", dest="cold", action="store_true", default=True,
                   help="baja el escenario antes de medir (arranque en frío, por defecto)")
    p.add_argument("--no-cold", dest="cold", action="store_false",
                   help="no baja el escenario primero; cronometra tal cual")
    p.add_argument("--timeout", type=float, default=180.0,
                   help="máximo a esperar el HTTP 200 (s)")
    p.add_argument("--interval", type=float, default=0.5,
                   help="cadencia del sondeo HTTP (s)")
    return p.parse_args()


def ssh_base(user: str, host: str) -> list[str]:
    """Comando SSH base: llave si existe, sshpass si hay PI_PASS, si no SSH normal."""
    common = ["-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=8"]
    key = Path.home() / ".ssh" / "id_ed25519"
    if key.exists():
        return ["ssh", "-o", "BatchMode=yes", *common, f"{user}@{host}"]
    if os.environ.get("PI_PASS"):
        os.environ["SSHPASS"] = os.environ["PI_PASS"]
        return ["sshpass", "-e", "ssh", *common, f"{user}@{host}"]
    return ["ssh", *common, f"{user}@{host}"]


def run_remote(base: list[str], remote_cmd: str, timeout: int = 120) -> tuple[int, str]:
    try:
        r = subprocess.run(base + [remote_cmd], capture_output=True, text=True,
                           timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def compose(base: list[str], compose_dir: str, action: str) -> tuple[int, str]:
    """Corre `docker compose <action>`; cae a `docker-compose` si no existe el plugin."""
    cmd = (f"cd {compose_dir} && "
           f"(docker compose {action} 2>/dev/null || docker-compose {action})")
    return run_remote(base, cmd, timeout=150)


def is_ready(host: str, port: int, timeout: float = 2.0) -> tuple[bool, int]:
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/", timeout=timeout) as r:
            return (r.status == 200), r.status
    except Exception:
        return False, 0


def main() -> int:
    args = parse_args()
    sc = SCENARIOS[args.scenario]
    compose_dir = f"{args.pi_home.rstrip('/')}/{sc['dir']}"
    port = sc["port"]
    base = ssh_base(args.pi_user, args.pi_host)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    out = args.output_dir / "deploy.csv"
    is_new = not out.exists()

    if args.cold:
        print(f"[deploy] bajando {args.scenario} (arranque en frío)...")
        rc, msg = compose(base, compose_dir, "down")
        if rc != 0:
            print(f"[deploy] aviso: 'compose down' rc={rc}: {msg[:160]}")
        # Esperar a que el puerto deje de responder, hasta 20 s.
        for _ in range(40):
            if not is_ready(args.pi_host, port)[0]:
                break
            time.sleep(0.5)

    print(f"[deploy] levantando {args.scenario} en {compose_dir} ...")
    t0 = time.time()
    rc, msg = compose(base, compose_dir, "up -d")
    if rc != 0:
        print(f"[deploy] ERROR: 'compose up -d' rc={rc}: {msg[:200]}")
        return 1

    # Cronometrar hasta el primer HTTP 200.
    deadline = t0 + args.timeout
    ready, status = False, 0
    while time.time() < deadline:
        ready, status = is_ready(args.pi_host, port)
        if ready:
            break
        time.sleep(args.interval)
    deploy_seconds = round(time.time() - t0, 1)

    with out.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if is_new:
            w.writerow(["ts", "scenario", "deploy_seconds", "ready", "http_status"])
        w.writerow([f"{t0:.3f}", args.scenario, deploy_seconds,
                    "true" if ready else "false", status])

    if ready:
        print(f"[deploy] {args.scenario} LISTO en {deploy_seconds} s (HTTP {status}) -> {out}")
        return 0
    print(f"[deploy] {args.scenario} NO respondió en {args.timeout:.0f} s "
          f"(último status={status}). Fila registrada como ready=false.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
