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

ssh_pi() { SSHPASS="$PI_PASS" sshpass -e ssh -o StrictHostKeyChecking=accept-new "$@"; }
scp_pi() { SSHPASS="$PI_PASS" sshpass -e scp -o StrictHostKeyChecking=accept-new "$@"; }

cmd_start() {
    local scenario="${1:-}"
    [ -z "$scenario" ] && { echo "usage: session.sh start <scenario>"; exit 2; }
    local config="$HERE/config/${scenario}.yaml"
    [ -f "$config" ] || { echo "no config: $config"; exit 2; }

    local session_id="${scenario}_$(date +%Y-%m-%d_%H%M)"
    local sdir="$HERE/sessions/$session_id"
    mkdir -p "$sdir"

    # Parse config (yq if available, else awk on the bits we need)
    local pi_host pi_user pi_remote pi_scn_out containers wifi_iface lan_iface router_host router_user
    pi_host=$(awk '/^pi:/{f=1} f && /^  host:/{print $2; exit}' "$config")
    pi_user=$(awk '/^pi:/{f=1} f && /^  user:/{print $2; exit}' "$config")
    pi_remote=$(awk '/^pi:/{f=1} f && /^  remote_metrics_dir:/{print $2; exit}' "$config")
    pi_scn_out=$(awk '/^pi:/{f=1} f && /^  scenario_metrics_out:/{print $2; exit}' "$config")
    containers=$(awk '/^pi:/{f=1} f && /^  containers:/{c=1; next} c && /^    - /{print substr($0,7)} c && /^  [a-z]/{exit}' "$config" | paste -sd,)
    wifi_iface=$(awk '/^router:/{f=1} f && /^  wifi_iface:/{print $2; exit}' "$config")
    lan_iface=$(awk '/^router:/{f=1} f && /^  lan_iface:/{print $2; exit}' "$config")
    router_host=$(awk '/^router:/{f=1} f && /^  host:/{print $2; exit}' "$config")
    router_user=$(awk '/^router:/{f=1} f && /^  user:/{print $2; exit}' "$config")

    echo "[start] session $session_id"
    echo "[start] Pi agent on ${pi_user}@${pi_host} containers=${containers}"

    # Launch Pi agent (resources)
    ssh_pi "${pi_user}@${pi_host}" \
        "mkdir -p ${pi_remote}/sessions/${session_id} && \
         nohup ${pi_remote}/venv/bin/python ${pi_remote}/bin/collect_resources.py \
            --output-dir ${pi_remote}/sessions/${session_id} \
            --containers ${containers} \
            --interval 1.0 \
            >${pi_remote}/sessions/${session_id}/agent.log 2>&1 & \
         echo \$!" > "$sdir/pi_agent.pid"
    echo "[start] Pi agent PID $(cat "$sdir/pi_agent.pid")"

    # Launch router collector (local)
    ROUTER_PASS="$ROUTER_PASS" nohup python3 "$HERE/laptop/collect_router.py" \
        --output-dir "$sdir" \
        --host "$router_host" --user "$router_user" \
        --wifi-iface "$wifi_iface" --lan-iface "$lan_iface" --interval 5.0 \
        >"$sdir/router_collector.log" 2>&1 &
    echo $! > "$sdir/router_collector.pid"
    echo "[start] router collector PID $(cat "$sdir/router_collector.pid")"

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
    printf "%s,%s,%s\n" "$(date +%s)" "$event" "$notes" >> "$SDIR/events.csv"
    echo "[log] $event ${notes:+\"$notes\"}"
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
    for f in resources.csv router.csv events.csv backend_latency.csv survey.csv loadtest.csv; do
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
    if [ -n "$pi_pid" ]; then
        echo "[end] stopping Pi agent ($pi_pid)"
        ssh_pi "${PI_USER}@${PI_HOST}" "kill -TERM $pi_pid 2>/dev/null || true"
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
    for f in resources.csv router.csv events.csv backend_latency.csv survey.csv loadtest.csv; do
        local p="$d/$f"
        if [ -f "$p" ]; then printf "  %-22s %6d rows\n" "$f" "$(wc -l <"$p")"; fi
    done
}

case "${1:-}" in
    start)   shift; cmd_start "$@" ;;
    log)     shift; cmd_log "$@" ;;
    status)  cmd_status ;;
    end)     cmd_end ;;
    *) echo "usage: $0 {start <scenario>|log <event> [notes]|status|end}"; exit 2 ;;
esac
