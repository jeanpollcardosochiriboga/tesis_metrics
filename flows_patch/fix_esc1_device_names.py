#!/usr/bin/env python3
"""Parche idempotente: corregir nombres/OS invertidos de Pi y PC (Esc1).

Bug: el bloque por IP en la funcion de parseo nmap (8b10b8cf29c8b481) usaba
MY_PC_IP (la PC admin, .20) para etiquetarla como "Raspberry Pi (Admin)", y no
contemplaba la IP real del Pi (DASH_IP, .10), que caia en "Dispositivo
Desconocido". Quedaban cruzados.

Fix:
  192.168.1.10 (DASH_IP)  -> "Raspberry Pi (Servidor)" + os RaspberryPi
  192.168.1.20 (MY_PC_IP) -> "PC Admin (Laptop)"        + os Windows/Linux

Uso: python3 fix_esc1_device_names.py /ruta/flows.json
"""
import json, sys, shutil, time

FLOWS = sys.argv[1] if len(sys.argv) > 1 else "/home/jeanpoll/Escritorio/tesis_escenario1/flows.json"
FN_ID = "8b10b8cf29c8b481"

REPLACEMENTS = [
    # 1) declarar PI_IP junto a MY_PC_IP
    ('const MY_PC_IP = env.get(\'MY_PC_IP\') || "192.168.1.218";',
     'const MY_PC_IP = env.get(\'MY_PC_IP\') || "192.168.1.218";\nconst PI_IP = env.get(\'DASH_IP\') || "192.168.1.10";'),
    # 2) la primera rama ahora es para el Pi
    ('if (ip === MY_PC_IP) {', 'if (ip === PI_IP) {'),
    ('name = "Raspberry Pi (Admin)";', 'name = "Raspberry Pi (Servidor)";'),
    # 3) la segunda rama ahora es para la PC admin por IP
    ('} else if (nameLower.includes("jeanpoll") || nameLower.includes("asus")) {',
     '} else if (ip === MY_PC_IP) {'),
    ('name = "jeanpoll-ASUS (Laptop)";', 'name = "PC Admin (Laptop)";'),
]


def main():
    flows = json.load(open(FLOWS))
    if not isinstance(flows, list):
        sys.exit("flows.json inesperado")
    fn = next((n for n in flows if n.get("id") == FN_ID), None)
    if fn is None:
        sys.exit(f"falta funcion {FN_ID}")
    f = fn.get("func", "")
    if "PI_IP" in f:
        print("= nombres Pi/PC ya corregidos")
        return
    for old, new in REPLACEMENTS:
        if old not in f:
            sys.exit(f"anclaje no encontrado: {old!r}")
        f = f.replace(old, new, 1)
    fn["func"] = f
    bak = f"{FLOWS}.bak.names.{int(time.time())}"
    shutil.copy2(FLOWS, bak)
    json.dump(flows, open(FLOWS, "w"), ensure_ascii=False, indent=1)
    print(f"+ nombres corregidos (.10->Raspberry Pi, .20->PC Admin) | backup {bak}")


if __name__ == "__main__":
    main()
