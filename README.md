# tesis/metrics — Harness de medición (§4 del marco teórico)

Recolecta las métricas del **§4** del marco teórico (satisfacción, desempeño
funcional, consumo de recursos, tiempo de montaje/despliegue) para los tres
escenarios, **uno a la vez**.

> **Guía de uso rápido.** El documento conceptual y de auditoría —qué mide cada
> métrica, por qué se eligió, su veredicto— está en [`METRICAS.md`](METRICAS.md).

## Arquitectura

**Toda la recolección corre EN EL PI.** La laptop solo dispara la sesión por SSH y descarga
los CSV para graficar — nunca recolecta (pedido del tutor). Un solo reloj (el de la Pi).

```
┌──────────────── Pi 3B+ (192.168.1.10) — RECOLECTA TODO ───────────────┐
│  contenedores del escenario (escN-nodered, …)                          │
│  collect_resources.py   ──► resources.csv      (psutil + docker SDK)   │
│  collectors/collect_router.py ──► router*.csv  (ssh OpenWrt 192.168.1.1)│
│  collectors/docker_events_collector.py ──► docker_events.csv           │
│  collectors/target_health_probe.py ──► target_health.csv (solo Esc3)   │
│  collectors/measure_deploy.py ──► deploy.csv                           │
│  middleware Node-RED    ──► backend_latency.csv                        │
│  /api/export_state      ──► tablas de dominio                          │
│  session.sh ── orquesta (con guard: aborta si no corre en el Pi)       │
└────────────────────────────┬───────────────────────────────────────────┘
                             │ la laptop dispara por SSH y, al cerrar,
                             │ descarga la carpeta de sesión (scp)
                             ▼
                  ┌───────── Laptop (solo visualiza) ──────────┐
                  │  gateway/session.ps1  (SSH + scp, no mide)  │
                  │  plot_scenario.py   ·   analyze.ipynb       │
                  └─────────────────────────────────────────────┘
```

## Outputs por sesión

Una carpeta `sessions/<fecha>_<escenario>/` (ej. `2026-05-22_esc1/`):

| Archivo | Origen | Cadencia |
|---|---|---|
| `resources.csv` | `pi/collect_resources.py` (psutil + docker SDK) | 1/s |
| `router.csv` | `collectors/collect_router.py` (tráfico agregado) | 1/5s |
| `router_devices.csv` | `collectors/collect_router.py` (MAC/IP/hostname por equipo) | 1/5s |
| `router_resources.csv` | `collectors/collect_router.py` (CPU/RAM del router) | 1/5s |
| `backend_latency.csv` | middleware Node-RED (`metrics_middleware.js`) | 1/petición |
| `deploy.csv` | `collectors/measure_deploy.py` | 1/despliegue |
| `target_health.csv` | `collectors/target_health_probe.py` (solo Esc3) | 1/s |
| `docker_events.csv` | `collectors/docker_events_collector.py` | por evento |
| `loadtest.csv` | `collectors/loadgen.py` (solo lab) | 1/escalón |
| `survey.csv` | form HTML → `/api/survey` | 1/encuestado |
| `events.csv` | `session.sh log` (anotaciones del operador) | discreto |
| tablas de dominio | `fetch_export_state.py` ← `/api/export_state` (al cerrar) | 1 vez |

## Uso por sesión

Primero **dejar desplegado solo el escenario a medir** (bajar los otros dos en el Pi).

**Desde la laptop (recomendado)** — el wrapper dispara `session.sh` EN EL PI por SSH y, al
cerrar, descarga la carpeta de sesión. La laptop nunca recolecta:

```powershell
# PowerShell en la laptop (gateway Windows)
cd tesis_metrics\gateway
.\session.ps1 start esc1     # arranca colectores EN EL PI (escenario aún abajo)
.\session.ps1 deploy         # mide tiempo de despliegue en frío -> deploy.csv
.\session.ps1 log montaje_fisico_s 95   # montaje físico (cronómetro del operador)
# ... corre la demo ...
.\session.ps1 status         # colectores activos y filas por CSV (en el Pi)
.\session.ps1 end            # cierra en el Pi y descarga la carpeta a sessions\
```

**Directo en el Pi** (equivalente; `PI_PASS`/`ROUTER_PASS` en `.env` del repo del Pi):

```bash
# por SSH dentro del Pi, en ~/tesis_metrics_repo
./session.sh start esc1      # session.sh aborta si NO corre en el Pi (guard de host)
./session.sh deploy ; ./session.sh status ; ./session.sh end
```

Pruebas de carga sintética (**solo en laboratorio**, nunca en demo pública; corre en el Pi):

```bash
python3 collectors/loadgen.py --config config/esc1.yaml --output-dir sessions/<id>/
```

## Análisis y gráficas

```bash
# Gráfica de recursos por escenario (eje X = tiempo, eje Y = consumo):
python3 plot_scenario.py sessions/2026-05-22_esc1

# Consolidado comparativo de los 3 escenarios:
python3 plot_scenario.py --general sessions/2026-05-22_esc1 \
    sessions/2026-05-22_esc2 sessions/2026-05-22_esc3 --out-dir sessions/

# Análisis completo (tablas + gráficos del capítulo de Resultados):
jupyter notebook analyze.ipynb
```

## Modos de sesión

- **`session.sh`** (este flujo) — mide **un escenario a fondo**, incluidas las tablas
  de dominio (auditoría Esc1, correos Esc2, atacantes Esc3). **Es el que produce datos
  analizables.**
- **`presentation.sh`** — monitor continuo de recursos para toda una jornada; **no**
  captura tablas de dominio. Ver la comparación en [`METRICAS.md` §7](METRICAS.md).

## Filosofía

- **Mediciones reales, no simuladas**: psutil lee `/proc`; httpx hace HTTP real;
  Node-RED mide en el handler verdadero; el router responde por SSH.
- **Mínimo riesgo de error**: bibliotecas estándar (psutil, httpx, asyncio, pandas);
  CSVs append-only; sin DB; el agente del Pi es un proceso suelto bajo `nohup`.
- **Un solo reloj**: como todos los colectores corren en la Pi, los CSV comparten el reloj de
  la Pi y se unen por timestamp sin sincronizar nada. (`session.sh` conserva un self-check de
  reloj por seguridad.)
- **La laptop solo visualiza**: dispara la sesión por SSH y descarga los CSV; `session.sh` lleva
  un guard que aborta si se ejecuta fuera del Pi.

## Estructura

```
metrics/
├── README.md                  # esta guía
├── METRICAS.md                # documento conceptual + auditoría
├── session.sh                 # orquestador EN EL PI (start/deploy/log/status/end)
├── presentation.sh            # monitor continuo de jornada (en el Pi)
├── plot_scenario.py           # gráficas por escenario + consolidado (en la laptop)
├── executive_report.py        # informe ejecutivo PDF (modo presentación)
├── analyze.ipynb              # análisis del §4 (en la laptop)
├── gateway/
│   └── session.ps1            # wrapper de la laptop: dispara por SSH + descarga (no mide)
├── pi/
│   ├── collect_resources.py   # corre en el Pi
│   └── install.sh             # despliega agente + venv al Pi
├── collectors/                # corren EN EL PI (los lanza session.sh)
│   ├── collect_router.py      # tráfico + dispositivos + recursos del router (ssh al OpenWrt)
│   ├── measure_deploy.py      # tiempo de despliegue (compose up -> HTTP 200)
│   ├── target_health_probe.py # disponibilidad del target (Esc3)
│   ├── docker_events_collector.py
│   ├── fetch_export_state.py  # tablas de dominio
│   └── loadgen.py             # rampa de carga sintética (solo lab)
├── flows_patch/
│   └── metrics_middleware.js  # latencia backend en Node-RED
├── survey/
│   ├── survey_template.json   # encuesta global (editable sin tocar código)
│   └── form.html
├── config/{esc1,esc2,esc3}.yaml
└── sessions/                  # outputs (gitignored)
```
