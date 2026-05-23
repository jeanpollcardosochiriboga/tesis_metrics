#!/usr/bin/env python3
"""Grafica del consumo de recursos de TODA la presentacion, con las marcas de
inicio de cada escenario (bitacora) superpuestas.

Lee de <dir>:
  - resources.csv : ts, source, cpu_pct, mem_mb, net_rx_kbps, net_tx_kbps  (1/s)
  - bitacora.csv  : ts, iso, hito, escenario, notas

Genera <dir>/presentacion_recursos.png : CPU% y memoria del host del Pi en el
tiempo, con bandas de color por escenario y el tiempo de montaje anotado.

Uso: python3 plot_presentation.py <dir-de-la-presentacion>
"""
import sys
import time
from pathlib import Path

import pandas as pd

# epoch -> hora LOCAL (la maquina esta en hora de Ecuador, sin DST)
_LOCAL_OFFSET = -time.timezone


def to_local(ts_series):
    return pd.to_datetime(ts_series + _LOCAL_OFFSET, unit="s")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ESC_COLORS = {"esc1": "#2563eb", "esc2": "#d97706", "esc3": "#dc2626"}
ESC_LABEL = {"esc1": "Esc1 · Red", "esc2": "Esc2 · Phishing", "esc3": "Esc3 · DoS"}


def main():
    if len(sys.argv) < 2:
        sys.exit("uso: plot_presentation.py <dir>")
    d = Path(sys.argv[1])
    res = pd.read_csv(d / "resources.csv")
    res["t"] = to_local(res["ts"])
    host = res[res["source"] == "host"].sort_values("t")
    if host.empty:
        sys.exit("resources.csv no tiene filas 'host'")

    bit = pd.DataFrame(columns=["ts", "iso", "hito", "escenario", "notas"])
    bpath = d / "bitacora.csv"
    if bpath.exists():
        bit = pd.read_csv(bpath)
        bit["t"] = to_local(bit["ts"])

    t_min, t_max = host["t"].min(), host["t"].max()

    # Tramos por escenario: desde cada scenario_ready hasta el siguiente hito de corte.
    readys = bit[bit["hito"] == "scenario_ready"].sort_values("ts") if not bit.empty else bit
    cuts = []
    if not bit.empty:
        cut_hitos = bit[bit["hito"].isin(["scenario_ready", "teardown_start", "fin_presentacion"])].sort_values("ts")
        spans = []
        ready_rows = list(readys.itertuples())
        for i, r in enumerate(ready_rows):
            start = r.t
            later = cut_hitos[cut_hitos["ts"] > r.ts]
            end = later["t"].iloc[0] if not later.empty else t_max
            spans.append((r.escenario, start, end))
        cuts = spans

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 5.2), sharex=True)

    ax1.plot(host["t"], host["cpu_pct"], color="#111827", lw=1.1, label="CPU host (%)")
    ax1.set_ylabel("CPU host (%)")
    ax1.set_ylim(0, max(100, host["cpu_pct"].max() * 1.1))
    ax1.grid(alpha=0.25)

    ax2.plot(host["t"], host["mem_mb"], color="#047857", lw=1.1, label="Memoria host (MB)")
    ax2.set_ylabel("Memoria host (MB)")
    ax2.grid(alpha=0.25)

    # Bandas + lineas de inicio por escenario
    for esc, start, end in cuts:
        color = ESC_COLORS.get(esc, "#6b7280")
        for ax in (ax1, ax2):
            ax.axvspan(start, end, color=color, alpha=0.07)
            ax.axvline(start, color=color, lw=1.4, ls="--")
        # tiempo de montaje desde la nota deploy_seconds del scenario_ready
        secs = ""
        row = readys[(readys["escenario"] == esc) & (readys["t"] == start)]
        if not row.empty:
            nota = str(row["notas"].iloc[0])
            if "deploy_seconds=" in nota:
                secs = " · montaje " + nota.split("deploy_seconds=")[1].split()[0] + "s"
        ax1.annotate(f"{ESC_LABEL.get(esc, esc)}\n{start.strftime('%H:%M:%S')}{secs}",
                     xy=(start, ax1.get_ylim()[1]), xytext=(4, -4),
                     textcoords="offset points", va="top", ha="left",
                     fontsize=8, color=color, fontweight="bold")

    # marcas manuales
    if not bit.empty:
        for m in bit[bit["hito"] == "marca"].itertuples():
            for ax in (ax1, ax2):
                ax.axvline(m.t, color="#6b7280", lw=0.8, ls=":")
            ax1.annotate(str(m.notas), xy=(m.t, ax1.get_ylim()[1] * 0.85),
                         fontsize=7, color="#374151", rotation=90, va="top")

    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    fig.autofmt_xdate()
    dur_min = (t_max - t_min).total_seconds() / 60.0
    fig.suptitle(f"Consumo de recursos del Raspberry Pi durante la presentacion\n"
                 f"{t_min.strftime('%Y-%m-%d %H:%M:%S')} → {t_max.strftime('%H:%M:%S')}  "
                 f"({dur_min:.1f} min)", fontsize=12, fontweight="bold")
    ax1.legend(loc="upper right", fontsize=8)
    ax2.legend(loc="upper right", fontsize=8)
    fig.tight_layout(rect=[0, 0, 1, 0.95])

    out = d / "presentacion_recursos.png"
    fig.savefig(out, dpi=140)
    print(f"grafica -> {out}")

    # Resumen de tiempos de montaje
    if not readys.empty:
        print("\nTiempos de montaje (deploy hasta listo):")
        for r in readys.itertuples():
            nota = str(r.notas)
            secs = nota.split("deploy_seconds=")[1].split()[0] if "deploy_seconds=" in nota else "?"
            print(f"  {ESC_LABEL.get(r.escenario, r.escenario):20s} inicio {r.t.strftime('%H:%M:%S')}  montaje {secs}s")


if __name__ == "__main__":
    main()
