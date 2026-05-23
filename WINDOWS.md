# Runbook: convertir este PC Windows en el gateway del laboratorio CEC-EPN

Eres Claude Code en Windows. Este repo (`tesis_metrics`) está clonado en el workspace. El Pi 3B+ ya
tiene el harness desplegado y verificado desde Linux. Tu trabajo aquí: (1) red, (2) SSH al Pi y
router, (3) levantar ops-console en Docker, (4) verificar end-to-end. El operador escribirá las
contraseñas cuando se las pidas (no están en este archivo).

## DATOS (lo que no se puede leer de la partición Linux)

- Repo: https://github.com/jeanpollcardosochiriboga/tesis_metrics.git
- **Adaptador onboard / PCI Ethernet** — MAC `BC:FC:E7:D3:7C:A1` → lado **compartido de ICS** hacia
  el WAN del router. **NO ponerle IP fija** (ICS le asigna `192.168.137.1` solo).
- **Adaptador USB Ethernet** — MAC `00:0A:43:00:A7:B1` → LAN admin. **IP fija `192.168.1.20/24`, sin
  gateway, sin DNS.**
- Pi: host `192.168.1.10`, usuario `raspberry1` (la contraseña la teclea el operador).
- Router OpenWrt: host `192.168.1.1`, usuario `root` (contraseña la teclea el operador).
- ICS interno: red `192.168.137.0/24`, gateway `192.168.137.1` (no choca con el LAN `192.168.1.0/24`).
- Node-RED en el Pi: Esc1 `:1881`, Esc2 `:1882`, Esc3 `:1883`. ops-console local: `:1890`.
- Esc2 debe tener `BASE_URL=http://192.168.1.10:1882` (ya corregido en el Pi desde Linux).
- SSID 2.4 GHz actual = `'prueba pi'` → antes del evento cambiar a `'CASA ABIERTA TI'` SOLO vía flows
  Node-RED del Esc1, NUNCA por LuCI.

## Paso 1 — Identificar adaptadores

```powershell
Get-NetAdapter | Format-Table Name, MacAddress, Status
```
Mapear por MAC al onboard y al USB de arriba. Anota los `Name` de Windows de cada uno.

## Paso 2 — IP fija del USB-LAN admin (scriptable)

En PowerShell admin, con `<USB>` = Name del adaptador USB:
```powershell
New-NetIPAddress -InterfaceAlias "<USB>" -IPAddress 192.168.1.20 -PrefixLength 24
```
NO asignar gateway ni DNS (así Windows no crea ruta por defecto por ahí). Verificar:
```powershell
Get-NetIPAddress -InterfaceAlias "<USB>"
```

## Paso 3 — ICS: compartir WiFi → onboard (HAZLO POR GUI, es lo confiable)

ICS por script (COM HNetCfg) es frágil; usa la GUI:
1. `ncpa.cpl` → clic derecho en el adaptador **WiFi** → Propiedades → pestaña **Uso compartido**.
2. Marcar "Permitir que otros usuarios… a través de la conexión a Internet de este equipo".
3. En "Conexión de red doméstica" elegir el adaptador **onboard** (MAC `BC:FC:…`). Aceptar.
4. Esto fija el onboard en `192.168.137.1/24` + DHCP automáticamente. **No** edites su IP a mano.

Persistencia tras reinicio:
```powershell
Set-Service SharedAccess -StartupType Automatic
# Registro: HKLM\SYSTEM\CurrentControlSet\Services\SharedAccess\Parameters\EnableRebootPersistConnection = 1 (DWORD)
```

## Paso 4 — Llaves SSH (generar nuevas, autorizar por password una vez)

OpenSSH ya viene en Windows. En PowerShell:
```powershell
ssh-keygen -t ed25519 -f $env:USERPROFILE\.ssh\id_ed25519 -N '""'
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh raspberry1@192.168.1.10 "cat >> .ssh/authorized_keys"
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh root@192.168.1.1 "cat >> /etc/dropbear/authorized_keys"
```
(El operador teclea PI_PASS y ROUTER_PASS en cada uno.) Verificar sin password:
```powershell
ssh raspberry1@192.168.1.10 date
ssh root@192.168.1.1 uptime
```

## Paso 5 — Docker Desktop (no está instalado)

Con WiFi dando internet al propio PC (no hace falta ICS para esto), descargar e instalar Docker
Desktop (https://www.docker.com/products/docker-desktop/), habilitar WSL2 si lo pide, reiniciar, y
abrirlo una vez para que el daemon arranque. Verificar `docker version` (debe mostrar Server).

## Paso 6 — ops-console (sin Python; flows.json ya viene en el repo)

```powershell
cd ops-console
ssh-keygen -t ed25519 -f data\ssh\id_ed25519 -N '""'
type data\ssh\id_ed25519.pub | ssh raspberry1@192.168.1.10 "cat >> .ssh/authorized_keys"
ssh-keyscan 192.168.1.10 > data\ssh\known_hosts
docker compose up -d
```
Verificar `http://localhost:1890/ui`. (Si `data/flows.json` faltara, recién ahí correr
`python build_flows.py` — pero debería venir en el clon.) El compose monta `data/ssh` y `../` (raíz
del repo) → ops-console debe quedar dentro del clon.

## Paso 7 — Verificación end-to-end

1. **Internet**: `ssh raspberry1@192.168.1.10 "ping -c2 8.8.8.8 && curl -sI https://smtp.gmail.com"`;
   el WAN del router debe tener IP `192.168.137.x`.
2. **Admin/edición**: `curl http://192.168.1.10:1881/flows` responde JSON.
3. **Dashboards**: el navegador abre `http://192.168.1.10:188x` (proyectar por HDMI). El QR de Esc2
   apunta a `192.168.1.10:1882`.
4. **Métricas**: el ciclo del harness corre EN EL PI:
   `ssh raspberry1@192.168.1.10` → `cd ~/tesis_metrics_repo && ./session.sh start <esc> … end`.
   Traer CSV: `scp -r raspberry1@192.168.1.10:tesis_metrics_repo/sessions/<id> .` → subir a Google
   Drive → analizar en Colab.
5. **Esc2 SMTP**: una reserva de prueba envía correo (confirma internet end-to-end).

## TROUBLESHOOTING (resuélvelo aquí, sin volver a Linux)

- **No hay ping al Pi (192.168.1.10):** ¿el USB-LAN tiene `192.168.1.20` y status `Up`?
  (`Get-NetIPAddress`, `Get-NetAdapter`). ¿Cable en el puerto LAN amarillo, no el WAN azul? Si el
  adaptador USB es intermitente, **re-conectar físicamente** antes de diagnosticar software.
- **El router no recibe internet / WAN sin IP `192.168.137.x`:** ICS no quedó activo o se compartió el
  adaptador equivocado. Repetir Paso 3 eligiendo el onboard (MAC `BC:FC:…`) como "red doméstica".
  `Restart-Service SharedAccess`.
- **ICS no persiste tras reinicio:** confirmar `SharedAccess` en Automático y el registro
  `EnableRebootPersistConnection=1`; a veces hay que desmarcar/remarcar el uso compartido una vez.
- **SSH pide password siempre / "Permission denied (publickey)":** la pubkey no quedó en el host. En
  el Pi va a `~/.ssh/authorized_keys` (permisos 600); en OpenWrt va a `/etc/dropbear/authorized_keys`.
- **SSH "REMOTE HOST IDENTIFICATION HAS CHANGED":** el Pi/router cambió de llave de host; borrar la
  línea vieja: `ssh-keygen -R 192.168.1.10`.
- **`docker compose` falla "cannot connect to the Docker daemon":** abrir Docker Desktop y esperar a
  que el daemon arranque; `docker version` debe mostrar Server.
- **ops-console no controla el Pi:** la llave de `data/ssh` no está autorizada en el Pi, o falta
  `known_hosts`. Repetir Paso 6. El contenedor usa `/usr/src/node-red/.ssh` (uid 1000).
- **Conflicto de subred:** ICS usa `192.168.137.0/24`; si algún adaptador ya usa esa red, ICS fallará.
  No debería pasar con el LAN `192.168.1.0/24`.
