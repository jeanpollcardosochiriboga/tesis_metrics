#!/usr/bin/env python3
"""Parche idempotente: detectar 'down' cuando la sonda /health falla/timeoutea (Esc3).

Bajo flood, /health del target single-thread se cuelga; el nodo http request
interno (esc3-http-rq-health) DA ERROR y no llama a esc3-fn-health, asi que el
estado se quedaba pegado en 'ok' y nunca pasaba a 'down' (banner/celulares no se
ponian rojos).

Fix:
  1) esc3-fn-pre-health: msg.requestTimeout = TIMEOUT_MS (la sonda falla rapido).
  2) Catch node (scope = esc3-http-rq-health) -> funcion que fija targetStatus
     'down' y lo emite a los 3 destinos de UI (texto, stats, viz+iframe), igual
     que la rama OK de esc3-fn-health.

Uso: python3 add_health_timeout_catch.py /ruta/flows.json
"""
import json, sys, shutil, time

FLOWS = sys.argv[1] if len(sys.argv) > 1 else "/home/jeanpoll/tesis_escenario3/flows.json"
TIMEOUT_MS = 2500
CATCH_ID = "esc3-catch-health"
DOWN_FN_ID = "esc3-fn-health-down"
RQ_ID = "esc3-http-rq-health"
PRE_ID = "esc3-fn-pre-health"
TO_MARK = "// __HTIMEOUT__"

DOWN_FN = """flow.set('targetStatus', 'down');
flow.set('targetRt', 9999);
var msg1 = { payload: '🔴 CAÍDO' };
var msg2 = { payload: 9999, topic: 'rt' };
var msg3 = { payload: { type: 'health', status: 'down', responseMs: 9999 } };
return [msg1, msg2, msg3];
"""


def main():
    flows = json.load(open(FLOWS))
    if not isinstance(flows, list):
        sys.exit("flows.json inesperado")
    by_id = {n.get("id"): n for n in flows}

    rq = by_id.get(RQ_ID) or sys.exit(f"falta {RQ_ID}")
    pre = by_id.get(PRE_ID) or sys.exit(f"falta {PRE_ID}")
    z = rq.get("z", "esc3-tab")
    changed = False

    # 1) timeout en la sonda
    f = pre.get("func", "")
    if TO_MARK not in f:
        pre["func"] = f"{TO_MARK}\nmsg.requestTimeout = {TIMEOUT_MS};\n" + f
        changed = True
        print(f"+ {PRE_ID}: requestTimeout={TIMEOUT_MS}ms")
    else:
        print(f"= {PRE_ID} ya tiene timeout")
    # tambien en la propiedad del nodo http request (best-effort)
    if str(rq.get("timeout", "")) != str(TIMEOUT_MS):
        rq["timeout"] = TIMEOUT_MS
        changed = True

    # 2) funcion 'down'
    if DOWN_FN_ID not in by_id:
        flows.append({
            "id": DOWN_FN_ID, "type": "function", "z": z,
            "name": "Salud caida (timeout)", "func": DOWN_FN,
            "outputs": 3, "noerr": 0, "initialize": "", "finalize": "", "libs": [],
            "x": 1500, "y": 360,
            "wires": [["esc3-txt-status"], ["esc3-tmpl-stats-full"],
                      ["esc3-tmpl-viz", "esc3-tmpl-iframe"]],
        })
        changed = True
        print(f"+ funcion {DOWN_FN_ID}")
    else:
        print(f"= funcion {DOWN_FN_ID} ya existe")

    # 3) catch node
    if CATCH_ID not in by_id:
        flows.append({
            "id": CATCH_ID, "type": "catch", "z": z, "name": "Catch /health",
            "scope": [RQ_ID], "uncaught": False,
            "x": 1300, "y": 360, "wires": [[DOWN_FN_ID]],
        })
        changed = True
        print(f"+ catch {CATCH_ID} (scope {RQ_ID})")
    else:
        print(f"= catch {CATCH_ID} ya existe")

    if not changed:
        print("sin cambios")
        return
    bak = f"{FLOWS}.bak.htcatch.{int(time.time())}"
    shutil.copy2(FLOWS, bak)
    json.dump(flows, open(FLOWS, "w"), ensure_ascii=False, indent=1)
    print(f"escrito {FLOWS} | backup {bak}")


if __name__ == "__main__":
    main()
