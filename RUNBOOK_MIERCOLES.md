# Runbook — Demo del miércoles (aula universitaria, ~20 alumnos)

Pasos exactos para correr los 3 escenarios uno por uno, capturar todas las métricas
del §4 del marco teórico y obtener el informe ejecutivo al final.

> **Regla de oro del Pi 3B+**: corre **un escenario a la vez**. Apagar el anterior
> antes de levantar el siguiente.

---

## Hallazgos del ensayo del 2026-05-18 — LEER ANTES DE LA DEMO

Tras el ensayo en casa con 3 dispositivos (Pato, Pame, Jean Poll), salieron 3 bugs que **DEBEN arreglarse o documentarse antes del miércoles**. Las métricas del harness sí se capturaron correctamente en los 3 escenarios — los bugs son del UX de los escenarios, no del harness.

### Bug 1 (CRÍTICO, ARREGLADO) — `BASE_URL` del Pi apuntaba al laptop
Esc2 generaba QR con `http://192.168.1.20:1882` (laptop) en lugar de `http://192.168.1.10:1882` (Pi). Los emails de los alumnos hubieran sido procesados por el escenario que corre en la **laptop**, no por el que mide el harness — y todos los dashboards del Pi habrían quedado en cero.

**Fix aplicado**: `sed -i "s|^BASE_URL=.*|BASE_URL=http://192.168.1.10:1882|" ~/tesis_escenario2/.env` en el Pi, restart de Esc2.

**Verificación pre-clase**: `ssh raspberry1@192.168.1.10 'grep BASE_URL ~/tesis_escenario2/.env'` debe mostrar `192.168.1.10:1882`. Igualmente verificar en Esc3 que cualquier URL exterior apunte al Pi.

### Bug 2 (CRÍTICO, FIX PENDIENTE PARA EL MIÉRCOLES TEMPRANO) — botón móvil de Esc3 no dispara flood real
El botón "ATACAR" en la página móvil de los teléfonos (`http://192.168.1.10:1883/`) solo incrementa `flow.pressCount` (efecto visual + animación), pero **NO gatilla el `esc3-attacker` asyncio**. El único botón que dispara flood real al target es el botón "ATACAR" del dashboard del operador (`/ui` tab "01 - Ataque").

Durante la demo del miércoles, si los 20 alumnos solo presionan en sus celulares, el target Flask NO va a colapsar — verán contador subiendo pero el servidor seguirá respondiendo OK. Pedagógicamente queda flojo.

**Fix sugerido**: en `tesis_escenario3/flows.json`, conectar el endpoint `/api/attack/press` (que reciben los teléfonos) al mismo `function` que arranca el ataque cuando se pulsa el botón del operador. O configurarlo para que cada press del teléfono haga `pressCount % 5 == 0 → start_attack`. Revisar el cableado del nodo "Pre-start" en el flow.

**Mitigación si no hay tiempo**: tú como operador pulsas "ATACAR" desde el dashboard al mismo tiempo que los alumnos presionan en sus teléfonos. El público no se entera.

### Bug 3 (NO CRÍTICO) — DNS tracking de Esc1 no muestra qué sitios visitan
Esc1 detecta los dispositivos (nmap funciona) pero el panel "Sitio:" siempre dice "En espera de tráfico…". El router tiene la config UCI correcta (`dhcp.@dnsmasq[0].logqueries=1`, `system.log_remote=1`, `log_ip=192.168.1.10`, `log_port=5515`, `log_proto=udp`) y el Pi escucha en UDP 5515 — pero ningún paquete llega.

Causas posibles (no diagnosticadas a fondo): (a) clientes Android modernos usan DoH/DoT y no consultan al router; (b) el syslog daemon de OpenWrt no está forwardeando las queries de dnsmasq (incluso `logger -t test` desde el router no llegó al Pi).

**Mitigación**: durante la demo, presentar Esc1 enfocándose en el **descubrimiento de dispositivos** y la **auditoría de usuarios registrados** (esos sí funcionan). El "qué sitio visita" queda como feature deshabilitada — no hace falta mencionarla.

**Fix futuro**: agregar al `/etc/init.d/log` del router un `option facility 'daemon'` explícito en system, y/o forzar dnsmasq a usar `log-facility=DAEMON.NOTICE`. Probar con `logger -p daemon.notice "test"` y `tcpdump -ni eth0 udp port 5515` desde el Pi (necesita `apt install tcpdump` en el Pi primero).

### Bug 4 (MENOR) — `email_envios.csv` siempre vacío
El export_state filtra `reservations.filter(r => r.sent)`, pero el flow original de Esc2 nunca setea `r.sent = true` después del envío SMTP. El email se envía OK; el harness solo no lo registra como "envío".

**Fix sugerido**: en el function node "Enviar correo" de Esc2 flows.json, después del envío exitoso, encontrar la reservación correspondiente y setear `r.sent = true; r.sentTs = Date.now()/1000`. Actualizar `flow.reservations`.

**Mitigación**: el reporte usa el conteo de capturas como proxy de envíos (capturas = envíos intentados = envíos exitosos en práctica). Click-through-rate sigue siendo correcto.

### Bug 5 (MENOR) — `auditoria_usuarios.csv` sin timestamp epoch
La tabla del dashboard de Esc1 guarda fechas como `"9:01:42 p. m."` (string formateado), no epoch. El notebook salta gracefully ("Sin auditoria_usuarios.csv (escenario distinto o usuarios no registrados)") porque busca columna `ts`.

**Fix sugerido**: en el function node "Tabla de alias" de Esc1, agregar `ts: Date.now()/1000` al objeto guardado en `global.audit_users`.

### Bug 6 (PROCEDURAL) — `esc3_snapshots` se acumula entre sesiones
El array `global.esc3_snapshots` no se limpia al iniciar nueva sesión de métricas. Si corres `session.sh start esc3` dos veces sin restartear el contenedor, el segundo CSV incluye datos del primero.

**Workaround procedural**: antes de cada `session.sh start esc3`, hacer `ssh raspberry1@192.168.1.10 'docker restart esc3-nodered'` para limpiar contexto.

### Validación de métricas del ensayo (que sí funcionaron bien)

| Escenario | Filas en CSVs principales | Hallazgo cuantitativo |
|---|---|---|
| Esc1 (9 min, 5 dispositivos) | resources 554, router 60, backend_latency 4417, auditoria_usuarios 3 | CPU host avg ~7%, pico 16% — el Pi 3B+ va sobrado para Esc1 |
| Esc2 (13 min, 3 emails) | resources 766, router 123, backend_latency 10, email_capturas 3, email_clicks 2 | CTR = 67% (2 de 3 clickearon el enlace educativo) |
| Esc3 (13 min, 3 atacantes desde celular + flood del operador) | resources 493, target_health 702, esc3_stats_snapshot 160, survey 4 respuestas | **Disponibilidad: 98.5% (idle) → 0% (ataque) → 58% (protegido)**. Mann-Whitney `idle vs ataque` p=2.86e-31, `ataque vs protegido` p=4.77e-05 — todo estadísticamente significativo |

El `target_health_probe.py` demostró objetivamente lo que el dashboard del operador NO muestra: durante el ataque (con el botón del operador), el target Flask cae a **0% disponibilidad** durante ~50 segundos. La protección con nginx rate-limit lo recupera al ~58%.

---

## 30 minutos ANTES de la clase — preparación

### 1. Red del aula
- WiFi del campus → tu laptop (asociada).
- Cable ethernet laptop USB-LAN → puerto **WAN** del router OpenWrt (azul).
- Cable ethernet router LAN (amarillo) → Pi.
- Encender el Pi.
- Encender el router. Los alumnos se conectarán al SSID **`CASA ABIERTA TI`** (sin contraseña).

### 2. Verificación de conectividad
```bash
# La laptop debe alcanzar Pi y router:
ping -c 2 192.168.1.10   # Pi
ping -c 2 192.168.1.1    # Router

# SSH al Pi (sin password gracias a la llave ed25519 instalada el 2026-05-18):
ssh raspberry1@192.168.1.10 'date; uptime'

# Si el router rechaza ssh con "Connection reset" (dropbear blacklist o rate limit):
sshpass -p 'DTIC2025B_jp' ssh -o KexAlgorithms=+diffie-hellman-group14-sha1 \
    -o HostKeyAlgorithms=+ssh-rsa root@192.168.1.1 '/etc/init.d/dropbear restart'
# (las opciones de algoritmo legacy son necesarias para el dropbear del Archer C7)
```

### 2.5. Verificación de reloj sincronizado (chrony)
```bash
chronyc tracking | grep "Leap status"    # debe decir Normal
ssh raspberry1@192.168.1.10 'chronyc sources | head -3'
# El Pi debe tener al laptop (192.168.1.20) marcado con '^*' o '^+' como source.
# Sin esto, los CSVs cruzados (Pi vs laptop) no son joinables por timestamp,
# y session.sh start abortará si offset > 2s.
```

### 2.6. Verificación de .env del Pi (los 3 escenarios)
**Hallazgo del ensayo**: el `.env` de Esc1 estaba ausente y el `BASE_URL` de Esc2 apuntaba al laptop. Verificar:
```bash
ssh raspberry1@192.168.1.10 '
  ls ~/tesis_escenario1/.env ~/tesis_escenario2/.env ~/tesis_escenario3/.env 2>&1
  echo "--- Esc2 BASE_URL ---"
  grep BASE_URL ~/tesis_escenario2/.env
  echo "--- Esc1 DASH_IP/MY_PC_IP ---"
  grep -E "DASH_IP|MY_PC_IP" ~/tesis_escenario1/.env
'
```
Salida esperada: los 3 .env existen, `BASE_URL=http://192.168.1.10:1882`, `DASH_IP=192.168.1.10`, `MY_PC_IP=192.168.1.20`.

### 3. Verificación del harness
```bash
cd ~/tesis/metrics
ls .venv/bin/python || python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -c "import httpx, pandas, matplotlib, yaml, psutil, tabulate; print('OK')"
```

### 4. Asegurarse de que el agente del Pi está al día
```bash
./pi/install.sh raspberry1@192.168.1.10
# (idempotente: solo actualiza si hay cambios)
```

### 5. .env del harness
```bash
cat ~/tesis/metrics/.env
# debe tener PI_PASS y ROUTER_PASS
```

---

## CICLO POR ESCENARIO (3 veces, una por escenario)

Misma secuencia para Esc1, Esc2, Esc3 — solo cambia el nombre y el orden de
arranque/apagado de contenedores.

### Plantilla — adapta `<N>` a `1`, `2` o `3`

```bash
# (A) ARRANCAR EL ESCENARIO N
ssh raspberry1@192.168.1.10 'cd ~/tesis_escenario<N>* && docker compose up -d'
# Espera 10-20 s hasta que Node-RED arranque
sleep 20

# (B) ABRIR LA SESIÓN DE MEDICIÓN
cd ~/tesis/metrics
./session.sh start esc<N>
# Esto:
#  - SSH al Pi → lanza collect_resources.py en background (CPU/RAM cada 1s)
#  - Local → lanza collect_router.py (estaciones WiFi cada 5s)
#  - Detecta pi_boot, escribe events.csv con session_start
#  - Estado guardado en .session_state

# (C) ANOTAR EVENTOS CLAVE DURANTE LA DEMO
./session.sh log demo_start "comenzó la presentación"
# ... cuando llegue el primer teléfono ...
./session.sh log first_user "primer phone conectado"
# ... cuando empiece la fase activa (ataque DoS, click phishing, etc.) ...
./session.sh log fase_activa "alumnos atacando / llenando form / etc."
# ... al final de la demo ...
./session.sh log demo_end "fin ventana de público"

# (D) DESPUÉS DE LA DEMO — CARGA SINTÉTICA (opcional, solo si te queda tiempo)
# Solo en lab, NUNCA durante la demo pública.
.venv/bin/python laptop/loadgen.py --config config/esc<N>.yaml \
    --output-dir sessions/$(cat .session_state | grep SDIR | cut -d'"' -f2 | xargs basename)
./session.sh log loadgen_done "rampa sintética terminada"

# (E) CERRAR LA SESIÓN
./session.sh end
# Esto:
#  - Detiene los recolectores
#  - scp del resources.csv del Pi
#  - scp del backend_latency.csv y survey.csv
#  - Imprime resumen de filas por CSV

# (F) APAGAR EL ESCENARIO N (libera RAM del Pi para el siguiente)
ssh raspberry1@192.168.1.10 'cd ~/tesis_escenario<N>* && docker compose down'
```

---

## Notas específicas por escenario

### Esc1 — Monitoreo de red
- **URL alumnos**: `http://192.168.1.10:1881/` (mostrar QR del dashboard a los alumnos)
- **Acción esperada**: alumnos navegan el dashboard, ven el grafo de su propio teléfono aparecer.
- **Pestaña de encuesta**: `http://192.168.1.10:1881/survey.html?scenario=esc1` — agrégala como QR en una diapositiva final.
- **Contenedores Pi**: `esc1-nodered` (1).
- **No requiere internet del aula** para funcionar.

### Esc2 — Phishing simulado Mu1ticines
- **URL alumnos** (la falsa): `http://192.168.1.10:1882/` (simula `mu1ticines.com.ec`)
- **Acción esperada**: alumnos escanean QR → ven cartelera → "reservan" → entregan email → llega correo de "confirmación" → click → llegan a página educativa.
- **Pestaña de encuesta**: `http://192.168.1.10:1882/survey.html?scenario=esc2` (servir en la pantalla final educativa).
- **Contenedores Pi**: `jp-esc2-nodered` (1).
- **REQUIERE internet** (Gmail SMTP). Si la WiFi del aula falla, el envío del correo falla silenciosamente — la captura del email ya quedó registrada.

### Esc3 — DoS "Colapso Controlado"
- **URL alumnos** (atacante): `http://192.168.1.10:1883/` — abre el dashboard mobile con el botón "ATACAR".
- **Acción esperada**: el operador pulsa "LANZAR" en el dashboard de control → los alumnos pulsan "atacar" desde sus teléfonos → ven el servidor CONAFIPS cayendo → operador pulsa "PROTEGER" → recuperación.
- **Pestaña de encuesta**: **ya integrada como 4ta tab "04_ Encuesta"** del dashboard — al terminar el ataque, navega a esa pestaña y muestra el QR a los alumnos.
- **Contenedores Pi** (4): `esc3-nodered`, `esc3-target`, `esc3-attacker`, `esc3-proxy`.
- **No requiere internet** para funcionar.
- **OJO**: NO corras `loadgen.py` durante la demo real — los alumnos ya generan el ataque desde sus teléfonos.

---

## DESPUÉS DE LA CLASE — generar el informe + PDF

Para cada una de las 3 sesiones, generar el reporte `.md` y el `.pdf`:

```bash
cd ~/tesis/metrics
for SESSION in sessions/esc1_*_<fecha> sessions/esc2_*_<fecha> sessions/esc3_*_<fecha>; do
  SESSION_DIR_OVERRIDE="$SESSION" .venv/bin/jupyter nbconvert --to notebook --execute analyze.ipynb \
      --output "/tmp/analyze_$(basename $SESSION).ipynb" \
      --ExecutePreprocessor.timeout=180
  ./make_pdf.sh "$SESSION"
done
```

(La variable `SESSION_DIR_OVERRIDE` fue añadida al notebook el 2026-05-18 para procesar sesiones específicas en batch sin editar a mano.)

**Salida** en `sessions/esc<N>_<fecha>_<hhmm>/`:
- `report_<id>.md` — informe en markdown con 13 secciones (resumen, recursos, latencia, encuesta, target_health, RX/TX, adopción, funnel, eventos docker, análisis estadístico Mann-Whitney + IC, glosario)
- `reporte_<id>.pdf` — versión PDF con plantilla eisvogel (portada, índice, lang=es)
- `plots/*.png` — hasta 10 figuras de alta resolución
- ~10 CSVs crudos como anexo / evidencia

Repite para cada uno de los 3 escenarios. Al final tendrás 3 carpetas de sesión, 3 reportes markdown, 3 PDFs, ~30 plots.

### Tip: ops-console wizard

Mientras corres la demo, la **ops-console** está en `http://localhost:1890/ui` (contenedor Docker en la laptop, `~/tesis/metrics/ops-console/`). Tiene 3 botones grandes para apagar/encender escenarios en el Pi vía SSH + 1 botón PANIC rojo + tab "Avanzado" con controles granulares. Útil como red de seguridad si la terminal falla.

---

## Troubleshooting

| Síntoma | Causa probable | Fix |
|---|---|---|
| `ssh: Connection reset by peer` al router | dropbear blacklist en memoria | `ssh root@192.168.1.1 '/etc/init.d/dropbear restart'` |
| `docker compose up` se cuelga en el Pi | RAM saturada (escenario anterior aún corriendo) | `ssh raspberry1@192.168.1.10 'docker ps' && docker compose down` en el anterior |
| `session.sh end` no encuentra archivos en el Pi | el agente nunca arrancó | revisar `sessions/<id>/pi_agent.pid` y `agent.log` |
| Los teléfonos no se asocian al WiFi | router en modo cliente o radio2.4 caído | `ssh root@192.168.1.1 'wifi status'` — verificar radio1 (2.4 GHz) en modo AP |
| `survey.csv` no se llena | el form HTML no llega al endpoint POST | abrir DevTools en el celular, ver si `/api/survey` responde 200 |
| `backend_latency.csv` no crece | container reiniciado sin pasar por `settings.js` | `docker compose restart` en el escenario |
| Notebook falla en una celda | datos faltantes (p. ej. router.csv vacío) | el notebook salta gracefully; revisar mensaje específico |

---

## Checklist final del miércoles

Antes de salir del aula:

- [ ] Tienes 3 carpetas en `sessions/` (una por escenario)
- [ ] Cada carpeta tiene al menos `resources.csv`, `backend_latency.csv`, `events.csv`
- [ ] Las 3 demos terminaron con al menos 10 respuestas en `survey.csv`
- [ ] Anotaste en `events.csv notes` cualquier incidencia (caídas, alumnos confundidos, etc.)
- [ ] Hiciste `./session.sh end` después de cada demo (no dejaste agentes corriendo)
- [ ] Apagaste el último escenario (`docker compose down` en el último que corriste)
