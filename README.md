# tesis/metrics — Harness de medición (§4 del marco teórico)

Recolecta las métricas del **§4** del marco teórico (satisfacción, desempeño
funcional, consumo de recursos, tiempo de montaje/despliegue) para los tres
escenarios, **uno a la vez**.

> **Guía de uso rápido.** El documento conceptual y de auditoría —qué mide cada
> métrica, por qué se eligió, su veredicto— está en [`METRICAS.md`](METRICAS.md).

## Arquitectura

```
┌──────────── Pi 3B+ (192.168.1.10) ──────────────┐    ┌───────── Laptop ──────────┐
│  contenedores del escenario (escN-nodered, …)   │    │  collect_router.py         │
│     ▲                                            │    │   └─ ssh OpenWrt (5 s)     │
│     │ psutil + docker SDK                        │    │  docker_events_collector.py│
│  collect_resources.py ──► resources.csv          │    │  target_health_probe.py    │
│  middleware Node-RED   ──► backend_latency.csv   │    │  measure_deploy.py         │
│  /api/export_state     ──► tablas de dominio     │    │  loadgen.py (solo lab)     │
└──────────────────────────────────────────────────┘    │  session.sh ── orquesta    │
               │ scp / fetch al cerrar la sesión        │  plot_scenario.py          │
               └──────────────────────────────────────► │  analyze.ipynb             │
                                                        └────────────────────────────┘
```

## Outputs por sesión

Una carpeta `sessions/<fecha>_<escenario>/` (ej. `2026-05-22_esc1/`):

| Archivo | Origen | Cadencia |
|---|---|---|
| `resources.csv` | `pi/collect_resources.py` (psutil + docker SDK) | 1/s |
| `router.csv` | `laptop/collect_router.py` (tráfico agregado) | 1/5s |
| `router_devices.csv` | `collect_router.py` (MAC/IP/hostname por equipo) | 1/5s |
| `router_resources.csv` | `collect_router.py` (CPU/RAM del router) | 1/5s |
| `backend_latency.csv` | middleware Node-RED (`metrics_middleware.js`) | 1/petición |
| `deploy.csv` | `laptop/measure_deploy.py` | 1/despliegue |
| `target_health.csv` | `laptop/target_health_probe.py` (solo Esc3) | 1/s |
| `docker_events.csv` | `laptop/docker_events_collector.py` | por evento |
| `loadtest.csv` | `laptop/loadgen.py` (solo lab) | 1/escalón |
| `survey.csv` | form HTML → `/api/survey` | 1/encuestado |
| `events.csv` | `session.sh log` (anotaciones del operador) | discreto |
| tablas de dominio | `fetch_export_state.py` ← `/api/export_state` (al cerrar) | 1 vez |

## Uso por sesión

Primero **dejar desplegado solo el escenario a medir** (bajar los otros dos en el Pi).

```bash
# Variables PI_PASS y ROUTER_PASS en .env
./session.sh start esc1     # arranca colectores (escenario aún abajo)
./session.sh deploy         # mide tiempo de despliegue en frío -> deploy.csv
# El montaje físico (conectar router+Pi+laptop) se mide con cronómetro y se anota:
./session.sh log montaje_fisico_s 95
# ... corre la demo ...
./session.sh log primer_usuario
./session.sh status         # muestra colectores activos y filas por CSV
./session.sh end            # detiene todo, hace scp + fetch de tablas de dominio
```

Pruebas de carga sintética (**solo en laboratorio**, nunca en demo pública):

```bash
python3 laptop/loadgen.py --config config/esc1.yaml --output-dir sessions/<id>/
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
- **Reloj sincronizado**: `session.sh` aborta si el offset Pi↔laptop supera 2 s, para
  poder unir CSVs de ambos hosts por timestamp.

## Estructura

```
metrics/
├── README.md                  # esta guía
├── METRICAS.md                # documento conceptual + auditoría
├── session.sh                 # orquestador (start/deploy/log/status/end)
├── presentation.sh            # monitor continuo de jornada
├── plot_scenario.py           # gráficas por escenario + consolidado
├── executive_report.py        # informe ejecutivo PDF (modo presentación)
├── analyze.ipynb              # análisis del §4
├── pi/
│   ├── collect_resources.py   # corre en el Pi
│   └── install.sh             # despliega agente + venv al Pi
├── laptop/
│   ├── collect_router.py      # tráfico + dispositivos + recursos del router
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
