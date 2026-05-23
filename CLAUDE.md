# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.


## rules

Before providing any response, ask me the necessary questions to give me a better answer, free from errors due to lack of context. Ask only the questions that are necessary and will be useful for understanding and resolving the problem or requirement.

Make a point of reviewing your response twice before sending it. During this self-review process, identify unnecessary, inaccurate, incomplete, or unsupported information. Avoid agreeing with me if I'm wrong, and let me know. Avoid unnecessary questions or asking questions just because I asked you to. Avoid lengthy responses if they aren't necessary.


## Projects Overview

This workspace contains a two-scenario cybersecurity thesis project (CEC-EPN) built on Node-RED + Docker, plus an Nginx reverse proxy gateway that ties them together.

- **tesis_escenario2/** — Phishing simulation: a fake cinema ticketing site (Mu1ticines — typosquat de multicines.com.ec) that captures email addresses, then redirects users to an educational awareness page.
- **Escritorio/tesis_escenario1/** — Network device detection and DNS monitoring dashboard with D3.js visualization, nmap scanning, and OpenWrt router control via SSH.
- **tesis_escenario3/** — Interactive DoS simulator ("Colapso Controlado"): audience members use their phones to flood a deliberately vulnerable Flask server. Node-RED orchestrates the attack and visualizes it live. Includes a protection phase (nginx rate limiting). Runs as 4 Docker containers on an isolated network.
- **Escritorio/tesis_gateway_nginx/** — Nginx reverse proxy routing local domains to the three scenarios.

The `scrcpy/` directory is an unrelated third-party Android screen mirroring tool.

## Running Each Project

All projects use Docker Compose. Start from each project's directory:

```bash
# Escenario 1 — network monitoring (port 1881)
cd Escritorio/tesis_escenario1
cp .env.example .env   # fill in ROUTER_PASS and network IPs before first run
docker-compose up -d

# Escenario 2 — phishing simulation (port 1882)
cd tesis_escenario2
cp .env.example .env   # fill in SMTP_PASS before first run
docker-compose up -d

# Escenario 3 — DoS simulator (port 1883) — runs 4 containers on isolated esc3-net
cd tesis_escenario3
cp .env.example .env   # adjust DASH_IP and WORKERS before first run
docker-compose up -d

# Gateway — start after scenarios are up (port 8088)
cd Escritorio/tesis_gateway_nginx
docker-compose up -d
```

Stop any project with `docker-compose down` from its directory. Logs: `docker-compose logs -f`.

Escenario 1 requires `--cap-add NET_RAW` and `--cap-add NET_ADMIN` (already in its compose file) for nmap to work.

## Architecture

```
NGINX Gateway :8088
  esc1.jp.local    →  Escenario 1 :1881
  esc2.jp.local    →  Escenario 2 :1882
  esc3.jp.local    →  Escenario 3 :1883
  gateway.jp.local →  health/landing
```

Both scenarios run Node-RED (Node.js 18 Alpine). Business logic lives in `flows.json` — this is the primary source of truth for backend behavior and is what gets exported/imported through the Node-RED UI.

**Escenario 1** ingests nmap scan results and UDP syslog (DNS) from an OpenWrt router, builds a device map, and renders it as a D3.js graph. It can also SSH into the router to change SSID settings. All router credentials and network IPs are read from environment variables via `env.get('VAR')` — no hardcoded values in `flows.json`.

**Escenario 2** serves a multi-step HTML frontend (`www/`) simulating movie seat booking. On form submit, Node-RED handles `POST /api/reserve`, waits 10 s, then calls `scripts/send_email.py` to relay via Gmail SMTP. `GET /tickets` delivers the phishing-awareness page. The QR code URL is generated dynamically from `BASE_URL` (JSONata expression in the inject node) — no hardcoded IPs.

**Escenario 3** runs 4 containers on an isolated Docker network (`esc3-net`): `esc3-nodered` (orchestrator + dashboard, port 1883), `esc3-target` (intentionally vulnerable Flask app, single-threaded with a blocking route), `esc3-attacker` (Python asyncio HTTP flood with FastAPI control API), and `esc3-proxy` (nginx rate limiter used as the protection mechanism). The Node-RED dashboard has 3 tabs: QR access code, live attack visualization (SVG animation + metrics), and stats. Audience phones access `http://<IP>:1883/` (mobile attack page). The protection phase redirects attacker traffic through the nginx proxy (`esc3-proxy:8080`), which rate-limits to 5 req/s, allowing the target to recover. Intended to run alone on the Pi (shut down Esc1 and Esc2 first).

## Node-RED Development Workflow

Edit flows through the Node-RED editor UI (port 1881 or 1882), then export the updated `flows.json` via **Menu → Export → Download** and commit it. Do not edit `flows.json` by hand — the JSON structure is machine-generated and order-sensitive.

## Configuration

Both scenarios require a `.env` file (copy from `.env.example` in each directory).

**Escenario 1** (`Escritorio/tesis_escenario1/.env`):

| Variable | Description |
|----------|-------------|
| `ROUTER_IP` | OpenWrt router IP on the LAN |
| `ROUTER_PASS` | SSH password for router root user |
| `SUBNET` | Subnet to scan with nmap, e.g. `192.168.1.0/24` |
| `MY_PC_IP` | Admin machine IP (excluded from the device map) |
| `DASH_IP` | IP of the machine running Node-RED (used as QR fallback) |
| `DASH_PORT` | Dashboard port (default `1881`, change only if conflicting) |

All these values are injected into Node-RED via `env.get('VAR')` in function nodes. The dashboard QR is generated at runtime using `hostname -I`; `DASH_IP` is only used if auto-detection fails.

**Escenario 2** (`tesis_escenario2/.env`):

| Variable | Description |
|----------|-------------|
| `SMTP_USER` | Gmail address used as sender |
| `SMTP_PASS` | Gmail App Password (not account password) |
| `BASE_URL` | Public base URL, e.g. `http://esc2.jp.local:8088` |
| `SENDER_NAME` | Display name for outgoing emails |
| `SMTP_SERVER` | SMTP server hostname (optional, default `smtp.gmail.com`) |
| `SMTP_PORT` | SMTP port (optional, default `465`) |

Nginx virtual hosts are defined in `Escritorio/tesis_gateway_nginx/nginx/conf.d/default.conf`. Add `/etc/hosts` entries on the host machine for `esc1.jp.local`, `esc2.jp.local`, `esc3.jp.local`, and `gateway.jp.local` pointing to `127.0.0.1`.

**Escenario 3** (`tesis_escenario3/.env`):

| Variable | Description |
|----------|-------------|
| `DASH_PORT` | External port for Node-RED dashboard (default `1883`) |
| `DASH_IP` | Host IP used as QR fallback if auto-detect fails |
| `WORKERS` | Concurrent asyncio workers for the HTTP flood (default `50`, use `30` on Pi) |
| `TARGET_URL` | Initial flood target URL (default `http://esc3-target:5000/reservar`) |

## Git Repositories

| Project | Remote |
|---------|--------|
| `tesis_escenario1` | `https://github.com/jeanpollcardosochiriboga/tesis_escenario1_git.git` |
| `tesis_escenario2` | `https://github.com/jeanpollcardosochiriboga/IMPLEMENTACION-ESCENARIO-2.git` |
| `tesis_escenario3` | TBD — create repo and add remote before first push |
| `tesis_gateway_nginx` | local only (no remote) |

Both repos use the branch naming convention `Branch_EscenarioN_<Description>_Funcional`. Push requires a GitHub Personal Access Token (no SSH keys configured on this machine).

## Lecciones operacionales

### 2026-04-23 — Casa abierta (primer intento en campo)

**Problema 1 — Modo cliente WiFi falló (dispositivos con IP pero sin internet):**
Se intentó configurar el TP-Link Archer C7 AC1750 (OpenWrt) como cliente WiFi para recibir internet y compartirlo. Los dispositivos obtenían IP pero sin internet. Causa: la interfaz `wwan` se configuró via LuCI con asignación incorrecta de múltiples redes (`wwan wan lan wan6` en lugar de solo `wwan`), lo que rompió el NAT/masquerade.

**Problema 2 — Dashboard Esc1 perdió funciones SSH tras manipular LuCI:**
Se modificó la configuración de bandas directamente desde LuCI (192.168.1.1) en lugar de via los flujos Node-RED. Los flujos Node-RED no se modificaron, pero el estado UCI del router cambió y los comandos SSH del dashboard dejaron de funcionar. Regla: nunca modificar la configuración del router via LuCI cuando el dashboard Esc1 está en uso — usar solo los flujos Node-RED o comandos SSH explícitos.

**Problema 3 — Esc2 depende de internet (SMTP):**
El correo de "confirmación" de phishing usa SMTP (puerto 465, smtp.gmail.com). Sin internet, el envío falla silenciosamente. No requiere cambios de código — planificar conectividad antes de la presentación.

**Asignación de bandas del router (TP-Link Archer C7 AC1750 con OpenWrt):**
- `radio0` = 5 GHz → upstream cliente (STA) en modo B2, desactivado en los demás casos
- `radio1` = 2.4 GHz → AP del laboratorio, **siempre activo, siempre en modo AP**
- SSID del laboratorio: 'CASA ABIERTA TI' (sin contraseña)

**Método de conectividad que nunca falla — USB tethering:**
```
Celular → cable USB → Laptop → cable Ethernet → puerto WAN del router
```
El router hace DHCP sobre su WAN ethernet como siempre. No requiere ninguna reconfiguración del router. Ambas bandas quedan en modo AP (5 GHz desactivado si no se necesita). Funciona en cualquier venue sin importar el SSID.

**Métodos de conectividad por situación:**

| Situación | Método | radio1 (2.4GHz) | radio0 (5GHz) |
|---|---|---|---|
| Hay cable ethernet en el venue | Conectar WAN del router al cable | AP lab | off |
| Sin cable, con celular+USB | USB tethering → laptop → WAN | AP lab | off |
| Sin cable, sin USB | Hotspot propio (SSID fijo) + STA 5GHz | AP lab | STA upstream |

**Para modo B2 (STA 5GHz → hotspot propio):** `wifinet1` ya está configurado como STA en radio0. Solo actualizar SSID/clave y hacer `wifi reload`:
```bash
ssh root@192.168.1.1 "uci set wireless.wifinet1.ssid='SSID_HOTSPOT'; uci set wireless.wifinet1.encryption='psk2'; uci set wireless.wifinet1.key='CLAVE'; uci commit wireless"
# Luego en sesión separada:
ssh root@192.168.1.1 "wifi reload &"
```

### Configuración de red del PC (admin)

El PC actúa únicamente como gateway NAT y acceso admin al LAN. Dos conexiones permanentes en NetworkManager:

**Conexión `demo-wan-share` en `eno1`** — Comparte internet al WAN azul del router (10.42.0.1/24, NAT/MASQUERADE).

**Conexión `esc1-lan` en `enx000a4300a7b1`** — creada el 2026-04-26, actualizada IP el 2026-04-28. Da al PC acceso admin al LAN del router (para SSH al router y al Pi). Configuración clave:
- IP estática `192.168.1.20/24` (fuera del pool DHCP del router que empieza en .100)
- `ipv4.never-default true` — nunca agrega ruta por defecto, el internet sigue por WiFi
- `autoconnect yes` — se activa sola al conectar el cable

Si se pierde la conexión o hay que recriarla:
```bash
nmcli connection add type ethernet ifname enx000a4300a7b1 con-name "esc1-lan" \
  ipv4.method manual ipv4.addresses "192.168.1.20/24" \
  ipv4.gateway "" ipv4.never-default true autoconnect yes
```

### Raspberry Pi 3B+ — servidor principal (los 3 escenarios)

**El Pi aloja los tres escenarios.** Es el servidor de Node-RED para Esc1, Esc2 y Esc3.

**Topología objetivo:**
```
Internet (WiFi venue / tethering)
    │
 PC (Ubuntu)
 ├── eno1 demo-wan-share ──── WAN azul del router (10.42.0.1/24)
 └── enx000a4300a7b1 ──────── LAN amarillo (192.168.1.20/24, admin)
                                       │
                                OpenWrt (192.168.1.1)
                                ├── LAN amarillo ──── Pi 3B+ (192.168.1.10, eth0)
                                │                      ├── Node-RED Esc1 :1881
                                │                      ├── Node-RED Esc2 :1882
                                │                      └── Node-RED Esc3 :1883 (+ 3 contenedores)
                                └── WiFi "CASA ABIERTA TI" → teléfonos → 192.168.1.10:188x
```

**IP estática en el Pi** (en `/etc/dhcpcd.conf`):
```
interface eth0
static ip_address=192.168.1.10/24
```

**`.env` de todos los escenarios en el Pi:** `DASH_IP=192.168.1.10`

**Capacidades Docker requeridas** — ya están en `docker-compose.yml` de Esc1:
```yaml
cap_add:
  - NET_RAW
  - NET_ADMIN
```
Necesarias para que nmap funcione dentro del contenedor.

**Nota:** Esc1, Esc2 y Esc3 no corren simultáneamente en el Pi — se presenta un escenario a la vez para no agotar la RAM.
