#!/usr/bin/env python3
"""Gráficas de consumo de recursos por escenario y consolidado general (§4.3, T6/T1).

Convención del tutor: eje X = tiempo, eje Y = consumo de recursos.

Dos modos:

  Por escenario — una figura con CPU (%) y RAM (MB) del host del Pi contra el tiempo,
  leyendo resources.csv de esa carpeta de sesión. Guarda recursos_<carpeta>.png.

      plot_scenario.py sessions/2026-05-22_esc1

  General (consolidado comparativo) — compara varios escenarios: tabla CSV con
  CPU promedio/pico y RAM máxima, más una figura de barras. Guarda en --out-dir.

      plot_scenario.py --general sessions/2026-05-22_esc1 sessions/2026-05-22_esc2 \\
                       sessions/2026-05-22_esc3 --out-dir sessions/

Lee solo la fila source='host' de resources.csv (consumo total del Pi).
"""
from __future__ import annotations
import argparse
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

_LOCAL_OFFSET = -time.timezone


def to_local(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s + _LOCAL_OFFSET, unit="s")


def scenario_label(name: str) -> str:
    for k, v in {"esc1": "Esc1 · Monitoreo", "esc2": "Esc2 · Phishing",
                 "esc3": "Esc3 · DoS"}.items():
        if k in name:
            return v
    return name


def load_host(session_dir: Path) -> pd.DataFrame:
    df = pd.read_csv(session_dir / "resources.csv")
    host = df[df["source"] == "host"].copy()
    if host.empty:
        raise SystemExit(f"[plot] {session_dir}/resources.csv no tiene filas host")
    host["t"] = to_local(host["ts"])
    return host.sort_values("t")


def _plot_cpu_ram(t, cpu, mem, mem_label: str, title: str, out: Path) -> Path:
    """Figura con CPU (%) y RAM en ejes gemelos contra el tiempo."""
    fig, ax_cpu = plt.subplots(figsize=(10, 4.5))
    ax_cpu.plot(t, cpu, color="#d9480f", label="CPU (%)")
    ax_cpu.set_xlabel("Tiempo")
    ax_cpu.set_ylabel("CPU (%)", color="#d9480f")
    ax_cpu.tick_params(axis="y", labelcolor="#d9480f")
    cpu_max = cpu.max()
    ax_cpu.set_ylim(0, max(100, (cpu_max if pd.notna(cpu_max) else 0) * 1.1))

    ax_mem = ax_cpu.twinx()
    ax_mem.plot(t, mem, color="#1c7ed6", label=mem_label)
    ax_mem.set_ylabel(mem_label, color="#1c7ed6")
    ax_mem.tick_params(axis="y", labelcolor="#1c7ed6")

    fig.suptitle(title)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    print(f"[plot] {out}")
    return out


def plot_one(session_dir: Path) -> list[Path]:
    label = scenario_label(session_dir.name)
    outs = []

    # Pi (resources.csv, fila host).
    host = load_host(session_dir)
    outs.append(_plot_cpu_ram(
        host["t"], host["cpu_pct"], host["mem_mb"], "RAM (MB)",
        f"Consumo del Raspberry Pi — {label}",
        session_dir / f"recursos_pi_{session_dir.name}.png"))

    # Router (router_resources.csv), si existe.
    rr = session_dir / "router_resources.csv"
    if rr.exists():
        df = pd.read_csv(rr)
        df["t"] = to_local(df["ts"])
        df["cpu_pct"] = pd.to_numeric(df["cpu_pct"], errors="coerce")
        df = df.sort_values("t")
        if df["cpu_pct"].notna().any():
            outs.append(_plot_cpu_ram(
                df["t"], df["cpu_pct"], df["mem_used_mb"], "RAM usada (MB)",
                f"Consumo del router OpenWrt — {label}",
                session_dir / f"recursos_router_{session_dir.name}.png"))
        else:
            print(f"[plot] {rr} sin datos de CPU válidos, omito gráfica de router")
    else:
        print(f"[plot] (sin router_resources.csv en {session_dir.name}; solo Pi)")
    return outs


def plot_general(session_dirs: list[Path], out_dir: Path) -> tuple[Path, Path]:
    rows = []
    for d in session_dirs:
        host = load_host(d)
        rows.append({
            "escenario": scenario_label(d.name),
            "cpu_prom_pct": round(host["cpu_pct"].mean(), 1),
            "cpu_pico_pct": round(host["cpu_pct"].max(), 1),
            "ram_max_mb": round(host["mem_mb"].max(), 0),
            "duracion_min": round((host["t"].max() - host["t"].min()).total_seconds() / 60, 1),
        })
    tbl = pd.DataFrame(rows)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_out = out_dir / "consolidado_general.csv"
    tbl.to_csv(csv_out, index=False)
    print(f"[plot] {csv_out}")

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.5))
    a1.bar(tbl["escenario"], tbl["cpu_prom_pct"], color="#ffa94d", label="CPU prom")
    a1.bar(tbl["escenario"], tbl["cpu_pico_pct"], color="#d9480f",
           width=0.4, label="CPU pico")
    a1.set_ylabel("CPU (%)"); a1.set_title("CPU por escenario"); a1.legend()
    a2.bar(tbl["escenario"], tbl["ram_max_mb"], color="#1c7ed6")
    a2.set_ylabel("RAM máx (MB)"); a2.set_title("RAM máxima por escenario")
    for ax in (a1, a2):
        ax.tick_params(axis="x", rotation=15)
    fig.suptitle("Consolidado comparativo de los 3 escenarios")
    fig.tight_layout()
    png_out = out_dir / "consolidado_general.png"
    fig.savefig(png_out, dpi=120)
    plt.close(fig)
    print(f"[plot] {png_out}")
    return csv_out, png_out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("session_dirs", nargs="+", type=Path)
    ap.add_argument("--general", action="store_true",
                    help="modo consolidado comparativo (varias carpetas)")
    ap.add_argument("--out-dir", type=Path, default=Path("sessions"),
                    help="destino del consolidado (solo con --general)")
    args = ap.parse_args()

    if args.general:
        plot_general(args.session_dirs, args.out_dir)
    else:
        for d in args.session_dirs:
            plot_one(d)
    return 0


if __name__ == "__main__":
    sys.exit(main())
