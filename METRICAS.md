# Métricas del prototipo — qué se mide, por qué y cómo

> Documento de auditoría y diseño del harness de medición (`tesis/metrics/`).
> Instrumenta el **Objetivo Específico 4** del plan F_AA_234A y el **§4 del marco
> teórico** (`esquema_marco_teorico_v4.md`). Para cada métrica responde tres
> preguntas — *qué mide*, *por qué se eligió*, *cómo funciona* — y cierra con un
> **veredicto**: mantener, cambiar o mejorar.
>
> `README.md` queda como guía de uso rápido. Este archivo es el documento conceptual.

---

## 1. Propósito y trazabilidad

El prototipo debe validarse con datos, no con impresiones. El §4 del marco teórico
fija cuatro familias de métricas. Cada familia se mide con scripts reales que
escriben tablas CSV. Ninguna cifra se inventa: `psutil` lee `/proc`, `httpx` hace
HTTP real, Node-RED mide `Date.now()` en el handler del request, el router responde
por SSH.

| Familia (§4) | Métrica concreta | Archivo CSV | Script productor | Tutor |
|---|---|---|---|---|
| §4.1 Satisfacción | SUS reducido + pedagógicas | `survey.csv` | form HTML → `/api/survey` | T8–T10 |
| §4.2 Desempeño funcional | Latencia backend | `backend_latency.csv` | `flows_patch/metrics_middleware.js` | — |
| §4.2 Desempeño funcional | Concurrencia real (teléfonos) | `router.csv` | `collectors/collect_router.py` | T2 |
| §4.2 Desempeño funcional | Disponibilidad real del target (Esc3) | `target_health.csv` | `collectors/target_health_probe.py` | — |
| §4.3 Consumo de recursos | CPU/RAM/red del Pi | `resources.csv` | `pi/collect_resources.py` | T5 |
| §4.2/4.3 | Dispositivos del router (MAC/IP) | `router_devices.csv` | `collectors/collect_router.py` | T2 |
| §4.3 Consumo de recursos | CPU/RAM del router | `router_resources.csv` | `collectors/collect_router.py` (`/proc`) | T3 |
| §4.4 Tiempo de montaje físico | Conexión router + Pi + laptop | cronómetro (manual) | operador | — |
| §4.4 Tiempo de despliegue | Arranque de cada escenario en el Pi | `deploy.csv` | `collectors/measure_deploy.py` (`session.sh deploy`) | — |
| **Dominio Esc2** | Correos capturados / enviados / clicks | `email_capturas/envios/clicks.csv` | `/api/export_state` | — |
| **Dominio Esc3** | N.º de atacantes + RPS (actual/pico) | `esc3_stats_snapshot.csv` | `/api/export_state` | — |
| Dominio Esc1 | Auditoría de usuarios detectados | `auditoria_usuarios.csv` | `/api/export_state` | — |
| Forense | Ciclo de vida de contenedores | `docker_events.csv` | `collectors/docker_events_collector.py` | — |

> **Carga sintética (`loadgen.py` → `loadtest.csv`) NO es métrica de Resultados.** Es una
> prueba de estrés **opcional de laboratorio** para hallar el límite teórico del servidor;
> no se corre con público y no se reporta en la tesis. La demo real se mide con las
> **tablas de dominio** y las estadísticas en vivo de arriba.

Las columnas "Tutor" enlazan cada métrica con las recomendaciones del §9.

> **Dónde corre cada colector (decisión de arquitectura).** **Toda la recolección corre EN EL
> PI**: `pi/collect_resources.py` se mide a sí mismo, y los scripts de `collectors/`
> (`collect_router.py`, `target_health_probe.py`, `docker_events_collector.py`,
> `measure_deploy.py`, `fetch_export_state.py`) los lanza `session.sh` **en el Pi**. El router se
> lee por SSH **desde el Pi** (misma LAN), no desde la laptop. **La laptop solo visualiza**:
> dispara la sesión por SSH (`gateway/session.ps1`) y descarga los CSV para graficar
> (`plot_scenario.py`, `analyze.ipynb`). Ventaja: un solo reloj (el del Pi) → los CSV se cruzan por
> timestamp sin sincronizar nada, y la medición no depende de que la laptop siga conectada.
> `session.sh` lleva un **guard** que aborta si se ejecuta fuera del Pi.

---

## 2. Organización: por escenario + una general

El tutor pide dos niveles de lectura (T1):

- **Por escenario** — cada sesión mide un solo escenario desplegado y produce su
  propia carpeta de CSVs. Es el nivel de detalle.
- **General (consolidado comparativo)** — una tabla y una gráfica que comparan los
  tres escenarios entre sí: consumo del Pi, tiempo de montaje y satisfacción. Se
  arma en el notebook a partir de las tres carpetas. La **encuesta es global** y
  vive en este nivel (no se mide por escenario — ver §10).

### Nomenclatura de carpetas (T7)

El tutor sugiere `22/05/2026_esc1`. La barra `/` es ilegal en rutas, así que se
adopta el formato ISO, que además ordena cronológicamente solo:

```
sessions/2026-05-22_esc1/
sessions/2026-05-22_esc2/
sessions/2026-05-22_esc3/
```

> **Implementado**: `session.sh` ya nombra `2026-05-22_esc1` (ver `cmd_start`,
> formato `$(date +%Y-%m-%d)_${scenario}`); solo desambigua con la hora si ya
> existe una carpeta del mismo día y escenario.

---

## 3. Las cuatro familias del §4

### 3.1. Satisfacción de la audiencia (§4.1)

Resumen aquí; el detalle de ítems y su sustento académico está en el §10.

- **Qué mide**: usabilidad percibida del prototipo completo y dos señales
  pedagógicas (comprensión e intención de recomendar la carrera).
- **Por qué se eligió**: el SUS es el instrumento de usabilidad más validado de la
  literatura [25]; su versión reducida conserva la correlación con menos preguntas,
  clave para una audiencia que responde de pie en una feria.
- **Cómo funciona**: un formulario HTML renderiza `survey/survey_template.json` y
  hace POST a `/api/survey`; Node-RED añade una fila a `survey.csv`.
- **Veredicto**: **mantener**. Instrumento sólido y editable sin tocar código.

### 3.2. Latencia de procesamiento del backend (§4.2)

- **Qué mide**: el tiempo entre que Node-RED recibe la petición HTTP y emite la
  respuesta. No incluye el tramo WiFi del teléfono ni el render del navegador.
- **Por qué se eligió**: es la latencia que se reporta de forma estándar en
  benchmarks de servidores. El tramo WiFi y el render dependen de hardware y red no
  controlados, así que se excluyen por rigor metodológico (§4.2 del marco).
- **Cómo funciona**: `metrics_middleware.js` se engancha como `httpNodeMiddleware`
  en `settings.js`. Mide con `process.hrtime.bigint()` y, al terminar la respuesta
  (`res.on('finish')`), añade una línea a `backend_latency.csv`:
  `ts, endpoint, method, processing_ms, status_code`. Es *fire-and-forget*: el
  `appendFile` asíncrono no bloquea la petición.
- **Veredicto**: **mantener**. Medición real, no invasiva, en el handler verdadero.

### 3.3. Capacidad de respuesta bajo concurrencia (§4.2)

Dos vistas complementarias.

**(a) Teléfonos reales** — concurrencia genuina del público.

- **Qué mide**: cuántas estaciones WiFi están asociadas al AP del público durante
  la demo, muestreado en el router.
- **Por qué se eligió**: es la concurrencia verdadera del evento, no una simulación.
- **Cómo funciona**: `collect_router.py` corre **en el Pi** y entra por SSH al OpenWrt
  cada 5 s (misma LAN), corre `iw dev <iface> station dump` y cuenta líneas `Station`;
  lee `/proc/net/dev` para RX/TX. Escribe `router.csv`. (Antes corría en la laptop; se movió
  al Pi para que la laptop solo visualice.)
- **Veredicto**: **implementado**. Además del conteo en `router.csv`, `collect_router.py`
  ahora cruza `iw station dump` con las leases DHCP y escribe `router_devices.csv`
  (MAC, IP, hostname, señal, tráfico por equipo) — T2, §4.1.

**(b) Carga sintética — fuera del alcance de Resultados.** `loadgen.py` existe como
prueba de estrés **opcional de laboratorio** (rampa de concurrencia → `loadtest.csv`
con `rps`, `error_rate`, percentiles y columna `knee`). **No se reporta en la tesis ni
se corre con público**: la demo real se mide con las métricas reales de abajo. Se
conserva el script por si se quiere un dato de límite teórico en lab.

**Métricas reales de Esc3 (DoS)** — lo que sí va a Resultados.

- **N.º de atacantes y RPS** — *qué mide*: cuántos equipos atacan (`devices`) y las
  peticiones por segundo (`currentRps`, `peakRps`). *Por qué*: son el efecto medible y
  no ambiguo del ataque. *Cómo*: el orquestador acumula snapshots; `/api/export_state`
  los entrega como serie de tiempo → `esc3_stats_snapshot.csv`.
- **Disponibilidad real del target** — *qué mide*: si el servidor Flask víctima responde
  y cuánto tarda, a lo largo del tiempo. *Por qué*: es la prueba objetiva del DoS, sin
  depender de la animación de fases. *Cómo*: `target_health_probe.py` sondea
  `GET http://Pi:5000/` cada 1 s y registra `status_code` y `response_ms` →
  `target_health.csv`.
- **Modelo de la demo (decidido)**: los teléfonos accionan la **visualización**; el
  **operador dispara el flood real** que degrada el target. Graficar RPS y
  disponibilidad real en el mismo eje de tiempo muestra la caída de forma inequívoca.
- **Importante — el "caído" visual NO es métrica**: el estado rojo/caído que ve el
  público lo acciona el contador de presiones (motor de fases), y puede desacoplarse de
  la salud real del servidor (de ahí la ambigüedad observada: caída sin flood real, o
  flood real sin caída visual). Para la tesis se reporta `target_health.csv` + RPS, no
  el estado visual.
- **Veredicto**: **mantener** atacantes, RPS y disponibilidad real.

### 3.4. Consumo de recursos en hardware de borde (§4.3)

- **Qué mide**: CPU, memoria y red del Pi (host y por contenedor) durante toda la
  sesión.
- **Por qué se eligió**: demuestra que un Pi 3B+ sostiene el escenario — sustenta la
  portabilidad y el bajo costo del prototipo (§2.1, §6.1).
- **Cómo funciona**: `collect_resources.py` corre en el Pi. Usa `psutil` para el host
  y el docker SDK para cada contenedor; resuelve la RAM por contenedor con tres
  estrategias en cascada (cgroup v1 → cgroup v2 → `psutil` sobre el PID y sus hijos),
  porque el controlador de memoria de cgroups viene desactivado por defecto en
  Raspberry Pi OS. Muestrea CPU, memoria y red cada 1 s a `resources.csv`.
- **Veredicto**: **mantener** CPU/RAM/red y formalizar la medición **aislada por
  escenario** (T5, §5). **No se mide disco** — el cuello de botella del Pi 3B+ es RAM
  y CPU, no almacenamiento; añadir disco sería ruido sin valor analítico.

### 3.5. Tiempo de montaje y despliegue (§4.4)

Se separan en dos medidas, porque son cosas distintas.

**(a) Montaje físico — cronómetro manual.**

- **Qué mide**: cuánto se tarda en dejar operativo el hardware: conectar el router,
  el Pi y la laptop, y energizarlos hasta que el sistema está listo para el primer
  participante.
- **Por qué se eligió**: cierra el círculo con el ideal plug-and-play (§2.2) y con
  "número de pasos manuales" del §4.4. Es una medición de campo, no de software.
- **Cómo funciona**: el operador lo mide con cronómetro. Arranca al energizar y para
  cuando el primer participante puede interactuar. Se anota a mano (en `events.csv`
  con `session.sh log montaje_fisico_s <n>`, o en bitácora de papel).
- **Veredicto**: **mantener** como medición manual del operador.

**(b) Tiempo de despliegue de cada escenario en el Pi — automatizado.**

- **Qué mide**: los segundos desde `docker compose up` hasta que el dashboard del
  escenario responde HTTP 200. El §4.4 del marco exige los dos tiempos (montaje y
  despliegue), así que **no es opcional**.
- **Por qué se eligió**: complementa el montaje físico. Mientras (a) mide el trabajo
  del operador, (b) mide el arranque del software en el hardware de borde.
- **Cómo funciona**: `collectors/measure_deploy.py` baja el escenario (arranque en frío),
  lanza `docker compose up -d` en el Pi por SSH, cronometra hasta el primer HTTP 200 y
  escribe `deploy.csv` (`ts, scenario, deploy_seconds, ready, http_status`). Se invoca
  con `./session.sh deploy` con una sesión activa:

  ```bash
  ./session.sh start esc1     # arranca colectores (escenario aún abajo)
  ./session.sh deploy         # mide despliegue en frío -> deploy.csv
  # ... demo ...
  ./session.sh end
  ```

  El número es fiable porque el escenario se levanta *desde cero* dentro de la ventana,
  y `resources.csv` además captura el pico de arranque. **No** usa el `StartedAt`
  (el viejo `deploy_seconds` automático estaba roto — ver §9, hallazgo 1).
- **Veredicto**: **implementado**. `measure_deploy.py` + `session.sh deploy`.

---

## 4. Métricas del router (Esc1) — diseño reforzado

El tutor pide más datos del router (T2, T3, T3b). Hoy `router.csv` solo guarda:
`ts, associated_stations, wifi_rx_kbps, wifi_tx_kbps, lan_rx_kbps, lan_tx_kbps`.

### 4.1. Dispositivos conectados con su IP (T2) — `router_devices.csv` (implementado)

- **Qué mide**: cada equipo asociado al AP, con su MAC, IP asignada por DHCP,
  hostname, señal y tráfico.
- **Por qué**: el §3.1 del marco define el monitoreo de tráfico como *inventariar
  activos*. Un conteo no inventaria; una tabla por dispositivo sí. Es además lo que
  el dashboard de Esc1 muestra al público.
- **Cómo funciona**: `collect_router.py` combina, en el mismo ciclo SSH,
  `iw dev <iface> station dump` (MAC + señal + bytes) con `cat /tmp/dhcp.leases`
  (MAC → IP + hostname); cruza por MAC y calcula kbps por equipo vía delta.
- **Esquema CSV**:

  ```csv
  ts,mac,ip,hostname,signal_dbm,connected_s,rx_kbps,tx_kbps
  1779281860.5,a4:cf:12:..,192.168.1.134,android-pato,-58,212,7.5,508.5
  ```

### 4.2. Recursos del router (T3) — `router_resources.csv` (implementado)

- **Qué mide**: CPU y RAM del propio router, periódicamente. **Sin disco** — el
  router casi no escribe a almacenamiento; el dato no aporta al análisis.
- **Por qué**: el router es hardware de borde igual que el Pi (§6.2). Si se satura
  bajo el tráfico del público, hay que saberlo.
- **Cómo funciona**: `collect_router.py` lee `/proc/stat` (CPU% por delta de jiffies)
  y `/proc/meminfo` (RAM) en el mismo ciclo SSH — sin depender del `top` de busybox.
- **Esquema CSV**:

  ```csv
  ts,cpu_pct,mem_used_mb,mem_total_mb
  1779281860.5,18.4,52.1,128.0
  ```

### 4.3. Otro dato del router pertinente a Esc1 (T3b) — **Implementado (2026-05-24)**

Esc1 analiza DNS y construye el mapa de red. Métricas alineadas con su §3.1, ya
exportadas a CSV:

- **Consultas DNS de uso activo + dominio más visitado** → `dns_queries.csv`. Un
  nodo función cuelga de la salida 0 del "Filtro DNS" y registra solo los eventos
  de uso ACTIVO de un servicio (`score_detectado >= 100`, descartando el tráfico
  de fondo/CDN con score ~20), cruzando la IP con `esc1_last_devices` para añadir
  alias y fabricante (las mismas columnas de la tabla del dashboard). Escribe a
  `/data/metrics_out/dns_queries.csv` (append, vía nodo `file`). Columnas:
  `ts, ip, alias, fabricante, servicio, dominio, score`. De aquí salen el **dominio
  más visitado por los usuarios** (`group by servicio`/`dominio`) y la **tendencia**
  temporal de consultas. Patch reproducible:
  [add_esc1_dns_csv.py](flows_patch/add_esc1_dns_csv.py) (marcador `__DNSCSV__`).
  > Nota: la cabecera se escribe una vez por proceso de Node-RED; al reiniciar el
  > contenedor reaparece una fila de cabecera intermedia (inocua, el análisis la
  > descarta filtrando `ts == 'ts'`).
- **Leases DHCP activas** → columna `dhcp_leases` en `router.csv`
  ([collect_router.py](collectors/collect_router.py), `_count_active_leases`): número de
  equipos que el router considera "vivos" (expiry==0 estática, o expiry>now),
  complementa el conteo de estaciones WiFi. No toca el Pi.

`session.sh end` jala `dns_queries.csv` del `metrics_out` del Pi por scp y lo lista
en `status`.

---

## 5. Métricas del Pi por escenario aislado (T5)

`resources.csv` mide **CPU, memoria y red** (no disco — ver §3.4). Lo que falta no es
una columna más, sino el **protocolo de medición aislada**.

El tutor quiere el consumo del Pi **con un solo escenario desplegado**, bajando lo
que no se usa. Esto ya es la práctica (el Pi no corre los tres a la vez por RAM),
pero hay que formalizarlo como protocolo de medición:

1. Antes de medir un escenario, `docker compose down` de los otros dos.
2. Confirmar con `docker ps` que solo corren los contenedores de ese escenario.
3. `session.sh start escN` → medir → `session.sh end`.

Así el consumo registrado es atribuible a ese escenario, sin ruido de los demás.

---

## 6. Gráficas (T6)

Convención fija para todas: **eje X = tiempo, eje Y = consumo de recursos**.

- **Por escenario**: dos gráficas de líneas (CPU y RAM contra el tiempo) —
  `recursos_pi_*.png` desde `resources.csv` y `recursos_router_*.png` desde
  `router_resources.csv` cuando existe. Permiten ver picos y asociarlos a momentos
  de la demo. Misma convención para Pi y router.
- **General (consolidada)**: comparar los tres escenarios — CPU promedio/pico y RAM
  máxima en una sola figura o tabla.

**Implementado** en `plot_scenario.py`:

```bash
python3 plot_scenario.py sessions/2026-05-22_esc1            # CPU/RAM vs tiempo
python3 plot_scenario.py --general sessions/2026-05-22_esc1 \
    sessions/2026-05-22_esc2 sessions/2026-05-22_esc3 --out-dir sessions/
```

El modo `--general` produce `consolidado_general.csv` (CPU prom/pico, RAM máx,
duración por escenario) y `consolidado_general.png` — la **métrica general** (T1).
`plot_presentation.py` sigue cubriendo el modo presentación de jornada.

---

## 7. Los dos modos de sesión — cuándo usar cada uno

Existen dos formas de medir y se confunden con facilidad. El 20-may se usó el
equivocado y no se capturó nada de dominio (hallazgo 4).

| | `session.sh` (por escenario) | `presentation.sh` (continuo) |
|---|---|---|
| Propósito | Medir un escenario a fondo | Monitor de toda la jornada |
| Captura recursos | Sí (`resources.csv`) | Sí (`resources.csv`) |
| Captura router | Sí (`router.csv`) | No |
| Latencia backend | Sí | No |
| **Tablas de dominio** (auditoría, emails, atacantes) | **Sí** (`/api/export_state` al cerrar) | **No** |
| Self-check de reloj del Pi | Sí (aborta si > 2 s; ya no hay desfase Pi↔laptop) | No |

**Regla**: para obtener datos analizables (auditoría de Esc1, correos de Esc2,
atacantes de Esc3) hay que usar **`session.sh`**. El modo presentación solo sirve
para vigilar recursos durante una jornada completa.

---

## 8. Tabla resumen de auditoría

| Métrica | Archivo | Estado | Acción |
|---|---|---|---|
| Satisfacción (SUS + pedagógicas) | `survey.csv` | OK | Mantener |
| Latencia backend | `backend_latency.csv` | OK | Mantener |
| Atacantes + RPS (Esc3) | `esc3_stats_snapshot.csv` | OK | Mantener |
| Disponibilidad real target (Esc3) | `target_health.csv` | OK | Mantener |
| Tablas de dominio Esc2 (correos/clicks) | `email_*.csv` | OK | Mantener |
| Consumo Pi (CPU/RAM/red) | `resources.csv` | OK | Aislar por escenario (T5) |
| Concurrencia real (teléfonos) | `router.csv` + `router_devices.csv` | OK | Implementado (T2) |
| Recursos del router (CPU/RAM) | `router_resources.csv` | OK | Implementado (T3) |
| Montaje físico | `events.csv` | Manual | Cronómetro del operador |
| Tiempo de despliegue | `deploy.csv` | OK | `measure_deploy.py` / `session.sh deploy` |
| Eventos contenedor | `docker_events.csv` | OK | Mantener |
| Métrica general consolidada | `consolidado_general.csv` | OK | `plot_scenario.py --general` (T1) |
| Carga sintética (knee) | `loadtest.csv` | Lab/opcional | Fuera de Resultados |
| Tabla de películas Esc2 | — | Falta | Pendiente (añadir a export_state) |
| Datos DNS del router (Esc1) | `dns_queries.csv` + `dhcp_leases` en `router.csv` | OK | Implementado (T3b, §4.3) |

---

## 9. Hallazgos y correcciones pendientes

1. **`deploy_seconds` erróneo (§4.4) — RESUELTO** — `presentation_watcher.py` lo
   calculaba contra el `StartedAt` del contenedor; si el contenedor ya estaba arriba
   daba valores absurdos (925 s, 1783 s el 20-may). **Solución implementada**:
   `collectors/measure_deploy.py` (`session.sh deploy`) levanta el escenario en frío y
   cronometra hasta el primer HTTP 200 → `deploy.csv` (ver §3.5b). El montaje físico
   va por cronómetro manual del operador. Queda **no** usar el `deploy_seconds` del
   watcher para esta métrica.
2. **`README.md` desactualizado — RESUELTO** — referenciaba archivos que ya no
   existen (`esc1_latency_nodes.json`, `pull_pi_csv.sh`, `api_survey.md`) y omitía
   `target_health`, `docker_events`, `export_state`, `deploy` y el modo presentación.
   **Hecho**: reescrito como guía de uso alineada con este documento.
3. **`loadgen` y el endpoint de Esc2 — RESUELTO (como aclaración, no cambio de
   endpoint)** — apuntar a `POST /api/reserve` dispararía el envío SMTP y su delay de
   10 s, mandando correos reales y midiendo el delay artificial. Por eso se mantiene
   el GET a la raíz. **Hecho**: corregidos los comentarios engañosos de los YAML.
4. **Modo equivocado de sesión** — usar `presentation.sh` cuando se necesitaban datos
   de dominio (causa de la pérdida del 20-may). **Acción**: §7 de este documento lo
   deja por escrito; reforzar en el runbook.
5. **Criterio del "knee" disperso — RESUELTO** — vivía solo en el notebook. **Hecho**:
   `loadgen.py` marca el knee en `loadtest.csv`. *Nota:* `loadgen` quedó como prueba de
   **laboratorio opcional, fuera del alcance de Resultados** (ver §3.3b).
6. **Esc3: "caído" visual desacoplado de la salud real — MEJORADO (2026-05-24)** — el
   estado rojo/caído lo acciona el contador de presiones (motor de fases). Antes el banner
   quedaba **pegado en CAÍDO** (el `pressCount` nunca decaía y la protección no estaba
   ligada a la recuperación) y el target **no se caía de verdad** (backlog por defecto de
   128 → recuperación de minutos). **Correcciones implementadas**:
   - `esc3-fn-phase` (marcador `__RECOVERY__`, en `flows_patch/add_phase_engine.py`):
     bajo protección el banner sigue la **salud real** (`flow.lastProbeRt`) y vuelve a
     ONLINE/PROTEGIDO cuando el target responde; sin protección, `pressCount` decae.
   - `target/app.py` (en el Pi): `/reservar` con `sleep(0.2)` + `request_queue_size=12`
     (backlog acotado) → el target se cae de verdad bajo flood y **se recupera en ~3 s**
     al activar el rate-limit del proxy. `attacker/attacker.py`: `/start` resetea el
     `target_url` al directo (ciclo repetible).
   - Verificado: `target_health.csv` muestra `idle`(200) → `ataque`(timeout) →
     `protegido`(200 estable). **Decisión vigente**: para Resultados se reporta
     `target_health.csv` (salud real) + RPS; el flood real lo dispara el **operador**.

Estado de las acciones del tutor: **T2, T3, T3b, T6, T7 implementados** (ver §§4–7).
Pendiente: **T5** (protocolo de medición aislada — es metodología, ya documentada
en §5).
*(T4 — disco — descartado: sin valor analítico.)*

---

## 10. Encuesta (§4.1) — instrumento global con sustento académico

La encuesta es **un solo instrumento para todo el prototipo** (T9), no por escenario.
Se entrega una vez, en la pestaña final de Esc3 (`scope: prototipo-completo` en
`survey_template.json`). Los QR de encuesta de Esc1/Esc2 quedan ocultos. La audiencia
objetivo son estudiantes de **bachillerato y primeros semestres**, así que los ítems
están escritos en lenguaje natural, sin jerga técnica.

Cada ítem tiene respaldo académico (T10):

| ID | Pregunta (resumen) | Tipo | Sustento académico |
|---|---|---|---|
| sus1 | Los tres escenarios fueron fáciles de seguir | Likert 1–5 | SUS [25] + Lewis & Sauro 2017 |
| sus2 | Necesité ayuda para entender qué hacer *(invertido)* | Likert 1–5 | SUS [25] |
| sus3 | Los escenarios estuvieron bien integrados | Likert 1–5 | SUS [25] |
| sus4 | Aprendí rápido qué pasaba | Likert 1–5 | SUS [25] + heurística "visibilidad del estado" [26] |
| sus5 | Me sentí cómodo participando con mi teléfono | Likert 1–5 | SUS [25] + usabilidad móvil [26] |
| sus6 | Tendría que aprender mucho para usar algo así *(invertido)* | Likert 1–5 | SUS [25] |
| ped1 | Comprendí los conceptos de ciberseguridad | Likert 1–5 | Métrica pedagógica (§4.1) — comprensión percibida |
| ped2 | Recomendaría estudiar TI en la EPN | Likert 1–5 | Intención de recomendar — proxy **NPS** pedagógico (§4.1) |
| mejoras | ¿Qué mejorarías? | Texto | Retroalimentación cualitativa abierta |
| libre | Comentario libre | Texto | Retroalimentación cualitativa abierta |

**Fundamento del SUS reducido**: el System Usability Scale original de Brooke [25]
tiene 10 ítems. La literatura posterior (Lewis & Sauro, 2017) muestra que versiones
cortas conservan la correlación con el SUS-10 cuando se requiere brevedad — exactamente
el caso de una feria donde el público responde en menos de un minuto. Por eso se usan
6 ítems (sus1–sus6), dos de ellos invertidos (sus2, sus6) para controlar el sesgo de
aquiescencia. El diseño de la interfaz que la encuesta evalúa se apoya en las
heurísticas de Nielsen [26] (§2.3).

**Scoring** (de `survey_template.json` → `_meta.scoring`):

- **SUS reducido**: `SUS = (Σ (5 − x_i) para invertidos, o (x_i − 1) para directos) /
  (4 × n_items)) × 100`, con `x_i ∈ {1..5}`. Resultado en escala 0–100.
- **NPS pedagógico (ped2)**: promotores = `ped2 ≥ 4`, detractores = `ped2 ≤ 2`,
  `NPS = %promotores − %detractores` (escala 1–5 adaptada).

**Salida**: cada respuesta es una fila en `survey.csv`
(`ts, scenario, respondent_uuid, libre, mejoras, ped1, ped2, sus1..sus6`). Editar
`survey_template.json` cambia las preguntas sin tocar código — el formulario HTML se
renderiza desde la plantilla.

**Veredicto**: **mantener**. El instrumento es global, breve, con base académica y
editable por el tutor. Confirmar solo que la redacción de cada ítem siga libre de
jerga para el público de bachillerato.

---

## 11. Observaciones de campo y decisiones por escenario (pendientes)

Issues detectados en pruebas reales, con la recomendación del tutor y la decisión
tomada. No son del harness de métricas, sino del comportamiento de los escenarios;
se documentan aquí porque condicionan qué y cómo se puede medir.

### 11.1. Esc1 — visualización de dominios DNS

- **Problema de campo**: al ver qué aplicaciones/dominios visitaban los usuarios, el
  retraso se volvió **evidente con más de 20 usuarios conectados** (con ~5 no se nota).
- **Bug de ranking**: **Facebook tiene un score desproporcionado y "siempre gana"**,
  aunque los usuarios no estén realmente en Facebook — la métrica/visual lo sobrepondera.
- **Recomendación del tutor**: dejar de mostrar el dominio en una **esquina** del
  dashboard y crear una **página aparte con una tabla que se actualice** conforme a los
  dominios que se van visitando.
- **Implementado (2026-05-24)** — parche `flows_patch/fix_esc1_ranking_table.py`, desplegado
  vía API Admin (`POST http://192.168.1.10:1881/flows`):
  - **Fix del ranking de Facebook**: el tráfico de **fondo/CDN** (fbcdn, fbsbx, graph.facebook,
    akamai, cloudfront, etc.) se clasifica como "Tráfico de fondo" con score bajo (20), así que
    ya **no** etiqueta al dispositivo como Facebook ni alimenta el conteo. Solo el uso ACTIVO
    (facebook.com/m.facebook.com, etc.) cuenta. *(Nota: los CDN de Instagram/WhatsApp/TikTok
    —cdninstagram, whatsapp.net, tiktokv— siguen contando como activos por estar más ligados al
    uso real de la app; revisable si se quiere afinar.)*
  - **Decaimiento**: la etiqueta de un dispositivo vuelve a "En espera de tráfico útil…" tras
    ~20 s sin tráfico activo (barrido cada 5 s sobre `esc1_active_map`; NO se usa `global.keys()`
    porque las claves con IP se anidan por la notación de puntos de Node-RED).
  - **Tabla de dominios (recomendación del tutor)**: nueva pestaña **"ESC1 Dominios"** con una
    tabla HTML (`ui_template`) que lista los servicios/dominios más consultados, refrescada cada 2 s.
- **Pendiente**: rendimiento del grafo D3 con >20 usuarios (throttle/render incremental) — **no
  abordado** en esta iteración por decisión (se priorizó la tabla nueva).

#### 11.1.1. Limitación conocida — DNS privado / DoH oculta el tráfico

Los teléfonos Android (y navegadores) con **DNS privado / DNS-over-HTTPS (DoH)** o apps tipo
**AdGuard** **no envían sus consultas DNS al router**: las cifran hacia un resolver externo
(`dns.google`, `cloudflare-dns.com`, AdGuard, etc.) por el puerto 443. Como Esc1 monitorea el
**syslog DNS del router (dnsmasq, puerto 5515)**, **el tráfico de esos equipos no aparece** en el
grafo ni en la tabla de dominios. Es una limitación inherente al método (monitoreo pasivo de DNS en
el router), no un bug. Para la demo: se observa el tráfico de los equipos que usan el DNS del router
(la mayoría por defecto); los que fuerzan DoH/AdGuard quedan como "En espera de tráfico útil…". Se
documenta como alcance metodológico del Esc1.

#### 11.1.2. Métricas internas de Esc1 — solo documentación, no se muestran al público

La pestaña **"ESC1 Metricas"** del dashboard **no se expone al público** (no está en la navegación
01–05 del diseño). Esas métricas son de instrumentación/diagnóstico, no de la demo, y se **documentan
aquí** (igual que el resto del harness `tesis_metrics`), sin mostrarlas en pantalla. Se acumulan en
`global.esc1_metrics` desde la función "Filtro DNS":

| Métrica | Significado |
|---|---|
| `dns_events_total` / `dns_events_validos` / `dns_events_descartados` | eventos DNS recibidos / parseados OK / descartados (ruido) |
| `dns_privado_detectado_total` | consultas a resolvers DoH/privados (señal de la limitación 11.1.1) |
| `no_autorizado_detectado_total` | dominios de categorías bloqueadas (adulto/piratería) |
| `dns_ipv6_total` / `_mapped` / `_unmapped` | eventos IPv6 y su correlación a IPv4 |
| `sim_tests_total` / `sim_tests_ok` | pruebas de clasificación (cuando se inyecta `expected_service`) |
| `ui_push_total` | refrescos enviados a la UI |

> Estado de la pestaña "ESC1 Metricas": se deja **oculta** del flujo de demo (reutilizable a futuro);
> su valor es documental, no de presentación.

#### 11.1.3. Clasificación de servicios, fabricante y guion para el público

La tabla "06_ Dominios visitados" muestra, **por dispositivo**, el alias registrado (o el hostname)
+ IP + **fabricante** + el **sitio que consulta ahora**. La dinámica de la demo es que el operador le
diga a cada participante qué está visitando su teléfono.

**Clasificación (función "Filtro DNS"):** se etiqueta el dominio al servicio de uso activo
(Facebook, Instagram, WhatsApp, TikTok, YouTube, **Telegram**, etc., score 110). El **tráfico de
fondo/infra** (CDN, push, analítica y SDKs de ads como **ByteDance/Pangle** `ibytedtos`,
`byteoversea`; Google `gstatic`/`googleapis`/`1e100`; Meta `fbcdn`/`fbsbx`) se marca como
**"Tráfico de fondo"** (score bajo) y **no** etiqueta al dispositivo. La etiqueta **decae** a
"En espera…" tras ~20 s sin tráfico activo.

**Fabricante:** se infiere del **hostname** (Samsung/Honor/Huawei/Xiaomi-Redmi/Apple/Motorola/…),
porque Android/iOS **aleatorizan el MAC** y el OUI suele dar "Desconocido".

**Limitaciones honestas (qué explicar al público):**
- Los teléfonos **hablan con muchos servicios en segundo plano** (notificaciones, publicidad,
  analítica) aunque no estés usando esa app — por eso a veces aparecía "siempre TikTok/Facebook"
  estando el equipo inactivo. **Eso mismo es la lección de privacidad**: tus apps envían datos sin
  que lo notes. Al navegar activamente, el sitio dominante refleja lo que haces.
- El DNS ve **infraestructura compartida**: Instagram/WhatsApp usan servidores de Meta/Google, así
  que puede haber ambigüedad puntual. Se mitiga mandando esa infra a "fondo", pero no es perfecto.
- Equipos con **DNS privado/DoH/AdGuard** no aparecen (ver §11.1.1).
- Mensaje sugerido al público: *"El sistema ve la huella de red de tu teléfono. Aunque no estés en
  una app, tu celular ya está hablando con sus servidores. Cuando navegas, vemos a dónde."*
- **Relación con la métrica DNS (T3b)**: **resuelto** — el mismo flujo que alimenta la tabla
  registra ahora las consultas de uso activo a `dns_queries.csv` (`ts, ip, alias, fabricante,
  servicio, dominio, score`), cerrando el T3b. De ese CSV salen el **dominio más visitado** y
  la tendencia temporal. Ver §4.3 y [add_esc1_dns_csv.py](flows_patch/add_esc1_dns_csv.py).

### 11.2. Esc3 — control del ataque y realismo de la caída

- **Decisión tomada**: el **operador dispara el flood real** con el botón; los teléfonos
  del público son la **ilusión visual** (creen que tumban el servidor). La caída y las
  métricas reales (`target_health.csv` + RPS) se generan cuando el operador ataca.
- **Por qué (recomendación honesta)**: el target es un Flask de **un solo hilo con ruta
  bloqueante** (`/reservar`, `sleep(0.2)` → capacidad ~5 req/s, `threaded=False`) y con
  **backlog de escucha acotado (`request_queue_size=12`)**. Tumbarlo requiere
  **concurrencia sostenida**, que aporta el flood `asyncio` del `esc3-attacker`
  (`WORKERS=30`) que dispara el operador. Los **toques del público son esporádicos**, no
  sostenidos, así que **no tumbarían el servidor de forma confiable**. La caída controlada
  por el operador es reproducible y medible.
- **Realismo afinado (2026-05-24)**: el backlog acotado hace que el target se caiga de
  verdad bajo flood (probe en timeout) **y** se recupere en ~3 s al activar la protección
  (rate-limit del proxy a 1 r/s, por debajo de la capacidad). Sin acotar el backlog, la
  cola por defecto (128) tardaba minutos en drenar y la recuperación no se apreciaba.
  Ver §9, hallazgo 6.
- **Encuadre para la tesis**: se presenta como una **carga controlada que demuestra el
  agotamiento de hilos** (§3.4), no como un ataque real de la audiencia. El "caído" visual
  por contador de presiones es animación, no dato (ver §9, hallazgo 6).
- **Opción futura (no recomendada ahora)**: que cada toque del teléfono envíe 1 petición
  real al target para que el público contribuya algo. Añade complejidad y **no mejora la
  confiabilidad** de la caída, que seguiría dependiendo del flood del operador.

---

## Referencias del marco teórico citadas

| # | Referencia | § |
|---|---|---|
| [11] | Lyon, *Nmap Network Scanning*, 2009 | 3.1, 5.2.1 |
| [25] | Brooke, *SUS — A Quick and Dirty Usability Scale*, 1996 | 4.1 |
| [26] | Nielsen, *Usability Engineering*, 1993 — heurísticas | 2.3 |
| — | Lewis & Sauro, 2017 — validación del SUS reducido | 4.1 |
