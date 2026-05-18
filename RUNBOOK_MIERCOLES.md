# Runbook — Demo del miércoles (aula universitaria, ~20 alumnos)

Pasos exactos para correr los 3 escenarios uno por uno, capturar todas las métricas
del §4 del marco teórico y obtener el informe ejecutivo al final.

> **Regla de oro del Pi 3B+**: corre **un escenario a la vez**. Apagar el anterior
> antes de levantar el siguiente.

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

# Si el router rechaza ssh con "Connection reset" (dropbear blacklist), reinícialo:
ssh root@192.168.1.1 '/etc/init.d/dropbear restart'
```

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

## DESPUÉS DE LA CLASE — generar el informe

```bash
cd ~/tesis/metrics
.venv/bin/jupyter notebook analyze.ipynb
# o sin abrir UI:
.venv/bin/jupyter nbconvert --to notebook --execute analyze.ipynb \
    --output analyze_executed.ipynb
```

El notebook por defecto procesa la **sesión más reciente**. Si quieres una específica,
edita `SESSION_DIR` en la segunda celda.

**Salida** en `sessions/esc<N>_<fecha>_<hhmm>/`:
- `report_<id>.md` — informe ejecutivo con 5 tablas + 5 plots (cita directa al
  capítulo de Resultados de la tesis)
- `plots/01_*.png` … `05_*.png` — figuras de alta resolución
- 6 CSVs crudos como anexo / evidencia

Repite para cada uno de los 3 escenarios. Al final tendrás 3 carpetas de sesión,
3 reportes markdown, 15 plots.

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
