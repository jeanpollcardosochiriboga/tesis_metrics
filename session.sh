#!/usr/bin/env bash
# Orchestrator for a metrics session.
#
# Usage:
#   ./session.sh start <scenario>     # start agents, create session dir
#   ./session.sh log <event> [notes]  # append to events.csv
#   ./session.sh status               # show running agents and current session
#   ./session.sh end                  # stop agents, pull CSVs from Pi
#
# Reads PI_PASS and ROUTER_PASS from .env.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
STATE_FILE="$HERE/.session_state"

# --- load env ---
[ -f "$HERE/.env" ] && set -a && . "$HERE/.env" && set +a

read_state() {
    [ -f "$STATE_FILE" ] || { echo "no active session"; exit 1; }
    . "$STATE_FILE"
}

# Use SSH key auth when ~/.ssh/id_ed25519 exists; fall back to sshpass otherwise.
if [ -f "$HOME/.ssh/id_ed25519" ]; then
    ssh_pi() { ssh -o StrictHostKeyChecking=accept-new -o BatchMode=yes "$@"; }
    scp_pi() { scp -o StrictHostKeyChecking=accept-new -o BatchMode=yes "$@"; }
else
    ssh_pi() { SSHPASS="$PI_PASS" sshpass -e ssh -o StrictHostKeyChecking=accept-new "$@"; }
    scp_pi() { SSHPASS="$PI_PASS" sshpass -e scp -o StrictHostKeyChecking=accept-new "$@"; }
fi

# Aborts if Pi<->laptop clock skew > 2 s. Without this, cross-host CSVs
# (resources.csv from Pi vs router.csv/backend_latency.csv from laptop) cannot
# be joined on timestamp.
check_clock_offset() {
    local pi_user="$1" pi_host="$2" threshold_ms="${3:-2000}"
    local t1 t2 t3 rtt_ms off_ms
    t1=$(date +%s.%N)
    t2=$(ssh_pi -o ConnectTimeout=5 "${pi_user}@${pi_host}" 'date +%s.%N' 2>/dev/null) || {
        echo "[clock-check] ABORT: SSH to ${pi_user}@${pi_host} failed"; return 1; }
    t3=$(date +%s.%N)
    read -r rtt_ms off_ms < <(awk -v t1="$t1" -v t2="$t2" -v t3="$t3" \
        'BEGIN{ rtt=(t3-t1)*1000; off=(t2-(t1+t3)/2)*1000;
                printf "%.0f %.0f\n", rtt, (off<0?-off:off) }')
    echo "[clock-check] Pi=${pi_host} rtt=${rtt_ms}ms |offset|=${off_ms}ms (threshold ${threshold_ms}ms)"
    if [ "$off_ms" -gt "$threshold_ms" ]; then
        echo "[clock-check] ABORT: offset > ${threshold_ms}ms — restart chrony on both hosts and retry"
        echo "             laptop: sudo systemctl restart chrony"
        echo "             pi:     ssh ${pi_user}@${pi_host} sudo systemctl restart chrony"
        return 1
    fi
}

cmd_start() {
    local scenario="${1:-}"
    [ -z "$scenario" ] && { echo "usage: session.sh start <scenario>"; exit 2; }
    local config="$HERE/config/${scenario}.yaml"
    [ -f "$config" ] || { echo "no config: $config"; exit 2; }

    # Formato de carpeta: fecha_escenario (T7), ej. 2026-05-22_esc1. Si ya existe
    # una sesión del mismo día y escenario, se desambigua con la hora.
    local session_id="$(date +%Y-%m-%d)_${scenario}"
    if [ -e "$HERE/sessions/$session_id" ]; then
        session_id="${session_id}_$(date +%H%M)"
    fi
    local sdir="$HERE/sessions/$session_id"
    mkdir -p "$sdir"

    # Parse config (yq if available, else awk on the bits we need)
    local pi_host pi_user pi_remote pi_scn_out containers wifi_iface lan_iface router_host router_user
    pi_host=$(awk '/^pi:/{f=1} f && /^  host:/{print $2; exit}' "$config")
    pi_user=$(awk '/^pi:/{f=1} f && /^  user:/{print $2; exit}' "$config")
    pi_remote=$(awk '/^pi:/{f=1} f && /^  remote_metrics_dir:/{print $2; exit}' "$config")
    pi_scn_out=$(awk '/^pi:/{f=1} f && /^  scenario_metrics_out:/{print $2; exit}' "$config")
    # Strip the leading "    - " and any inline "# comment" before joining with commas.
    containers=$(awk '/^pi:/{f=1} f && /^  containers:/{c=1; next} c && /^    - /{print substr($0,7)} c && /^  [a-z]/{exit}' "$config" \
                 | sed -E 's/[[:space:]]*#.*$//; s/[[:space:]]+$//' \
                 | paste -sd,)
    wifi_iface=$(awk '/^router:/{f=1} f && /^  wifi_iface:/{print $2; exit}' "$config")
    lan_iface=$(awk '/^router:/{f=1} f && /^  lan_iface:/{print $2; exit}' "$config")
    router_host=$(awk '/^router:/{f=1} f && /^  host:/{print $2; exit}' "$config")
    router_user=$(awk '/^router:/{f=1} f && /^  user:/{print $2; exit}' "$config")

    echo "[start] session $session_id"
    echo "[start] Pi agent on ${pi_user}@${pi_host} containers=${containers}"

    check_clock_offset "$pi_user" "$pi_host" || { rm -rf "$sdir"; exit 3; }

    # Launch Pi agent (resources). The `(nohup ... &)` subshell + sleep + pgrep
    # pattern is required so SSH itself doesn't hang waiting for the
    # background process's pipes to close (well-known SSH gotcha).
    local pi_session_dir="${pi_remote}/sessions/${session_id}"
    ssh_pi "${pi_user}@${pi_host}" \
        "mkdir -p ${pi_session_dir} && \
         sh -c '(nohup ${pi_remote}/venv/bin/python ${pi_remote}/bin/collect_resources.py \
            --output-dir ${pi_session_dir} \
            --containers ${containers} \
            --interval 1.0 \
            </dev/null >${pi_session_dir}/agent.log 2>&1 &)' && \
         sleep 0.4 && \
         pgrep -f \"collect_resources.py.*${session_id}\" | tail -1" \
        > "$sdir/pi_agent.pid" < /dev/null
    echo "[start] Pi agent PID $(cat "$sdir/pi_agent.pid")"

    # Launch router collector (local)
    ROUTER_PASS="$ROUTER_PASS" nohup python3 "$HERE/laptop/collect_router.py" \
        --output-dir "$sdir" \
        --host "$router_host" --user "$router_user" \
        --wifi-iface "$wifi_iface" --lan-iface "$lan_iface" --interval 5.0 \
        >"$sdir/router_collector.log" 2>&1 &
    echo $! > "$sdir/router_collector.pid"
    echo "[start] router collector PID $(cat "$sdir/router_collector.pid")"

    # Stream `docker events` from the Pi: container restarts, OOM kills, deaths.
    # Without this, a crashed container leaves no forensic trace.
    nohup python3 "$HERE/laptop/docker_events_collector.py" \
        --output-dir "$sdir" \
        --pi-user "$pi_user" --pi-host "$pi_host" \
        >"$sdir/docker_events.log" 2>&1 &
    echo $! > "$sdir/docker_events.pid"
    echo "[start] docker events collector PID $(cat "$sdir/docker_events.pid")"

    # Esc3-only: probe target Flask availability (the metric that illustrates
    # the DoS scenario; the Node-RED middleware instruments the orchestrator,
    # not the target).
    if [ "$scenario" = "esc3" ]; then
        nohup python3 "$HERE/laptop/target_health_probe.py" \
            --output-dir "$sdir" \
            --target-url "http://${pi_host}:5000/" \
            --orchestrator-url "http://${pi_host}:1883" \
            --interval 1.0 \
            >"$sdir/target_health.log" 2>&1 &
        echo $! > "$sdir/target_health.pid"
        echo "[start] target health probe PID $(cat "$sdir/target_health.pid")"
    fi

    # Write state
    cat > "$STATE_FILE" <<EOF
SESSION_ID="$session_id"
SCENARIO="$scenario"
SDIR="$sdir"
CONFIG="$config"
PI_HOST="$pi_host"
PI_USER="$pi_user"
PI_REMOTE="$pi_remote"
PI_SCN_OUT="$pi_scn_out"
EOF

    # events.csv: emit start marker
    echo "ts,event,notes" > "$sdir/events.csv"
    cmd_log session_start "scenario=$scenario session=$session_id"

    # Detect Pi boot time
    local boot_epoch
    boot_epoch=$(ssh_pi "${pi_user}@${pi_host}" "awk 'BEGIN{srand(); cmd=\"date +%s\"; cmd|getline now; close(cmd); cmd=\"awk \\\"{print int(\\\\\\\$1)}\\\" /proc/uptime\"; cmd|getline up; close(cmd); print now-up}'" 2>/dev/null || echo "")
    if [ -n "$boot_epoch" ]; then
        printf "%s,pi_boot,uptime epoch\n" "$boot_epoch" >> "$sdir/events.csv"
    fi

    echo "[start] session active at $sdir"
}

cmd_log() {
    read_state
    local event="${1:-}" notes="${2:-}"
    [ -z "$event" ] && { echo "usage: session.sh log <event> [notes]"; exit 2; }
    # Escape commas/quotes/newlines in notes per CSV rules (RFC 4180).
    if printf '%s' "$notes" | grep -q '[,"\n]'; then
        notes='"'"$(printf '%s' "$notes" | sed 's/"/""/g')"'"'
    fi
    printf "%s,%s,%s\n" "$(date +%s)" "$event" "$notes" >> "$SDIR/events.csv"
    echo "[log] $event ${notes:+\"$notes\"}"
}

cmd_deploy() {
    # Mide el tiempo de despliegue (§4.4): levanta el escenario en frío y cronometra
    # hasta el primer HTTP 200. Requiere una sesión activa (corre `start` primero,
    # con el escenario aún abajo para que resources.csv capture el arranque).
    read_state
    echo "[deploy] midiendo despliegue de $SCENARIO en ${PI_HOST}"
    PI_PASS="${PI_PASS:-}" python3 "$HERE/laptop/measure_deploy.py" \
        --scenario "$SCENARIO" \
        --output-dir "$SDIR" \
        --pi-host "$PI_HOST" --pi-user "$PI_USER" || \
        echo "[deploy] la medición falló (ver salida arriba)"
    # Deja una marca en events.csv con el resultado.
    if [ -f "$SDIR/deploy.csv" ]; then
        local last; last=$(tail -1 "$SDIR/deploy.csv")
        cmd_log deploy_measured "$last"
    fi
}

cmd_status() {
    if [ ! -f "$STATE_FILE" ]; then echo "no active session"; return; fi
    read_state
    echo "session: $SESSION_ID  scenario: $SCENARIO"
    echo "dir:     $SDIR"
    local pi_pid router_pid
    pi_pid=$(cat "$SDIR/pi_agent.pid" 2>/dev/null || echo "?")
    router_pid=$(cat "$SDIR/router_collector.pid" 2>/dev/null || echo "?")
    echo "pi agent PID (on Pi): $pi_pid"
    if [ "$router_pid" != "?" ] && kill -0 "$router_pid" 2>/dev/null; then
        echo "router collector PID (local): $router_pid (running)"
    else
        echo "router collector PID (local): $router_pid (NOT running)"
    fi
    echo
    for f in resources.csv router.csv events.csv deploy.csv backend_latency.csv survey.csv loadtest.csv \
             auditoria_usuarios.csv email_capturas.csv email_envios.csv email_clicks.csv router_devices.csv router_resources.csv \
             esc3_stats_snapshot.csv target_health.csv docker_events.csv; do
        local p="$SDIR/$f"
        if [ -f "$p" ]; then
            printf "  %-22s %6d rows\n" "$f" "$(wc -l <"$p")"
        else
            printf "  %-22s (missing)\n" "$f"
        fi
    done
}

cmd_end() {
    read_state
    cmd_log session_end "ending"
    local pi_pid router_pid
    pi_pid=$(cat "$SDIR/pi_agent.pid" 2>/dev/null || echo "")
    router_pid=$(cat "$SDIR/router_collector.pid" 2>/dev/null || echo "")

    if [ -n "$router_pid" ] && kill -0 "$router_pid" 2>/dev/null; then
        echo "[end] stopping router collector ($router_pid)"
        kill -TERM "$router_pid" || true
    fi
    local target_pid
    target_pid=$(cat "$SDIR/target_health.pid" 2>/dev/null || echo "")
    if [ -n "$target_pid" ] && kill -0 "$target_pid" 2>/dev/null; then
        echo "[end] stopping target health probe ($target_pid)"
        kill -TERM "$target_pid" || true
    fi
    local events_pid
    events_pid=$(cat "$SDIR/docker_events.pid" 2>/dev/null || echo "")
    if [ -n "$events_pid" ] && kill -0 "$events_pid" 2>/dev/null; then
        echo "[end] stopping docker events collector ($events_pid)"
        kill -TERM "$events_pid" || true
    fi
    if [ -n "$pi_pid" ]; then
        echo "[end] stopping Pi agent ($pi_pid)"
        ssh_pi "${PI_USER}@${PI_HOST}" "kill -TERM $pi_pid 2>/dev/null || true"
    fi

    # Pull /api/export_state from the scenario's Node-RED (tables that only
    # live in flow/global context — Esc1 audit_users, Esc2 reservations+clicks,
    # Esc3 stats snapshots).
    local nodered_port
    case "$SCENARIO" in
        esc1) nodered_port=1881 ;;
        esc2) nodered_port=1882 ;;
        esc3) nodered_port=1883 ;;
        *)    nodered_port="" ;;
    esac
    if [ -n "$nodered_port" ]; then
        echo "[end] fetching /api/export_state from ${PI_HOST}:${nodered_port}"
        python3 "$HERE/laptop/fetch_export_state.py" \
            "http://${PI_HOST}:${nodered_port}" "$SDIR" || \
            echo "  (export_state fetch failed — scenario may not have the endpoint yet)"
    fi

    echo "[end] pulling resources.csv from Pi"
    scp_pi "${PI_USER}@${PI_HOST}:${PI_REMOTE}/sessions/${SESSION_ID}/resources.csv" "$SDIR/resources.csv" || \
        echo "  (no resources.csv yet)"

    echo "[end] pulling backend_latency.csv and survey.csv from Pi (scenario metrics_out)"
    scp_pi "${PI_USER}@${PI_HOST}:${PI_SCN_OUT}/backend_latency.csv" "$SDIR/backend_latency.csv" 2>/dev/null || \
        echo "  (no backend_latency.csv — middleware not installed yet?)"
    scp_pi "${PI_USER}@${PI_HOST}:${PI_SCN_OUT}/survey.csv" "$SDIR/survey.csv" 2>/dev/null || \
        echo "  (no survey.csv — form not used yet?)"

    rm -f "$STATE_FILE"
    echo "[end] session closed. Files in $SDIR"
    cmd_status_after "$SDIR"
}

cmd_status_after() {
    local d="$1"
    echo
    for f in resources.csv router.csv events.csv deploy.csv backend_latency.csv survey.csv loadtest.csv \
             auditoria_usuarios.csv email_capturas.csv email_envios.csv email_clicks.csv router_devices.csv router_resources.csv \
             esc3_stats_snapshot.csv target_health.csv docker_events.csv; do
        local p="$d/$f"
        if [ -f "$p" ]; then printf "  %-22s %6d rows\n" "$f" "$(wc -l <"$p")"; fi
    done
}

case "${1:-}" in
    start)   shift; cmd_start "$@" ;;
    deploy)  cmd_deploy ;;
    log)     shift; cmd_log "$@" ;;
    status)  cmd_status ;;
    end)     cmd_end ;;
    *) echo "usage: $0 {start <scenario>|deploy|log <event> [notes]|status|end}"; exit 2 ;;
esac
