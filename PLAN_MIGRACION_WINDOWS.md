# Plan: migración gateway Linux → Windows + harness al Pi (handoff autocontenido)

## Context

Migrar el gateway de red de Linux a Windows (dual boot, mismo laptop; partición Linux ext4 ilegible
desde Windows, **sin USB**) y dejar el harness de métricas corriendo en el Pi 3B+. El miedo del
usuario: tener que reiniciar entre Linux y Windows para resolver errores. **Solución:** dejar en
GitHub un runbook autocontenido (`WINDOWS.md`) que Claude Code en Windows lea del workspace y ejecute
solo, con su propia sección de troubleshooting, sin depender de Linux.

Esta revisión verificó el plan contra los archivos reales. Hallazgos confirmados y corregidos:
- ✅ Layout de dos carpetas resuelve el scp "same file" (`session.sh:267`).
- ✅ Colectores del harness son **stdlib** (verificado import por import) → no instalar httpx/pyyaml/pandas en el Pi.
- ✅ `ops-console/data/flows.json` **se commitea** → en Windows **no se necesita Python ni `build_flows.py`**.
- ⚠️ `--interval` está hardcodeado en `session.sh:99` (editar ahí, no el YAML — `sample_interval_s` no se parsea).
- ⚠️ El self-SSH del Pi exige llave propia en `authorized_keys` (`docker_events_collector.py` usa `ssh` pelado sin sshpass; `PI_PASS` no lo cubre).
- ⚠️ Llaves SSH: no se rescatan; en Windows se **generan nuevas** y se autorizan por password.
- ⚠️ `BASE_URL` de Esc2 local dice `192.168.1.20:1882` (debe ser `.10`) → verificar/corregir en el Pi.
- ⚠️ Riesgo abierto (sin remediación, decisión del usuario): `.env.example` con `PI_PASS`/`ROUTER_PASS` reales ya está en GitHub.

Entorno Windows: Claude Code + VS Code + Git ya instalados; **falta Docker Desktop**. Transporte: GitHub.

---

# ESTADO (actualizado 2026-05-23)

**PARTE A — COMPLETA y verificada.** Pi listo: repo clonado en `~/tesis_metrics_repo`, self-SSH
configurado (llave propia + `127.0.0.1`/`192.168.1.10`/`localhost` en known_hosts), `.env` con
ROUTER_PASS. **Ambos modos de métricas probados en el Pi:** `session.sh` (ciclo esc3 completo:
resources/router/target_health/export_state OK) **y** `presentation.sh` (start/status/end OK).
WINDOWS.md y configs pusheados; repo privado `tesis_redaccion` creado con la redacción.
**Router: sin cambios para la migración** (WAN DHCP se adapta solo a ICS).

**Nota presentation.sh:** NO lee el YAML — usa `PI_HOST=${PI_HOST:-192.168.1.10}`. En el Pi funciona
con ese default (SSH a su propia IP de LAN vía accept-new + self-key). Se puede forzar
`PI_HOST=127.0.0.1 ./presentation.sh ...` para consistencia, pero no es necesario.

**FALTA: solo la PARTE B (lado Windows, tras reiniciar)** + renombrar SSID 'prueba pi' →
'CASA ABIERTA TI' por flows Node-RED antes del evento.

---

# PARTE A — Pre-migración en Linux (✅ HECHA — referencia)

Objetivo: dejar el Pi 100% listo y todo lo necesario en GitHub, para que en Windows solo quede red +
SSH + ops-console + verificar. **No cambiar gateway y harness a la vez.**

### A1. Desplegar y verificar el harness en el Pi (estando en Linux)
1. Editar `config/esc{1,2,3}.yaml`: `pi.host: 127.0.0.1` (hoy `192.168.1.10`). Los tres (esc3.yaml
   quedó viejo). Dejar `pi.user: raspberry1`, `remote_metrics_dir: /home/raspberry1/tesis_metrics`,
   `router.host: 192.168.1.1`.
2. (Opcional, overhead) si `docker stats` cada 1 s infla la métrica en el Pi: editar `session.sh:99`
   `--interval 1.0` → `2.0`. **Editar el YAML no sirve** (no se parsea).
3. `git add -A && git commit && git push origin main` (incluye `laptop/*`, `flows_patch/*`,
   `config/*`, notebooks, `ops-console/` con su `data/flows.json`). `.venv`, `sessions/`, `.env` fuera.
4. En el Pi: `git clone <repo> ~/tesis_metrics_repo` (NO tocar `~/tesis_metrics`, el runtime con
   `bin/` + `venv` + `sessions/`).
5. **Self-SSH del Pi (obligatorio):** en el Pi, `ssh-copy-id raspberry1@127.0.0.1` o agregar la pubkey
   de `raspberry1` a su propio `~/.ssh/authorized_keys`. Probar `ssh raspberry1@127.0.0.1 date` sin
   password. (Sin esto `docker_events.csv` queda vacío.)
6. Crear `~/tesis_metrics_repo/.env` con `ROUTER_PASS=...` (lo usa `collect_router.py` vía sshpass).
7. Verificar: `cd ~/tesis_metrics_repo && ./session.sh start esc1` → `clock-check` pasa; `status`
   muestra filas creciendo en `resources.csv`, `router.csv`, **`docker_events.csv`**; `end` deja CSV
   en `sessions/<id>/`. Repetir `start/end` para `esc2` y confirmar `email_*.csv`.

### A2. Corregir BASE_URL de Esc2 en el Pi (ahora)
- En el Pi: `grep BASE_URL ~/tesis_escenario2/.env`. Si no es `http://192.168.1.10:1882`, corregir y
  `docker compose -f ~/tesis_escenario2/docker-compose.yml up -d` para recargar. (La copia local del
  laptop decía `.20` → el QR/correo de phishing apuntaría a un host sin Esc2.)

### A3. Commitear el runbook de Windows al repo
- Crear `WINDOWS.md` en la raíz del repo `tesis_metrics` con el contenido de la **PARTE B** de abajo.
- `git add WINDOWS.md && git commit -m "docs: runbook migración a Windows" && git push`.
- (Opcional) subir `sessions/` de prueba a Google Drive desde el navegador, si se quieren los dry-runs.

### A4. Apuntar los datos que Windows no podrá leer
Todo está en la PARTE B (bloque DATOS). Confirmar que esos valores siguen vigentes antes de apagar.

---

# PARTE B — Contenido de `WINDOWS.md` (se commitea al repo; Claude Code en Windows lo ejecuta)

> Pegar TODO lo que sigue (desde "## Runbook…" hasta el final) en `WINDOWS.md` en la raíz del repo.
> Es secret-free: las contraseñas se escriben cuando el sistema las pida, no van en el archivo.

```markdown
## Runbook: convertir este PC Windows en el gateway del laboratorio CEC-EPN

Eres Claude Code en Windows. Este repo (tesis_metrics) está clonado en el workspace. El Pi 3B+ ya
tiene el harness desplegado y verificado desde Linux. Tu trabajo aquí: (1) red, (2) SSH al Pi y
router, (3) levantar ops-console en Docker, (4) verificar end-to-end. El operador escribirá las
contraseñas cuando se las pidas (no están en este archivo).

### DATOS (lo que no se puede leer de la partición Linux)
- Repo: https://github.com/jeanpollcardosochiriboga/tesis_metrics.git
- **Adaptador onboard / PCI Ethernet** — MAC `BC:FC:E7:D3:7C:A1` → lado **compartido de ICS** hacia
  el WAN del router. **NO ponerle IP fija** (ICS le asigna 192.168.137.1 solo).
- **Adaptador USB Ethernet** — MAC `00:0A:43:00:A7:B1` → LAN admin. **IP fija 192.168.1.20/24, sin
  gateway, sin DNS.**
- Pi: host `192.168.1.10`, usuario `raspberry1` (la contraseña la teclea el operador).
- Router OpenWrt: host `192.168.1.1`, usuario `root` (contraseña la teclea el operador).
- ICS interno: red `192.168.137.0/24`, gateway `192.168.137.1` (no choca con el LAN 192.168.1.0/24).
- Node-RED en el Pi: Esc1 :1881, Esc2 :1882, Esc3 :1883. ops-console local: :1890.
- Esc2 debe tener `BASE_URL=http://192.168.1.10:1882` (ya corregido en el Pi desde Linux).
- SSID 2.4 GHz actual = 'prueba pi' → antes del evento cambiar a 'CASA ABIERTA TI' SOLO vía flows
  Node-RED del Esc1, NUNCA por LuCI.

### Paso 1 — Identificar adaptadores
`Get-NetAdapter | Format-Table Name, MacAddress, Status` (PowerShell admin). Mapear por MAC al
onboard y al USB de arriba. Anota los `Name` de Windows de cada uno.

### Paso 2 — IP fija del USB-LAN admin (scriptable)
En PowerShell admin, con <USB> = Name del adaptador USB:
```
New-NetIPAddress -InterfaceAlias "<USB>" -IPAddress 192.168.1.20 -PrefixLength 24
```
NO asignar gateway ni DNS (así Windows no crea ruta por defecto por ahí). Verificar
`Get-NetIPAddress -InterfaceAlias "<USB>"`.

### Paso 3 — ICS: compartir WiFi → onboard (HAZLO POR GUI, es lo confiable)
ICS por script (COM HNetCfg) es frágil; usa la GUI:
1. `ncpa.cpl` → clic derecho en el adaptador **WiFi** → Propiedades → pestaña **Uso compartido**.
2. Marcar "Permitir que otros usuarios… a través de la conexión a Internet de este equipo".
3. En "Conexión de red doméstica" elegir el adaptador **onboard** (MAC BC:FC:…). Aceptar.
4. Esto fija el onboard en 192.168.137.1/24 + DHCP automáticamente. **No** edites su IP a mano.
Persistencia tras reinicio: servicio `SharedAccess` en Automático (`Set-Service SharedAccess
-StartupType Automatic`) y registro `HKLM\SYSTEM\CurrentControlSet\Services\SharedAccess\Parameters
\EnableRebootPersistConnection = 1`.

### Paso 4 — Llaves SSH (generar nuevas, autorizar por password una vez)
OpenSSH ya viene en Windows. En PowerShell:
```
ssh-keygen -t ed25519 -f $env:USERPROFILE\.ssh\id_ed25519 -N '""'
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh raspberry1@192.168.1.10 "cat >> .ssh/authorized_keys"
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh root@192.168.1.1 "cat >> /etc/dropbear/authorized_keys"
```
(El operador teclea PI_PASS y ROUTER_PASS en cada uno.) Verificar sin password:
`ssh raspberry1@192.168.1.10 date` y `ssh root@192.168.1.1 uptime`.

### Paso 5 — Docker Desktop (no está instalado)
Con WiFi dando internet (aún sin ICS hace falta, WiFi sirve internet al propio PC), descargar e
instalar Docker Desktop (https://www.docker.com/products/docker-desktop/), habilitar WSL2 si lo pide,
reiniciar, y abrirlo una vez para que el daemon arranque. Verificar `docker version`.

### Paso 6 — ops-console (sin Python; flows.json ya viene en el repo)
```
cd ops-console
ssh-keygen -t ed25519 -f data\ssh\id_ed25519 -N '""'
type data\ssh\id_ed25519.pub | ssh raspberry1@192.168.1.10 "cat >> .ssh/authorized_keys"
ssh-keyscan 192.168.1.10 > data\ssh\known_hosts
docker compose up -d
```
Verificar `http://localhost:1890/ui`. (Si `data/flows.json` faltara, recién ahí correr
`build_flows.py` — pero debería venir en el clon.) El compose monta `data/ssh` y `../` (raíz del
repo) → ops-console debe quedar dentro del clon.

### Paso 7 — Verificación end-to-end
1. Internet: `ssh raspberry1@192.168.1.10 "ping -c2 8.8.8.8 && curl -sI https://smtp.gmail.com"`; el
   WAN del router debe tener IP 192.168.137.x.
2. Admin/edición: `curl http://192.168.1.10:1881/flows` responde JSON.
3. Dashboards: el navegador abre `http://192.168.1.10:188x` (proyectar por HDMI). El QR de Esc2
   apunta a 192.168.1.10:1882.
4. Métricas: el ciclo del harness corre EN EL PI (`ssh raspberry1@192.168.1.10` →
   `cd ~/tesis_metrics_repo && ./session.sh start <esc> … end`). Traer CSV:
   `scp -r raspberry1@192.168.1.10:tesis_metrics_repo/sessions/<id> .` → subir a Google Drive →
   analizar en Colab.
5. Esc2 SMTP: una reserva de prueba envía correo (confirma internet end-to-end).

### TROUBLESHOOTING (resuélvelo aquí, sin volver a Linux)
- **No hay ping al Pi (192.168.1.10):** ¿el USB-LAN tiene 192.168.1.20 y status Up?
  (`Get-NetIPAddress`, `Get-NetAdapter`). ¿Cable en el puerto LAN amarillo (no el WAN azul)? Si el
  adaptador USB es intermitente, **re-conectar físicamente** antes de diagnosticar software.
- **El router no recibe internet / WAN sin IP 192.168.137.x:** ICS no quedó activo o se compartió el
  adaptador equivocado. Repetir Paso 3 eligiendo el onboard (MAC BC:FC:…) como "red doméstica".
  Reiniciar el servicio: `Restart-Service SharedAccess`.
- **ICS no persiste tras reinicio:** confirmar `SharedAccess` en Automático y el registro
  `EnableRebootPersistConnection=1`; a veces hay que desmarcar/remarcar el uso compartido una vez.
- **SSH pide password siempre / "Permission denied (publickey)":** la pubkey no quedó en el host. En
  el Pi va a `~/.ssh/authorized_keys` (permisos 600); en OpenWrt va a `/etc/dropbear/authorized_keys`.
- **SSH "REMOTE HOST IDENTIFICATION HAS CHANGED":** el Pi/router cambió de llave de host; borrar la
  línea vieja con `ssh-keygen -R 192.168.1.10`.
- **`docker compose` falla "cannot connect to the Docker daemon":** abrir Docker Desktop y esperar a
  que el daemon arranque; `docker version` debe mostrar Server.
- **ops-console no controla el Pi:** la llave de `data/ssh` no está autorizada en el Pi, o falta
  `known_hosts`. Repetir Paso 6. El contenedor usa `/usr/src/node-red/.ssh` (uid 1000).
- **Conflicto de subred:** ICS usa 192.168.137.0/24; si algún adaptador WiFi ya usa esa red, ICS
  fallará. No debería pasar con el LAN 192.168.1.0/24.
```

---

## Riesgos a recordar
- Internet = punto único de falla para Esc2 (SMTP), independiente de este cambio.
- Efecto observador del harness en el Pi 3B+: medir con/sin colectores; ajustar `session.sh:99` si infla.
- `flows.json` se edita por API/UI, nunca a mano.
- SSID 'prueba pi' → 'CASA ABIERTA TI' vía flows Node-RED, nunca LuCI.
- Reloj del Pi sin RTC: offline la hora absoluta puede desviarse; no afecta joins internos.
- Riesgo abierto (sin remediación aquí): `.env.example` con contraseñas reales ya está en GitHub.

## Resumen de decisiones
1. Linux → Windows: viable, aprobado. 2. Cables: igual. 3. Harness al Pi: dos carpetas, sin tocar
código salvo `session.sh:99` si hace falta. 4. Análisis: Google Colab. 5. ops-console: Windows +
Docker Desktop (sin Python; flows.json ya viene). 6. Reverse proxy nginx: no usar en campo. 7. Router:
sin cambios. 8. Orden: Pi listo y todo en GitHub en Linux → luego migrar. 9. Transporte: GitHub
(`WINDOWS.md`). 10. Llaves SSH: nuevas en Windows, autorizadas por password.
