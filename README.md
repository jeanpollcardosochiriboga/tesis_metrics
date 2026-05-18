# tesis/metrics — Harness de medición para §4 del marco teórico

Recolecta las cuatro familias de métricas del §4 del marco teórico de la tesis CEC-EPN
(satisfacción, desempeño funcional, consumo de recursos, tiempo de montaje) para cada
uno de los tres escenarios (Esc1, Esc2, Esc3), uno a la vez.

## Arquitectura

```
┌──────────── Pi 3B+ (192.168.1.10) ──────────────┐    ┌───────── Laptop ──────────┐
│  scenario container (esc1/2/3-nodered, etc.)    │    │                            │
│     ▲                                            │    │  collect_router.py         │
│     │ psutil + docker SDK                        │    │   └─ ssh OpenWrt (5 s)     │
│  collect_resources.py ──► resources.csv          │    │                            │
│  Node-RED subflow      ──► backend_latency.csv   │    │  loadgen.py                │
│                                                  │    │   └─ rampa asyncio         │
└──────────────────────────────────────────────────┘    │                            │
               │                                        │  session.sh                │
               │ scp al final de la sesión              │   └─ orquesta todo         │
               └──────────────────────────────────────► │                            │
                                                        │  analyze.ipynb             │
                                                        └────────────────────────────┘
```

## Outputs por sesión

Una carpeta `sessions/<scenario>_<fecha>_<hhmm>/` con 6 CSVs:

| Archivo | Origen | Granularidad |
|---|---|---|
| `resources.csv` | psutil + docker SDK en el Pi | 1 sample/s |
| `router.csv` | ssh al OpenWrt | 1 sample/5s |
| `backend_latency.csv` | Subflow Node-RED instrumentado | 1 fila/petición |
| `loadtest.csv` | loadgen.py | 1 fila/escalón de concurrencia |
| `events.csv` | Anotaciones manuales del operador | discreto |
| `survey.csv` | POST del form HTML al endpoint /api/survey | 1 fila/encuestado |

## Uso rápido

```bash
# Primera vez: instalar agente en el Pi
./pi/install.sh raspberry1@192.168.1.10

# Por cada sesión:
./session.sh start esc1                       # arranca todo en paralelo
./session.sh log first_user                   # anota evento durante demo
./session.sh log demo_end
./session.sh end                              # detiene, hace scp del CSV del Pi

# Pruebas de carga sintética (solo en lab):
python3 laptop/loadgen.py --config config/esc1.yaml --session sessions/<id>/

# Análisis:
jupyter notebook analyze.ipynb
```

## Filosofía

- **Mediciones reales, no simuladas**: psutil lee `/proc`; httpx hace HTTP real; Node-RED
  mide `Date.now()` en el handler real del request.
- **Mínimo riesgo de errores**: bibliotecas estándar (psutil, httpx, asyncio, pandas);
  sin parsear stdout; CSVs append-only; sin systemd; sin DB.
- **Cero contenedores nuevos en el Pi**: el agente es un proceso Python suelto bajo `nohup`.

## Estructura

```
metrics/
├── README.md
├── requirements.txt
├── session.sh                       # orquestador (start/log/end)
├── pi/
│   ├── collect_resources.py         # corre en el Pi
│   └── install.sh                   # despliega script + venv al Pi
├── laptop/
│   ├── collect_router.py            # ssh OpenWrt
│   ├── loadgen.py                   # rampa asyncio
│   └── pull_pi_csv.sh               # scp del CSV del Pi
├── flows_patch/
│   └── esc1_latency_nodes.json      # subflow Node-RED para latencia
├── survey/
│   ├── survey_template.json         # 10 preguntas (editables por tutor)
│   ├── form.html                    # renderiza el template
│   └── api_survey.md                # spec del endpoint POST /api/survey
├── config/
│   ├── esc1.yaml
│   ├── esc2.yaml
│   └── esc3.yaml
├── sessions/                        # outputs (gitignored)
└── analyze.ipynb                    # tablas y gráficos del §4
```
