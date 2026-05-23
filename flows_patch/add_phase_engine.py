#!/usr/bin/env python3
"""Motor de fases por #presses + permanencia minima (Esc3).

Escalada visible en 3 fases, controlada por la cantidad de presses del publico:
  - verde  (OK)         : 0-7 presses
  - amarillo (DEGRADADO): 8-14 presses
  - rojo   (CAIDO)      : >=15 presses
Cada fase permanece un minimo de DWELL_MS antes de avanzar, aunque el publico
presione muy rapido (asi se aprecian las tres). El flood REAL se dispara al
entrar en rojo y se detiene al recuperarse; el probe externo sigue midiendo el
colapso real para la tesis.

Cambios (idempotentes):
  - esc3-fn-phase + esc3-inject-phase (timer 1s): unica autoridad del estado
    mostrado (banner operador + celulares via flow.targetStatus) y del flood.
  - esc3-http-rq-phase-stop: POST /stop al recuperarse.
  - esc3-fn-press: vuelve a 3 salidas (solo cuenta; ya no dispara el flood).
  - esc3-fn-health: deja de fijar el estado; solo mide rt para stats.
  - esc3-fn-health-down (catch): no-op.
  - esc3-tmpl-viz: banner desacoplado de st.running + clase amarilla b-slow.

Uso: python3 add_phase_engine.py /ruta/flows.json
"""
import json, sys, shutil, time

FLOWS = sys.argv[1] if len(sys.argv) > 1 else "/home/jeanpoll/tesis_escenario3/flows.json"
DWELL_MS = 8000
TH_SLOW = 8
TH_DOWN = 15

PHASE_FUNC = f"""var count = flow.get('pressCount') || 0;
var now = Date.now();
var order = {{ ok: 0, slow: 1, down: 2 }};
var name  = ['ok', 'slow', 'down'];
var phase = flow.get('phase') || 'ok';
var enteredAt = flow.get('phaseEnteredAt') || now;
var DWELL = {DWELL_MS};

var desired = count >= {TH_DOWN} ? 'down' : count >= {TH_SLOW} ? 'slow' : 'ok';
var prev = phase;

if (order[desired] > order[phase]) {{
    // subir de a una grada, respetando permanencia minima
    if (now - enteredAt >= DWELL) {{
        phase = name[order[phase] + 1];
        enteredAt = now;
    }}
}} else if (order[desired] < order[phase]) {{
    // recuperacion inmediata (stop / reset)
    phase = desired;
    enteredAt = now;
}}

flow.set('phase', phase);
flow.set('phaseEnteredAt', enteredAt);
flow.set('targetStatus', phase);

var label = phase === 'down' ? '🔴 CAÍDO' : phase === 'slow' ? '🟡 DEGRADADO' : '🟢 ONLINE';
var mLabel  = {{ payload: label }};
var rtFake  = phase === 'down' ? 9999 : phase === 'slow' ? 3000 : 20;
flow.set('targetRt', rtFake);
var mHealth = {{ payload: {{ type: 'health', status: phase, responseMs: rtFake }} }};

// flood real: asegurar encendido en rojo, apagar al salir
var mStart = null, mStop = null;
if (phase === 'down') {{
    if (!flow.get('attacking')) {{
        flow.set('attacking', true);
        flow.set('attackStart', now);
        mStart = {{ payload: {{}} }};
    }}
}} else if (prev === 'down') {{
    flow.set('attacking', false);
    mStop = {{ payload: {{}} }};
}}
return [mLabel, mHealth, mStart, mStop];
"""

HEALTH_FUNC = """// __PHASEMODE__ : la fase la decide esc3-fn-phase; aqui solo medimos rt
var rt = Date.now() - (msg._t0 || Date.now());
flow.set('lastProbeRt', rt);
return [null, { payload: rt > 9999 ? 9999 : rt, topic: 'rt' }, null];
"""

DOWN_FN_NOOP = """// __PHASEMODE__ : estado lo maneja esc3-fn-phase; catch sin efecto en UI
return null;
"""


def main():
    flows = json.load(open(FLOWS))
    if not isinstance(flows, list):
        sys.exit("flows.json inesperado")
    by_id = {n.get("id"): n for n in flows}
    changed = False

    def need(i):
        n = by_id.get(i)
        if n is None:
            sys.exit(f"falta nodo {i}")
        return n

    press = need("esc3-fn-press")
    health = need("esc3-fn-health")
    viz = need("esc3-tmpl-viz")
    z = press.get("z", "esc3-tab")

    # 1) esc3-fn-press -> 3 salidas, solo cuenta (revertir disparo del 5o press)
    if "__PRESSFIRE__" in press.get("func", ""):
        f = press["func"]
        f = f[: f.index("// __PRESSFIRE__")].rstrip()
        press["func"] = f + "\nreturn [msg, msgViz, msgUi];\n"
        press["outputs"] = 3
        press["wires"] = press.get("wires", [])[:3]
        changed = True
        print("+ esc3-fn-press revertido a 3 salidas (solo cuenta)")
    else:
        print("= esc3-fn-press ya en modo conteo")

    # 2) esc3-fn-health -> solo rt
    if "__PHASEMODE__" not in health.get("func", ""):
        health["func"] = HEALTH_FUNC
        changed = True
        print("+ esc3-fn-health: solo mide rt")
    else:
        print("= esc3-fn-health ya en modo fase")

    # 3) catch down-fn no-op (si existe)
    dn = by_id.get("esc3-fn-health-down")
    if dn is not None and "__PHASEMODE__" not in dn.get("func", ""):
        dn["func"] = DOWN_FN_NOOP
        changed = True
        print("+ esc3-fn-health-down: no-op")

    # 4) http request /stop para recuperacion
    if "esc3-http-rq-phase-stop" not in by_id:
        flows.append({
            "id": "esc3-http-rq-phase-stop", "type": "http request", "z": z,
            "name": "Attacker /stop (fase)", "method": "POST", "ret": "txt",
            "paytoqs": "ignore", "url": "http://esc3-attacker:5001/stop",
            "tls": "", "persist": False, "proxy": "", "authType": "",
            "x": 560, "y": 700, "wires": [[]],
        })
        changed = True
        print("+ esc3-http-rq-phase-stop")

    # 5) motor de fases
    if "esc3-fn-phase" not in by_id:
        flows.append({
            "id": "esc3-fn-phase", "type": "function", "z": z,
            "name": "Motor de fases", "func": PHASE_FUNC, "outputs": 4,
            "noerr": 0, "initialize": "", "finalize": "", "libs": [],
            "x": 360, "y": 760,
            "wires": [["esc3-txt-status"],
                      ["esc3-tmpl-viz", "esc3-tmpl-iframe"],
                      ["esc3-http-rq-press-start"],
                      ["esc3-http-rq-phase-stop"]],
        })
        changed = True
        print("+ esc3-fn-phase (motor)")
    else:
        # mantener la logica al dia
        by_id["esc3-fn-phase"]["func"] = PHASE_FUNC
        print("= esc3-fn-phase ya existe (func actualizada)")
        changed = True

    # 6) timer 1s
    if "esc3-inject-phase" not in by_id:
        flows.append({
            "id": "esc3-inject-phase", "type": "inject", "z": z,
            "name": "tick fase 1s", "props": [{"p": "payload"}],
            "repeat": "1", "crontab": "", "once": True, "onceDelay": 1,
            "topic": "", "payload": "", "payloadType": "date",
            "x": 150, "y": 760, "wires": [["esc3-fn-phase"]],
        })
        changed = True
        print("+ esc3-inject-phase (1s)")

    # 7) banner viz: desacoplar de st.running + clase amarilla + recovered
    fmt = viz["format"]
    orig = fmt
    if "b-slow" not in fmt:
        fmt = fmt.replace(
            ".dv-banner.b-protected",
            ".dv-banner.b-slow      { background: linear-gradient(90deg, #eab308, #ca8a04); color: #111; animation: bn-pulse 1.4s ease-in-out infinite; }\n      .dv-banner.b-protected",
            1,
        )
    fmt = fmt.replace("st.running && st.health === 'down'", "st.health === 'down'")
    fmt = fmt.replace("st.running && st.health === 'slow'", "st.health === 'slow'")
    fmt = fmt.replace("!st.running && (Date.now() - st.recoveredAt) < 4000",
                      "(Date.now() - st.recoveredAt) < 4000")
    fmt = fmt.replace("setBanner('down', '🟡 SISTEMA DEGRADADO · ATAQUE EN CURSO')",
                      "setBanner('slow', '🟡 SISTEMA DEGRADADO · BAJO PRESIÓN')")
    fmt = fmt.replace(
        "st.health = p.status; st.rt = p.responseMs;",
        "var _ph = st.health; st.health = p.status; st.rt = p.responseMs; if (_ph !== 'ok' && st.health === 'ok') st.recoveredAt = Date.now();",
        1,
    )
    if fmt != orig:
        viz["format"] = fmt
        changed = True
        print("+ esc3-tmpl-viz: banner desacoplado + b-slow")
    else:
        print("= esc3-tmpl-viz ya parcheado")

    if not changed:
        print("sin cambios")
        return
    bak = f"{FLOWS}.bak.phase.{int(time.time())}"
    shutil.copy2(FLOWS, bak)
    json.dump(flows, open(FLOWS, "w"), ensure_ascii=False, indent=1)
    print(f"escrito {FLOWS} | backup {bak}")


if __name__ == "__main__":
    main()
