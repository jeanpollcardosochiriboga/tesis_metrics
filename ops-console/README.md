# Operator Console (Node-RED en la laptop)

Wizard de operación para encender / apagar los 3 escenarios del Pi desde un solo dashboard, sin abrir terminal.

## Topología

```
laptop:1890  ──┐
               ▼
Node-RED operator (Docker)
   │ exec → ssh ──► Pi 192.168.1.10
                       └── docker compose up/down esc{1,2,3}
```

## Levantar

```bash
cd ~/tesis/metrics/ops-console
docker compose build      # primera vez
docker compose up -d
```

Dashboard: <http://localhost:1890/ui/>  
Editor:    <http://localhost:1890/>

## Lo que hace cada botón

### Tab "Demo" (wizard apto para presentación)

| Botón | Acción |
|---|---|
| **INICIAR DEMO ESC1** (azul) | Apaga Esc2 y Esc3, levanta Esc1, muestra `docker ps` |
| **INICIAR DEMO ESC2** (azul) | Apaga Esc1 y Esc3, levanta Esc2 |
| **INICIAR DEMO ESC3** (azul) | Apaga Esc1 y Esc2, levanta Esc3 |
| **PANIC: APAGAR TODO** (rojo) | `docker compose down` en los 3 escenarios |
| **Refrescar estado** | Muestra qué contenedores siguen vivos |

Cada acción es atómica (la cadena `down ; down ; up` se ejecuta en una sola sesión SSH).

### Tab "Avanzado"

Por cada escenario, 4 botones granulares: UP / DOWN / RESTART / LOGS. Útil cuando algo se atasca o se quiere debugar un container específico sin romper los demás.

## Métricas

La ops-console **NO** dispara `session.sh start/end` automáticamente — eso queda en la laptop como CLI:

```bash
cd ~/tesis/metrics
./session.sh start esc3      # corre el guard de chrony, lanza colectores
# ... operador opera la ops-console UI durante la demo ...
./session.sh end             # cierra colectores, jala CSVs, ejecuta /api/export_state
```

Decisión deliberada: mantener métricas separadas reduce la superficie de fallo en la demo pública. Si la ops-console se cae, las métricas siguen.

## Cómo se autentica al Pi

La build incluye `openssh-client` y `sshpass`. El contenedor monta la llave privada ed25519 de la laptop en `/usr/src/node-red/.ssh/` (read-only). La llave pública ya está autorizada en el Pi (ver [memoria `pi_server`](../../../.claude/projects/-home-jeanpoll/memory/project_pi_server.md)).

Cambiar de Pi o usuario: editar `docker-compose.yml` (`PI_HOST`, `PI_USER`) **y** regenerar los flows:

```bash
python3 build_flows.py
docker compose restart
```

## Cambiar la UI

Toda la UI se construye desde `build_flows.py`. Editar ese script y regenerar:

```bash
python3 build_flows.py
docker compose restart
```

No editar `data/flows.json` a mano — se sobrescribe en cada build.

## Seguridad

- `data/ssh/` está gitignored: la llave privada nunca debe llegar al repo.
- La ops-console escucha en `0.0.0.0:1890`, accesible desde la LAN. Si el venue no es de confianza, restringir vía UFW o cambiar a `127.0.0.1:1890`.
- No requiere auth de Node-RED, pero el control de la demo es del operador físicamente sentado frente a la laptop.
