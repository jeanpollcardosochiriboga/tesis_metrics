#!/usr/bin/env bash
# Monitor continuo de la PRESENTACION completa (las metricas que pide el tutor):
#   - Consumo de recursos (CPU y memoria) del Pi, muestreado 1/s sin interrupcion
#     durante toda la demo -> sessions/presentacion_<fecha>/resources.csv
#   - Bitacora con la hora EXACTA en que empieza cada prototipo -> bitacora.csv
#   - Tiempo de montaje (deploy hasta "listo") de cada escenario.
#
# A diferencia de session.sh (una sesion por escenario), este corre UNA sola
# captura continua para que la grafica abarque toda la presentacion y se vea a
# que escenario corresponde cada tramo.
#
# Uso:
#   ./presentation.sh start                 # arranca el monitor continuo
#   ./presentation.sh deploy <esc1|esc2|esc3>   # baja los demas, sube ese, mide montaje, marca inicio
#   ./presentation.sh mark "<texto>"        # marca manual en la bitacora (p.ej. si cambias por ops-console)
#   ./presentation.sh teardown <escN>       # mide tiempo de desmontaje
#   ./presentation.sh status                # estado
#   ./presentation.sh end                   # detiene el monitor y baja resources.csv
#   ./presentation.sh plot                  # genera la grafica de la sesion actual/ultima
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
STATE="$HERE/.presentation_state"
[ -f "$HERE/.env" ] && set -a && . "$HERE/.env" && set +a

PI_USER="${PI_USER:-raspberry1}"
PI_HOST="${PI_HOST:-192.168.1.10}"
PI_REMOTE="${PI_REMOTE:-/home/raspberry1/tesis_metrics}"
CONTAINERS="${CONTAINERS:-esc1-nodered,jp-esc2-nodered,esc3-nodered,esc3-target,esc3-attacker,esc3-proxy}"

if [ -f "$HOME/.ssh/id_ed25519" ]; then
    ssh_pi() { ssh -o StrictHostKeyChecking=accept-new -o BatchMode=yes "$@"; }
    scp_pi() { scp -o StrictHostKeyChecking=accept-new -o BatchMode=yes "$@"; }
else
    ssh_pi() { SSHPASS="$PI_PASS" sshpass -e ssh -o StrictHostKeyChecking=accept-new "$@"; }
    scp_pi() { SSHPASS="$PI_PASS" sshpass -e scp -o StrictHostKeyChecking=accept-new "$@"; }
fi

iso() { date -d "@$1" "+%Y-%m-%d %H:%M:%S" 2>/dev/null || date "+%Y-%m-%d %H:%M:%S"; }

bitacora() {  # ts hito escenario notas
    local ts="$1" hito="$2" esc="${3:-}" notas="${4:-}"
    printf '%s,%s,%s,%s,%s\n' "$ts" "$(iso "$ts")" "$hito" "$esc" "$notas" >> "$SDIR/bitacora.csv"
}

port_for() { case "$1" in esc1) echo 1881;; esc2) echo 1882;; esc3) echo 1883;; *) echo "";; esac; }

check_clock() {
    local t1 t2 t3 off
    t1=$(date +%s.%N)
    t2=$(ssh_pi -o ConnectTimeout=6 "${PI_USER}@${PI_HOST}" 'date +%s.%N') || { echo "[clock] ABORT: SSH fallo"; return 1; }
    t3=$(date +%s.%N)
    off=$(awk -v t1="$t1" -v t2="$t2" -v t3="$t3" 'BEGIN{o=(t2-(t1+t3)/2)*1000; printf "%.0f", (o<0?-o:o)}')
    echo "[clock] |offset| Pi<->laptop = ${off} ms (umbral 2000)"
    [ "$off" -le 2000 ] || { echo "[clock] ABORT: reinicia chrony en ambos y reintenta"; return 1; }
}

cmd_start() {
    [ -f "$STATE" ] && { echo "ya hay una presentacion activa ($(. "$STATE"; echo "$SDIR")). Usa end primero."; exit 1; }
    check_clock || exit 3
    local id="presentacion_$(date +%Y-%m-%d_%H%M)"
    local sdir="$HERE/sessions/$id"
    local SDIR="$sdir"   # visible a bitacora() por scope dinamico
    mkdir -p "$sdir"
    local rdir="${PI_REMOTE}/sessions/${id}"
    echo "[start] $id  (host + contenedores: ${CONTAINERS})"
    ssh_pi "${PI_USER}@${PI_HOST}" \
        "mkdir -p ${rdir} && sh -c '(nohup ${PI_REMOTE}/venv/bin/python ${PI_REMOTE}/bin/collect_resources.py \
            --output-dir ${rdir} --containers ${CONTAINERS} --interval 1.0 \
            </dev/null >${rdir}/agent.log 2>&1 &)' && sleep 0.5 && \
         pgrep -f \"collect_resources.py.*${id}\" | tail -1" > "$sdir/pi_agent.pid" < /dev/null
    echo "[start] colector en Pi PID $(cat "$sdir/pi_agent.pid")"
    cat > "$STATE" <<EOF
ID="$id"
SDIR="$sdir"
RDIR="$rdir"
EOF
    echo "ts,iso,hito,escenario,notas" > "$sdir/bitacora.csv"
    bitacora "$(date +%s)" "inicio_presentacion" "" "monitor continuo activo"

    # Watcher: detecta cuando cada escenario queda listo (sea por ops-console,
    # SSH o deploy) y registra hora de inicio + tiempo de montaje.
    local key=""; [ -f "$HOME/.ssh/id_ed25519" ] && key="$HOME/.ssh/id_ed25519"
    nohup python3 "$HERE/laptop/presentation_watcher.py" \
        --bitacora "$sdir/bitacora.csv" --pi-host "$PI_HOST" --pi-user "$PI_USER" \
        ${key:+--ssh-key "$key"} --interval 1.5 \
        >"$sdir/watcher.log" 2>&1 &
    echo $! > "$sdir/watcher.pid"
    echo "[start] watcher PID $(cat "$sdir/watcher.pid")  (mide montaje aunque levantes por ops-console)"
    echo "[start] bitacora -> $sdir/bitacora.csv"
}

cmd_deploy() {
    . "$STATE" 2>/dev/null || { echo "no hay presentacion activa (start primero)"; exit 1; }
    local esc="${1:-}"; local port; port=$(port_for "$esc")
    [ -z "$port" ] && { echo "uso: deploy <esc1|esc2|esc3>"; exit 2; }
    bitacora "$(date +%s)" "deploy_issued" "$esc" "via presentation.sh deploy"
    echo "[deploy] $esc: bajando los demas y levantando (el watcher registra el montaje)..."
    ssh_pi "${PI_USER}@${PI_HOST}" "
        for o in esc1 esc2 esc3; do
          [ \"\$o\" != \"$esc\" ] && (cd ~/tesis_\${o/esc/escenario} 2>/dev/null && docker compose down >/dev/null 2>&1 || true);
        done
        cd ~/tesis_${esc/esc/escenario} && docker compose up -d >/dev/null 2>&1"
    echo "[deploy] ${esc} lanzado. Mira la bitacora: el watcher anota 'scenario_ready' con el tiempo de montaje cuando responda."
}

cmd_teardown() {
    . "$STATE" 2>/dev/null || { echo "no hay presentacion activa"; exit 1; }
    local esc="${1:-}"; [ -z "$(port_for "$esc")" ] && { echo "uso: teardown <escN>"; exit 2; }
    local t0; t0=$(date +%s)
    bitacora "$t0" "teardown_start" "$esc" ""
    ssh_pi "${PI_USER}@${PI_HOST}" "cd ~/tesis_${esc/esc/escenario} && docker compose down >/dev/null 2>&1"
    local t1; t1=$(date +%s)
    bitacora "$t1" "teardown_done" "$esc" "teardown_seconds=$((t1 - t0))"
    echo "[teardown] ${esc} desmontado en $((t1 - t0))s"
}

cmd_mark() {
    . "$STATE" 2>/dev/null || { echo "no hay presentacion activa"; exit 1; }
    local txt="${1:-}"; [ -z "$txt" ] && { echo "uso: mark \"texto\""; exit 2; }
    bitacora "$(date +%s)" "marca" "" "$txt"
    echo "[mark] $txt"
}

cmd_status() {
    [ -f "$STATE" ] || { echo "sin presentacion activa"; return; }
    . "$STATE"
    echo "presentacion: $ID"
    echo "dir: $SDIR"
    echo "filas resources.csv en Pi: $(ssh_pi "${PI_USER}@${PI_HOST}" "wc -l < ${RDIR}/resources.csv 2>/dev/null" 2>/dev/null || echo '?')"
    echo "--- bitacora ---"; cat "$SDIR/bitacora.csv"
}

cmd_end() {
    . "$STATE" 2>/dev/null || { echo "sin presentacion activa"; exit 1; }
    bitacora "$(date +%s)" "fin_presentacion" "" ""
    local wpid; wpid=$(cat "$SDIR/watcher.pid" 2>/dev/null || echo "")
    [ -n "$wpid" ] && kill -TERM "$wpid" 2>/dev/null || true
    local pid; pid=$(cat "$SDIR/pi_agent.pid" 2>/dev/null || echo "")
    [ -n "$pid" ] && ssh_pi "${PI_USER}@${PI_HOST}" "kill -TERM $pid 2>/dev/null || true"
    echo "[end] colector detenido. Bajando resources.csv..."
    scp_pi "${PI_USER}@${PI_HOST}:${RDIR}/resources.csv" "$SDIR/resources.csv" || echo "  (no resources.csv)"
    rm -f "$STATE"
    echo "[end] listo. Archivos en $SDIR"
    ls -la "$SDIR"
    echo "[end] genera la grafica con:  ./presentation.sh plot $SDIR"
}

cmd_plot() {
    local dir="${1:-}"
    if [ -z "$dir" ]; then
        if [ -f "$STATE" ]; then . "$STATE"; dir="$SDIR"; else
            dir=$(ls -dt "$HERE"/sessions/presentacion_* 2>/dev/null | head -1); fi
    fi
    [ -d "$dir" ] || { echo "no encuentro la carpeta de presentacion"; exit 1; }
    # si el monitor sigue activo, baja una copia fresca del resources.csv
    if [ -f "$STATE" ]; then . "$STATE"; scp_pi "${PI_USER}@${PI_HOST}:${RDIR}/resources.csv" "$dir/resources.csv" 2>/dev/null || true; fi
    local py="$HERE/.venv/bin/python"; [ -x "$py" ] || py="python3"
    "$py" "$HERE/plot_presentation.py" "$dir"
}

cmd_report() {
    local dir="${1:-}"
    if [ -z "$dir" ]; then
        if [ -f "$STATE" ]; then . "$STATE"; dir="$SDIR"; else
            dir=$(ls -dt "$HERE"/sessions/presentacion_* 2>/dev/null | head -1); fi
    fi
    [ -d "$dir" ] || { echo "no encuentro la carpeta de presentacion"; exit 1; }
    if [ -f "$STATE" ]; then . "$STATE"; scp_pi "${PI_USER}@${PI_HOST}:${RDIR}/resources.csv" "$dir/resources.csv" 2>/dev/null || true; fi
    local py="$HERE/.venv/bin/python"; [ -x "$py" ] || py="python3"
    "$py" "$HERE/executive_report.py" "$dir" || { echo "fallo generando el informe .md"; exit 1; }
    local md="$dir/informe_ejecutivo.md" pdf="$dir/informe_ejecutivo.pdf"
    if command -v pandoc >/dev/null 2>&1; then
        pandoc "$md" --from=markdown+pipe_tables+raw_tex-implicit_figures --to=pdf --pdf-engine=xelatex \
            --template="$HERE/templates/eisvogel.latex" --resource-path="$dir" \
            --variable title:"Informe ejecutivo de metricas" \
            --variable subtitle:"Tesis CEC-EPN - $(basename "$dir")" \
            --variable author:"Jean Poll Cardoso Chiriboga" \
            --variable date:"$(date '+%Y-%m-%d')" \
            -o "$pdf" && echo "[report] PDF -> $pdf" || echo "[report] pandoc fallo; queda el .md y el PNG"
    else
        echo "[report] pandoc no instalado; queda el .md ($md) y el PNG presentacion_recursos.png"
    fi
}

case "${1:-}" in
    start)    cmd_start ;;
    deploy)   shift; cmd_deploy "$@" ;;
    teardown) shift; cmd_teardown "$@" ;;
    mark)     shift; cmd_mark "$@" ;;
    status)   cmd_status ;;
    end)      cmd_end ;;
    plot)     shift; cmd_plot "$@" ;;
    report)   shift; cmd_report "$@" ;;
    *) echo "uso: $0 {start|deploy <escN>|teardown <escN>|mark \"txt\"|status|end|plot [dir]|report [dir]}"; exit 2 ;;
esac
