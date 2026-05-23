#!/usr/bin/env python3
"""Informe ejecutivo de metricas de la presentacion (para el tutor).

Genera <dir>/informe_ejecutivo.md (y la figura presentacion_recursos.png) con:
  - Tabla de tiempos de montaje por escenario (deploy hasta listo).
  - Grafica del consumo de CPU/memoria continuo, con bandas por escenario.
  - Tabla de consumo por escenario (CPU promedio/max, memoria max).
  - Bitacora con la hora exacta de inicio de cada prototipo.
  - Interpretacion breve.

presentation.sh report lo convierte a PDF con la plantilla eisvogel.

Uso: python3 executive_report.py <dir-de-la-presentacion>
"""
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

_LOCAL_OFFSET = -time.timezone
ESC_LABEL = {"esc1": "Esc1 · Monitoreo de red", "esc2": "Esc2 · Phishing", "esc3": "Esc3 · DoS"}


def to_local(s):
    return pd.to_datetime(s + _LOCAL_OFFSET, unit="s")


def fnum(x, n=1):
    return f"{x:.{n}f}" if pd.notna(x) else "—"


def main():
    if len(sys.argv) < 2:
        sys.exit("uso: executive_report.py <dir>")
    d = Path(sys.argv[1])
    res = pd.read_csv(d / "resources.csv")
    res["t"] = to_local(res["ts"])
    host = res[res["source"] == "host"].sort_values("t")
    bit = pd.read_csv(d / "bitacora.csv") if (d / "bitacora.csv").exists() else pd.DataFrame()
    if not bit.empty:
        bit["t"] = to_local(bit["ts"])
        bit[["escenario", "notas"]] = bit[["escenario", "notas"]].fillna("")

    # Generar la figura reutilizando plot_presentation.py
    py = sys.executable
    subprocess.run([py, str(Path(__file__).parent / "plot_presentation.py"), str(d)], check=False)

    t0, t1 = host["t"].min(), host["t"].max()
    dur_min = (t1 - t0).total_seconds() / 60.0

    readys = bit[bit["hito"] == "scenario_ready"].sort_values("ts") if not bit.empty else pd.DataFrame()
    cut_hitos = bit[bit["hito"].isin(["scenario_ready", "scenario_down", "teardown_start", "fin_presentacion"])].sort_values("ts") if not bit.empty else pd.DataFrame()

    # --- Tabla de montaje + spans por escenario ---
    mount_rows, span_rows = [], []
    for r in readys.itertuples():
        secs = "—"
        nota = str(r.notas)
        if "deploy_seconds=" in nota:
            secs = nota.split("deploy_seconds=")[1].split()[0]
        mount_rows.append((ESC_LABEL.get(r.escenario, r.escenario), r.t.strftime("%H:%M:%S"), secs))
        # span hasta el siguiente corte
        later = cut_hitos[cut_hitos["ts"] > r.ts]
        end = later["t"].iloc[0] if not later.empty else t1
        seg = host[(host["t"] >= r.t) & (host["t"] <= end)]
        if not seg.empty:
            span_rows.append((
                ESC_LABEL.get(r.escenario, r.escenario),
                f"{(end - r.t).total_seconds()/60:.1f}",
                fnum(seg["cpu_pct"].mean()), fnum(seg["cpu_pct"].max()),
                fnum(seg["mem_mb"].mean(), 0), fnum(seg["mem_mb"].max(), 0),
            ))

    cpu_avg, cpu_max = host["cpu_pct"].mean(), host["cpu_pct"].max()
    mem_max = host["mem_mb"].max()

    L = []
    L.append("# Informe ejecutivo de métricas — presentación del prototipo\n")
    L.append(f"**Equipo medido:** Raspberry Pi 3B+ (servidor de los 3 escenarios).  ")
    L.append(f"**Ventana:** {t0.strftime('%Y-%m-%d %H:%M:%S')} → {t1.strftime('%H:%M:%S')} ({dur_min:.1f} min).  ")
    L.append("**Muestreo:** 1 medición por segundo (host y contenedores).\n")

    L.append("## 1. Tiempo de montaje de cada escenario\n")
    L.append("Segundos desde que se levanta el escenario (`docker compose up`) hasta que el dashboard responde (servicio listo). Corresponde a §4.4 del marco teórico (plug-and-play).\n")
    if mount_rows:
        L.append("| Escenario | Hora de inicio | Montaje (s) |")
        L.append("|---|---|---|")
        for esc, hora, secs in mount_rows:
            L.append(f"| {esc} | {hora} | {secs} |")
    else:
        L.append("_No se registraron arranques de escenario en esta sesión._")
    L.append("")

    L.append("## 2. Consumo de recursos durante la presentación\n")
    L.append("\\begin{center}")
    L.append("\\includegraphics[width=0.95\\textwidth]{presentacion_recursos.png}")
    L.append("\\end{center}\n")
    L.append("*Figura 1. Consumo de CPU y memoria del Raspberry Pi durante la presentación, con bandas de color por escenario y la hora de inicio de cada uno.*\n")
    L.append(f"Resumen global: **CPU promedio {fnum(cpu_avg)} %**, pico {fnum(cpu_max)} %; **memoria máxima {fnum(mem_max,0)} MB**.\n")

    if span_rows:
        L.append("### Consumo por escenario\n")
        L.append("| Escenario | Duración (min) | CPU prom (%) | CPU pico (%) | Mem prom (MB) | Mem máx (MB) |")
        L.append("|---|---|---|---|---|---|")
        for row in span_rows:
            L.append("| " + " | ".join(row) + " |")
        L.append("")

    L.append("## 3. Bitácora — hora de inicio de cada prototipo\n")
    L.append("Registro de hitos para asociar cada tramo de la gráfica con su escenario.\n")
    if not bit.empty:
        L.append("| Hora | Hito | Escenario | Notas |")
        L.append("|---|---|---|---|")
        for r in bit.itertuples():
            L.append(f"| {r.t.strftime('%H:%M:%S')} | {r.hito} | {r.escenario or ''} | {str(r.notas) or ''} |")
    L.append("")

    L.append("## 4. Interpretación\n")
    interp = (f"El Raspberry Pi 3B+ sostuvo toda la presentación con un consumo de CPU promedio de "
              f"{fnum(cpu_avg)} % (pico {fnum(cpu_max)} %) y memoria máxima de {fnum(mem_max,0)} MB, "
              f"holgado frente a sus ~900 MB útiles. ")
    if mount_rows:
        nums = [float(s) for _, _, s in mount_rows if s not in ("—", "?")]
        if nums:
            interp += (f"Los escenarios quedaron listos en un rango de {min(nums):.0f}–{max(nums):.0f} s desde su arranque, "
                       f"evidenciando el carácter plug-and-play del prototipo. ")
    interp += "El muestreo continuo permite asociar cada tramo de consumo con el escenario activo según la bitácora."
    L.append(interp + "\n")

    out = d / "informe_ejecutivo.md"
    out.write_text("\n".join(L), encoding="utf-8")
    print(f"informe -> {out}")


if __name__ == "__main__":
    main()
