#!/usr/bin/env python3
"""Parche idempotente para Esc3 (bug A.3).

El boton "ATACAR" de la pagina movil (endpoint /api/attack/press -> nodo
esc3-fn-press) solo incrementaba flow.pressCount y no disparaba el flood real.
Este parche hace que, al llegar al 5o press (y si no hay un ataque en curso),
esc3-fn-press dispare el ataque real (POST http://esc3-attacker:5001/start),
re-armable tras detener.

- Anade un nodo http request dedicado `esc3-http-rq-press-start` (sin salida,
  para no gatillar el http response que cuelga del request del operador).
- Convierte esc3-fn-press de 3 a 4 salidas; la 4a dispara el request solo en
  el evento que cruza el umbral.

Idempotente: re-ejecutarlo no duplica nodos ni wires.

Uso:
    python3 add_mobile_attack_trigger.py /home/jeanpoll/tesis_escenario3/flows.json
"""
import json, sys, shutil, time

FLOWS = sys.argv[1] if len(sys.argv) > 1 else "/home/jeanpoll/tesis_escenario3/flows.json"
PRESS_ID = "esc3-fn-press"
NEW_REQ_ID = "esc3-http-rq-press-start"
MARK = "// __PRESSFIRE__"
THRESHOLD = 5

FIRE_BLOCK = f"""
{MARK}
var fire = null;
if (!flow.get('attacking') && count >= {THRESHOLD}) {{
    flow.set('attacking', true);
    flow.set('protection', false);
    flow.set('attackStart', Date.now());
    fire = {{ payload: {{}} }};   // dispara POST /start en el attacker (re-armable tras stop)
}}
return [msg, msgViz, msgUi, fire];
"""


def main():
    flows = json.load(open(FLOWS))
    if not isinstance(flows, list):
        sys.exit("flows.json no es una lista de nodos (formato inesperado)")

    by_id = {n.get("id"): n for n in flows}
    press = by_id.get(PRESS_ID)
    if press is None:
        sys.exit(f"no se encontro el nodo {PRESS_ID}")

    changed = False

    # 1) Nodo http request dedicado para el trigger movil (sin downstream).
    if NEW_REQ_ID not in by_id:
        flows.append({
            "id": NEW_REQ_ID,
            "type": "http request",
            "z": press.get("z", "esc3-tab"),
            "name": "Attacker /start (movil)",
            "method": "POST",
            "ret": "txt",
            "paytoqs": "ignore",
            "url": "http://esc3-attacker:5001/start",
            "tls": "",
            "persist": False,
            "proxy": "",
            "authType": "",
            "x": 560,
            "y": 620,
            "wires": [[]],
        })
        changed = True
        print(f"+ nodo {NEW_REQ_ID} anadido")
    else:
        print(f"= nodo {NEW_REQ_ID} ya existe")

    # 2) Funcion esc3-fn-press: 4 salidas + bloque fire (idempotente por marcador).
    func = press.get("func", "")
    if MARK in func:
        print(f"= {PRESS_ID}.func ya parcheado")
    else:
        # quita el return original "return [msg, msgViz, msgUi];" y anade el bloque
        stripped = func.replace("return [msg, msgViz, msgUi];", "").rstrip()
        press["func"] = stripped + "\n" + FIRE_BLOCK.lstrip("\n")
        press["outputs"] = 4
        changed = True
        print(f"+ {PRESS_ID}.func parcheado (outputs=4)")

    # asegura outputs=4 aunque el func ya estuviera marcado
    if press.get("outputs") != 4:
        press["outputs"] = 4
        changed = True

    # 3) Wire de la 4a salida -> nodo request dedicado.
    wires = press.setdefault("wires", [])
    while len(wires) < 4:
        wires.append([])
    if NEW_REQ_ID not in wires[3]:
        wires[3].append(NEW_REQ_ID)
        changed = True
        print(f"+ wire {PRESS_ID}[3] -> {NEW_REQ_ID}")
    else:
        print(f"= wire {PRESS_ID}[3] -> {NEW_REQ_ID} ya existe")

    if not changed:
        print("sin cambios (ya estaba parcheado)")
        return

    bak = f"{FLOWS}.bak.{int(time.time())}"
    shutil.copy2(FLOWS, bak)
    print(f"backup: {bak}")
    json.dump(flows, open(FLOWS, "w"), ensure_ascii=False, indent=1)
    print(f"escrito: {FLOWS}")


if __name__ == "__main__":
    main()
