# README — Trabajo del martes 2026-05-19 (handoff al chat nuevo)

> **Para el asistente nuevo:** este archivo es el handoff de la sesión del 2026-05-18 (ensayo en casa con 3 dispositivos). El [README_MAÑANA.md](README_MAÑANA.md) original es el plan que se ejecutó hoy y queda como histórico. Este README es lo que hay que hacer **martes** (con todo el día) y **miércoles temprano** antes de salir al CEC. La demo pública es el **miércoles 2026-05-20**, así que hay ~36 horas de runway — no hay que correr.

---

## ✅ ACTUALIZACIÓN 2026-05-19 (noche) — problemas resueltos en esta sesión

Todo lo siguiente quedó **resuelto, desplegado al Pi y validado en vivo**. Los cambios de `flows.json` se hicieron con **parches idempotentes** en [flows_patch/](flows_patch/) (con backup), aplicados a la copia local y a la del Pi.

| Bug | Estado | Qué se hizo |
|---|---|---|
| **A.2 — DNS "sitios visitados" Esc1** | ✅ RESUELTO | Causa raíz: dnsmasq del router tenía `log-facility=/tmp/dnsmasq.log` en `/etc/dnsmasq.conf` → escribía las queries a un archivo (inexistente bajo ujail), no a syslog, y logd nunca las reenviaba. Fix: comentar esa línea + `dnsmasq restart`. Validado con tcpdump + probe temporal: `query[...]` llega al Pi y `Filtro DNS` la parsea. Persiste a reinicios (backup en el router). El transporte y el código de Node-RED siempre estuvieron bien. |
| **A.3 — Botón móvil Esc3 no atacaba** | ✅ RESUELTO (rediseñado a fases) | Ahora hay un **motor de fases** por cantidad de presses con permanencia mínima de 8 s: 🟢 verde 0–7, 🟡 amarillo 8–14, 🔴 rojo ≥15. El flood REAL se dispara al entrar en rojo (target colapsa de verdad, validado HTTP 000) y se detiene al recuperarse. El probe externo sigue midiendo el colapso real. Parche `add_phase_engine.py`. Umbrales/tiempos configurables (`TH_SLOW=8`, `TH_DOWN=15`, `DWELL_MS=8000`). |
| **Banner/celulares no se ponían en "CAÍDO"** | ✅ RESUELTO | Antes decía "DEGRADADO" (amarillo) y nunca rojo. Banner del operador full red "🔴 SISTEMA CAÍDO POR ATAQUE DOS" + amarillo propio (`b-slow`), desacoplado de `st.running`. Página móvil: fondo **rojo completo** (`body.body-down`) al caer. |
| **Esc1 — imágenes y nombres de Pi/PC** | ✅ RESUELTO | Imágenes por IP con prioridad sobre nmap: `192.168.1.10`→raspberry.png, `192.168.1.20`→laptop.png (`fix_esc1_device_images.py`). Nombres estaban **invertidos** (MY_PC_IP etiquetado como Raspberry): corregido a `.10`→"Raspberry Pi (Servidor)", `.20`→"PC Admin (Laptop)" (`fix_esc1_device_names.py`). WhatsApp: verificado que **sí se clasifica** (no era bug de regex; depende de cuántas queries DNS genere el teléfono y de IPv6). |

### 🆕 Métricas que pidió el tutor (CPU/memoria continuo + bitácora + tiempo de montaje)

Se creó un orquestador **independiente** de `session.sh` para capturar **toda la presentación de corrido** (no por-escenario), con marcas de inicio de cada prototipo y medición de tiempo de montaje:

- **[presentation.sh](presentation.sh)** — comandos:
  - `./presentation.sh start` — arranca el monitor continuo (CPU/mem/red del Pi + contenedores, 1/s) y crea `bitacora.csv`.
  - `./presentation.sh deploy <esc1|esc2|esc3>` — baja los demás, sube ese escenario, **mide el tiempo de montaje** (deploy → HTTP 200) y registra la **hora exacta de inicio** del prototipo en la bitácora.
  - `./presentation.sh mark "texto"` — marca manual (úsala si cambias de escenario por la ops-console en vez de `deploy`).
  - `./presentation.sh teardown <escN>` — mide tiempo de desmontaje.
  - `./presentation.sh end` — detiene y baja `resources.csv`.
  - `./presentation.sh plot` — genera la gráfica.
- **[plot_presentation.py](plot_presentation.py)** — gráfica `presentacion_recursos.png`: CPU% y memoria del Pi en el tiempo (hora local), con **bandas de color por escenario**, líneas de inicio y el **tiempo de montaje anotado**. Imprime además la tabla de tiempos de montaje.

**Flujo sugerido para mañana:** `start` al inicio → `deploy esc1` (o `mark` si usas ops-console) → demo Esc1 → `deploy esc2` → demo → `deploy esc3` → demo → `end` → `plot`. La gráfica resultante responde directamente lo del tutor: consumo continuo + a qué escenario corresponde cada tramo + cuánto tardó en montar cada uno. Esto cubre el **B.1** del plan (tiempo de montaje §4.4).

> Probado end-to-end esta noche (start → deploy esc1 (montaje 1 s, ya estaba arriba) → mark → end → plot OK). El clock-check Pi↔laptop dio |offset| 184 ms.

### 🔁 RUNBOOK de mañana — métricas (levantando por la ops-console)

**1. Preflight (5 min):**
- Adaptador USB-LAN conectado; `ping 192.168.1.10` y `ping 192.168.1.1` responden.
- `chronyc tracking` en la laptop (drift < 1 s). `presentation.sh start` aborta si el offset Pi↔laptop > 2 s.
- En la laptop solo debe correr la ops-console: `docker ps` → solo `tesis-ops-console`.

**2. Arrancar el monitor (una sola vez, al inicio):**
```bash
cd ~/tesis/metrics
./presentation.sh start
```
Arranca el colector continuo de CPU/mem en el Pi (1/s) **y el watcher**, que detecta solo cuándo queda listo cada escenario y registra hora de inicio + tiempo de montaje — **aunque levantes por la ops-console** (no tocas terminal durante la demo).

**3. Por cada escenario:** levanta con la ops-console (`http://localhost:1890/ui` → botón **"INICIAR DEMO ESCN"**) y haz la demo. El watcher anota `scenario_ready` + montaje automáticamente.
- _Opcional, solo Esc3:_ si quieres la disponibilidad del DoS en CSV: `python3 laptop/target_health_probe.py --output-dir sessions/presentacion_<fecha> --target-url http://192.168.1.10:5000/ --orchestrator-url http://192.168.1.10:1883 &`
- Si cambias algo a mano: `./presentation.sh mark "texto"`.

**4. Al terminar:**
```bash
./presentation.sh end       # detiene el monitor y baja resources.csv
./presentation.sh report    # genera informe_ejecutivo.pdf
```
Sale `sessions/presentacion_<fecha>/informe_ejecutivo.pdf`: tabla de **tiempos de montaje**, **gráfica CPU/mem** con bandas por escenario, **bitácora** de horas de inicio e interpretación. (El layout del PDF tiene una página algo vacía — cosmético, se pule luego.)

**Las demás métricas del marco teórico:** las CSV de cada escenario (`backend_latency`, `survey`, embudo de phishing, stats Esc3) las escribe el *middleware* del escenario en su `metrics_out` mientras corre; se acumulan solas. El análisis fino (latencia, CTR, SUS, disponibilidad DoS) se hace **después** con `analyze.ipynb` → PDF por escenario. **No botes esos CSV.**

### Pendiente / notas
- **Validación visual en navegador** de Esc1 (`http://192.168.1.10:1881/ui`): confirmar que el Pi muestra 🍓 + "Raspberry Pi (Servidor)" y la PC 💻 + "PC Admin (Laptop)" una vez que nmap los detecte.
- **A.4 (encuestas en reportes Esc1/Esc2)** y polish C.x: sin tocar todavía.
- El adaptador USB-LAN se cayó una vez durante esta sesión (carrier=1 sin ruta) y se recuperó con re-plug físico (ver §0).
- El Pi quedó corriendo **Esc1**.

---

## 0. Advertencias críticas — LEER PRIMERO

- **Revocar el PAT clásico** `ghp_bLCG...sar7s` en https://github.com/settings/tokens. Sigue pendiente desde la sesión del 2026-05-17. 30 segundos de trabajo.
- **NO levantar copias locales de los escenarios en la laptop** durante el trabajo del martes. Hoy estaban corriendo `esc1-nodered`, `jp-esc2-nodered`, `esc3-nodered` en la laptop (puertos 1881/1882/1883) y eso causó al menos un bug serio (Esc2 BASE_URL apuntando al laptop). Solo `tesis-ops-console` (1890) debe estar arriba en la laptop.
- **SSH key ed25519** está instalada para `raspberry1@192.168.1.10` — ya no se necesita password. Si pides password, algo está mal.
- **chrony**: la laptop sirve NTP al Pi. `session.sh start` aborta si offset > 2 s. Si chrony falla, `sudo systemctl restart chrony` en ambos.
- **Adaptador USB-LAN** (`enx000a4300a7b1`) tiene tendencia a tumbar el enlace sin perder carrier. Si Pi y router fallan ping al mismo tiempo y `cat /sys/class/net/enx000a4300a7b1/carrier` muestra `1`, re-conectar físicamente el adaptador.
- **Regla CLAUDE.md** sigue: un escenario a la vez en el Pi 3B+ (~900 MB RAM útiles). El switch entre escenarios lo hace la ops-console (botón "INICIAR DEMO ESC<N>") o `docker compose down/up` por SSH.

---

## 1. Estado al cierre del lunes 2026-05-18

**Pipeline de métricas: completo y validado end-to-end.**

| Pieza | Ubicación | Estado |
|---|---|---|
| SSH key + chrony Pi↔laptop | `~/.ssh/id_ed25519`, `/etc/chrony/chrony.conf` | ✅ operativo |
| `session.sh` con clock guard + colectores | [session.sh](session.sh) | ✅ |
| `target_health_probe.py` (Esc3, 1 Hz, tagging fase) | [laptop/target_health_probe.py](laptop/target_health_probe.py) | ✅ |
| `docker_events_collector.py` | [laptop/docker_events_collector.py](laptop/docker_events_collector.py) | ✅ |
| `/api/export_state` en los 3 Node-RED | parche idempotente en [flows_patch/add_export_state.py](flows_patch/add_export_state.py); deployado en Pi | ✅ |
| `fetch_export_state.py` (jala tablas → CSV) | [laptop/fetch_export_state.py](laptop/fetch_export_state.py) | ✅ |
| Notebook con 8 celdas nuevas (target_health, funnel, adopción, eventos, stats, glosario) | [analyze.ipynb](analyze.ipynb), honra `SESSION_DIR_OVERRIDE` env var | ✅ |
| Pipeline pandoc + eisvogel | [make_pdf.sh](make_pdf.sh), [templates/eisvogel.latex](templates/eisvogel.latex) | ✅ |
| Ops-console Node-RED en laptop | [ops-console/](ops-console/) en `http://localhost:1890/ui` | ✅ funcional (mejoras pendientes — ver §3.C) |
| Encuesta única en Esc3 (10 ítems prototipo en conjunto) | [survey/survey_template.json](survey/survey_template.json) | ✅ |

**Ensayo end-to-end con 3 dispositivos reales (Pato, Pame, Jean Poll):**
- 3 sesiones completas (`sessions/esc1_2026-05-18_2059`, `esc2_2026-05-18_2109`, `esc3_2026-05-18_2122`)
- Datos cuantitativos coherentes (ver §2)
- 3 PDFs generados con eisvogel (~300-400 KB cada uno)

---

## 2. Lo que validó el ensayo (números duros para defender la tesis)

| Escenario | Duración | Datos clave | Hallazgo cuantitativo |
|---|---|---|---|
| **Esc1** (red) | 9 min, 5 disp. | resources 554, latency 4417, audit 3 | CPU host avg 7%, max 16% — Pi 3B+ va sobrado |
| **Esc2** (phishing) | 13 min, 3 emails | capturas 3, clicks 2, latency 10 req | **CTR pedagógico = 67%** (2/3 abrieron el enlace educativo) |
| **Esc3** (DoS) | 13 min, 3 atacantes mobile + flood operador | target_health 702 muestras, snapshots 160, survey 4 | **Disponibilidad: 98.5% (idle) → 0% (ATAQUE) → 58% (PROTEGIDO)**. Mann-Whitney `idle vs ataque` p = 2.86×10⁻³¹, `ataque vs protegido` p = 4.77×10⁻⁵. Statistical significance overwhelming. |

**El hallazgo más fuerte para el capítulo de Resultados de la tesis**: el `target_health_probe.py` (probe externo, independiente del dashboard que Esc3 muestra al operador) prueba que el target Flask cae a **0% disponibilidad** durante el ataque del operador (50 segundos seguidos sin un solo 200 OK). La protección con nginx rate-limit lo recupera al 58%. Esto es lo que el dashboard del operador NO mostraba (decía "degradado" en lugar de "caído"), justificando la necesidad de un probe externo.

---

## 3. Bugs encontrados, en orden de prioridad

### A — Críticos para que la demo se vea bien (tres en total)

#### A.1 — `BASE_URL` del Pi apuntaba al laptop (ya arreglado, verificar mañana)

**Síntoma original**: Esc2 generaba el QR con `http://192.168.1.20:1882` (laptop), no `192.168.1.10:1882` (Pi). Los emails de los alumnos hubieran sido procesados por el escenario que corre en la laptop, los dashboards del Pi en cero, las métricas vacías.

**Fix aplicado en el ensayo**: `sed -i "s|^BASE_URL=.*|BASE_URL=http://192.168.1.10:1882|" ~/tesis_escenario2/.env` en el Pi, restart de Esc2.

**Verificación pre-clase del miércoles**:
```bash
ssh raspberry1@192.168.1.10 'grep BASE_URL ~/tesis_escenario2/.env'
# Esperado: BASE_URL=http://192.168.1.10:1882
```

Adicionalmente verificar que **NADA del set local** esté corriendo en la laptop:
```bash
docker ps --format "{{.Names}}" | grep -vE "^(tesis-ops-console|buildx)" 
# Esperado: salida vacía
```

#### A.2 — DNS "sitios visitados" en Esc1 no se ve (TU PRIORIDAD #1)

**Síntoma**: el panel "Sitio:" en el dashboard de Esc1 dice "En espera de tráfico…" para todos los dispositivos, incluso cuando los teléfonos están activos en TikTok / WhatsApp.

**Lo verificado en el ensayo**:
- Router UCI tiene la config correcta: `dhcp.@dnsmasq[0].logqueries='1'`, `system.log_ip='192.168.1.10'`, `system.log_port='5515'`, `system.log_proto='udp'`, `system.log_remote='1'`.
- Pi escucha en UDP 5515: `ss -lunp` muestra `node-red pid=2903 fd=18` ligado a `0.0.0.0:5515`.
- No hay firewall bloqueando en el Pi: `iptables -L INPUT -n` con default ACCEPT, no hay UFW.
- Pero **0 mensajes llegan al Pi**, incluso `logger -t test "X"` ejecutado **desde el router** tampoco aparece. Y la query forzada `nslookup test.example.com @192.168.1.1` desde la laptop tampoco genera log.

**Hipótesis a probar (orden de menor a mayor esfuerzo):**

> 1. **Hipótesis del usuario (probable y rápida)**: las copias LOCALES del Esc1 que estuvieron corriendo todo el día en la laptop (uid `esc1-nodered`, puerto 1881) podían tener bound `0.0.0.0:5515` también — y como el router envía UDP a `192.168.1.10`, ese paquete podía rebotar por ARP cache antiguo o conflicto IPv4 si la laptop alguna vez se identificó con esa IP. **Acción**: confirmar con `docker ps` en la laptop que nada local está arriba, hacer `arp -d 192.168.1.10` en el router, restart router, repetir test.
>
> 2. **Hipótesis del usuario (segunda)**: el flows.json de Esc1 puede tener el nodo `udp in` mal configurado, o la función `Filtro DNS` no parsea el formato exacto que envía dnsmasq de este OpenWrt. **Acción**: inspeccionar el nodo `udp in` (id `Receptor DNS`) en `tesis_escenario1/flows.json` — puerto y interfaz; y en la función `Filtro DNS` agregar un `node.warn(msg.payload)` al inicio para imprimir CUALQUIER cosa que llegue, sin filtrar.
>
> 3. **Hipótesis técnica más profunda**: el syslog daemon de OpenWrt (busybox `logd`) no está reenviando dnsmasq al syslog remoto. Aunque `log_remote=1` está, dnsmasq puede estar logueando a un facility que `logd` no reenvía. **Acción**: setear `option facility 'daemon'` en `/etc/config/system` y `option log-facility='/dev/log'` (o `DAEMON.INFO`) en dnsmasq. Verificar con tcpdump.
>
> 4. **Hipótesis "DoH/DoT"**: Android moderno (Samsung S20/S25 confirmados en el ensayo) usan DNS-over-HTTPS por defecto, bypassan al router. **Verificación**: usar un dispositivo configurado con DNS explícito del router (forzar `192.168.1.1` en config WiFi del teléfono, deshabilitar "DNS privado" en Android). Si con eso aparece — es DoH. Si sigue sin aparecer — es problema #1/2/3.

**Setup del debug** (martes temprano):
```bash
# Instalar tcpdump en el Pi (no está)
ssh raspberry1@192.168.1.10 'sudo apt-get install -y tcpdump'

# Sesión 1 — tcpdump en el Pi (ver QUÉ llega al puerto 5515)
ssh raspberry1@192.168.1.10 'sudo tcpdump -ni eth0 -A udp port 5515'

# Sesión 2 — desde el router (forzar evento)
sshpass -p 'DTIC2025B_jp' ssh -o KexAlgorithms=+diffie-hellman-group14-sha1 \
    -o HostKeyAlgorithms=+ssh-rsa root@192.168.1.1 \
    'logger -t MANUAL_TEST "from router $(date)"'

# Si el tcpdump del Pi NO captura: problema del syslog daemon o ruta de red.
# Si SÍ captura pero Node-RED no lo recibe: problema del flows.json (nodo UDP o filtro).
```

#### A.3 — Botón móvil de Esc3 no dispara flood real

**Síntoma**: el botón "ATACAR" en `http://192.168.1.10:1883/` (página que cargan los teléfonos) solo incrementa `flow.pressCount` y un contador visual. **No** gatilla el `esc3-attacker` asyncio. El único botón que dispara flood real es el del dashboard del operador (`/ui` tab "01 - Ataque").

**Impacto si no se arregla**: con 20 alumnos presionando, verán contador subiendo pero el target Flask seguirá respondiendo 200 OK. Pedagógicamente quedaría como "demo simulada", no real.

**Mitigación si no hay tiempo (segura)**: el operador (tú) presiona el botón "ATACAR" del dashboard al mismo tiempo que los alumnos presionan en sus teléfonos. El público no se entera. Esto es lo que pasó en el ensayo y los datos cuantitativos quedan idénticos (`target_health` registra el colapso real).

**Fix correcto (martes)**: en `tesis_escenario3/flows.json`, encontrar el endpoint `http in` con URL `/api/attack/press` (id `metrics_*` no — es el endpoint genuino del attacker; busca por url). Cablear su salida al mismo function que arranca el ataque (función con `flow.set('attacking', true)` y el HTTP request al esc3-attacker). Estrategia:
- Cada `/api/attack/press` incrementa `pressCount`.
- Cuando `pressCount % 10 === 0`, hacer `POST esc3-attacker:5001/start` con concurrency proporcional (o simplemente arrancar el ataque al 5° press y dejarlo correr hasta `/api/attack/stop`).
- Mantener el contador visual igual; solo agregar el side-effect del attacker.

#### A.4 — Encuestas aparecen en reportes Esc1/Esc2 (no deberían)

**Síntoma**: el `survey.csv` se jala en `session.sh end` para los 3 escenarios. El notebook procesa la encuesta en todos los reportes, mostrando "1 respuesta" en Esc1/Esc2 (residuo de prueba) y "4 respuestas" en Esc3 (de las cuales 1 es residuo). **Debe**: solo Esc3 muestra encuestas, y el 4 vs 3 hay que limpiarlo.

**Fix (rápido, ~15 min)**:
1. En el notebook, celda de Tabla 5 (`SUS reducido`): envolver todo el bloque en `if SESSION_DIR.name.startswith('esc3_'): ...`.
2. Limpiar `survey.csv` en el Pi antes de cada sesión nueva de Esc3 (o filtrar por `ts > session_start_ts` al cargar). Para el miércoles, hacer `ssh raspberry1@192.168.1.10 'rm -f ~/tesis_escenario3/metrics_out/survey.csv'` antes de la sesión real de Esc3.
3. Re-generar los 3 PDFs del ensayo para verificar que Esc1/Esc2 ya no muestran encuesta.

---

### B — Importantes para el marco teórico (no bloquean la demo)

#### B.1 — Tiempo de montaje §4.4 — instrumentar `docker compose up/down`

**Justificación**: §4.4 del marco teórico habla explícitamente de "tiempo de montaje y plug-and-play". Hoy lo medimos con eventos manuales (`session.sh log demo_start`, etc.). Es laxo y olvidable.

**Diseño propuesto**: agregar `session.sh deploy <scenario>` y `session.sh teardown <scenario>` que:
1. Marcan `mount_start` en events.csv (epoch)
2. Ejecutan `ssh raspberry1@... 'cd ~/tesis_escenario<N> && docker compose up -d'`
3. Hacen polling HTTP a `http://192.168.1.10:188<N>/ui` hasta status 200 (o /admin para Esc3)
4. Marcan `mount_ready` (epoch) — diferencia con mount_start = **tiempo de montaje**
5. Para teardown análogo: `teardown_start` → `docker compose down` → `teardown_done`

Después agregar una celda al notebook con tabla:

| Escenario | mount_ready − mount_start (s) | teardown_done − teardown_start (s) |
|---|---|---|
| esc1 | ? | ? |
| esc2 | ? | ? |
| esc3 | ? | ? |

Esfuerzo: ~1 h código + 30 min validar con 3 vueltas.

---

### C — Polish (post-demo o si sobra tiempo el martes tarde)

#### C.1 — Ops-console accesible desde la LAN (192.168.1.20:1890)

Hoy escucha en `0.0.0.0:1890` pero UFW podría bloquear. Verificar:
```bash
sudo ufw allow from 192.168.1.0/24 to any port 1890 proto tcp comment "ops-console LAN"
```
Esfuerzo: 2 minutos.

#### C.2 — Botón "Generar reporte PDF" en ops-console

Tab "Reportes" en ops-console con botones:
- "Generar PDF Esc1" → `exec` corre `cd /metrics && SESSION_DIR_OVERRIDE=sessions/esc1_<latest> jupyter nbconvert --execute ... && ./make_pdf.sh <session>`
- Idem Esc2, Esc3
- Botón "Descargar último PDF" → http response con el PDF como attachment

Necesita: ops-console container tiene que tener pandoc + xelatex + jupyter + scipy + pandas. Hoy no los tiene. Opciones:
- Agregar al Dockerfile (build pesado)
- O hacer que el botón corra el comando ya en la laptop (host) vía SSH a localhost — más simple

Esfuerzo: 1.5 h.

#### C.3 — Estilo clean-tech unificado en ops-console

Dark theme (#0eb8c0 acentos cyan teal, fondo #111, tipografía sans-serif). Match con los 3 escenarios. Editar `data/settings.js` con tema `theme-dark` + `themeState` ajustado. El primer intento de Hoy falló por "circular dep" del ui_base — hay que usar el formato exacto de node-red-dashboard 3.6.x.

Esfuerzo: ~1 h con prueba/error.

---

## 4. Plan para el martes (24h, sin presión)

### Mañana (4 h)
1. **Verificación post-noche** (15 min): SSH al Pi, chrony, no hay procesos locales colgados, ops-console responde.
2. **Bug A.2 — DNS** (2-3 h): probar las 4 hipótesis en orden. El paso 1 (instalar tcpdump y observar) es la pieza clave. Documentar cuál ganó.
3. **Bug A.3 — Esc3 button** (1 h): modificar flows.json, hot-reload, probar con un solo dispositivo.

### Tarde (4 h)
4. **Bug A.4 — survey filter** (15 min).
5. **Re-correr ensayo completo** con los fixes (1 h físicos + setup).
6. **Bug B.1 — tiempo de montaje** (1.5 h).
7. **Re-generar los 3 PDFs limpios** y compartir contigo para revisión.

### Noche (2-3 h, opcional)
8. **Polish C.1, C.2** si quedan ganas.

### Miércoles temprano (1 h)
9. **Preflight de aula** según §6 del [RUNBOOK_MIERCOLES.md](RUNBOOK_MIERCOLES.md).
10. **Revocar PAT** (30 segundos, mencionar al asistente al iniciar).

---

## 5. Hipótesis pendientes y refs útiles

### Sobre el DNS (lo más caliente)
- Tu hipótesis #1 (conflicto con local copies) es la más probable y la primera a probar.
- Tu hipótesis #2 (flows.json mal configurado): el nodo UDP en flows.json se llama por id `Receptor DNS` (basado en log line `[udp in:Receptor DNS] udp listener at 0.0.0.0:5515`). Buscar ese nodo y verificar `port: 5515` y `multicast: false` y `binaryAsBuffer: true`.
- El comando rápido para inspeccionar: `python3 -c "import json; d=json.load(open('/home/jeanpoll/Escritorio/tesis_escenario1/flows.json')); [print(n) for n in d if n.get('name')=='Receptor DNS']"`

### Comandos útiles que ya están listos
- Iniciar sesión: `cd ~/tesis/metrics && ./session.sh start esc<N>`
- Terminar: `./session.sh end`
- Estado: `./session.sh status`
- Logear evento: `./session.sh log <event> "<notes>"`
- Switch escenario en Pi: usar ops-console o `ssh raspberry1@192.168.1.10 'cd ~/tesis_escenarioN && docker compose up -d'`
- Re-deployar flows.json al Pi: `scp ... raspberry1@192.168.1.10:/tmp/x && ssh raspberry1@... 'sudo mv /tmp/x ~/tesis_escenario<N>/flows.json && sudo chown root:root ~/tesis_escenario<N>/flows.json && docker restart <container>'`
- Hot-reload Esc3 (si está corriendo): `python3 -c "import json; d=json.load(open('flows.json')); json.dump({'flows':d}, open('/tmp/x','w'))"; curl -X POST http://192.168.1.10:1883/admin/flows -H "Content-Type: application/json" -H "Node-RED-API-Version: v2" --data-binary @/tmp/x`

### Memorias en `~/.claude/projects/-home-jeanpoll/memory/`
- `project_pi_ssh_chrony.md` — setup permanente de SSH+chrony
- `feedback_usb_lan_flaky.md` — re-plug físico si el LAN cae
- `project_pi_server.md` — IP estática del Pi, escenarios disponibles
- `project_demo_network.md` — `eno1` shared NAT + `enx000a4300a7b1` LAN
- `feedback_estilo_escritura.md` — reglas anti-IA para texto en la tesis

---

## 6. Checklist final del martes (antes de irse a dormir)

- [ ] Bug A.2 DNS: confirmar la causa y aplicar fix. Validar con `tcpdump` que llegan paquetes al Pi.
- [ ] Bug A.3 Esc3 mobile: validar que con 1 dispositivo presionando el botón, el target Flask cae (probe lo confirma).
- [ ] Bug A.4 surveys: PDF de Esc1 y Esc2 sin encuesta, Esc3 con 3 respuestas exactas.
- [ ] B.1 tiempo de montaje: tabla en el notebook con los 3 escenarios.
- [ ] PAT revocado en GitHub.
- [ ] No hay copias locales corriendo en la laptop (`docker ps` solo muestra `tesis-ops-console`).
- [ ] Pi y laptop con drift < 1 s (`chronyc tracking`).
- [ ] Re-generación de los 3 PDFs con los fixes y verificación visual (figuras, tablas, no errores LaTeX).

---

*Generado el 2026-05-18 al cierre de la sesión del ensayo. Si encuentras este archivo desactualizado, archívalo y crea uno nuevo.*
