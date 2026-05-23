#!/usr/bin/env python3
"""Parche idempotente: clasificar 200 lentisimo como 'down' (Esc3).

El target es Flask single-thread; bajo flood la sonda /health recibe un 200
muy lento (rt ~15s) en vez de fallar, asi que esc3-fn-health lo etiquetaba
'slow' (amarillo "DEGRADADO") y nunca 'down'. Resultado: el banner del operador
y la pagina movil nunca se ponian rojos ("CAIDO").

Fix: rt >= DOWN_MS con 200 -> 'down'. Mantiene la banda 'slow' (2.5s-8s).

Uso: python3 fix_health_down_classification.py /ruta/flows.json
"""
import json, sys, shutil, time

FLOWS = sys.argv[1] if len(sys.argv) > 1 else "/home/jeanpoll/tesis_escenario3/flows.json"
NID = "esc3-fn-health"
MARK = "// __DOWNFIX__"
DOWN_MS = 8000

NEW_FUNC = f"""var rt = Date.now() - (msg._t0 || Date.now());
var ok = (msg.statusCode === 200);
{MARK} un 200 extremadamente lento = sistema caido, no solo "lento"
var status;
if (!ok) status = 'down';
else if (rt >= {DOWN_MS}) status = 'down';
else if (rt >= 2500) status = 'slow';
else status = 'ok';

flow.set('targetStatus', status);
flow.set('targetRt', rt);

var peak = flow.get('peakRps') || 0;
var cur = flow.get('currentRps') || 0;
if (cur > peak) {{ flow.set('peakRps', cur); }}

var label = status === 'ok' ? '🟢 ONLINE' : status === 'slow' ? '🟡 DEGRADADO' : '🔴 CAÍDO';
var msg1 = {{ payload: label }};
var msg2 = {{ payload: rt > 9999 ? 9999 : rt, topic: 'rt' }};
var msg3 = {{ payload: {{ type: 'health', status: status, responseMs: rt < 9999 ? rt : 9999 }} }};
return [msg1, msg2, msg3];
"""


def main():
    flows = json.load(open(FLOWS))
    if not isinstance(flows, list):
        sys.exit("flows.json inesperado")
    n = next((x for x in flows if x.get("id") == NID), None)
    if n is None:
        sys.exit(f"no se encontro {NID}")
    if MARK in n.get("func", ""):
        print(f"= {NID} ya parcheado")
        return
    n["func"] = NEW_FUNC
    bak = f"{FLOWS}.bak.health.{int(time.time())}"
    shutil.copy2(FLOWS, bak)
    json.dump(flows, open(FLOWS, "w"), ensure_ascii=False, indent=1)
    print(f"+ {NID} parcheado (rt>={DOWN_MS}ms -> down) | backup {bak}")


if __name__ == "__main__":
    main()
