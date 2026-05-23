#!/usr/bin/env python3
"""Parche idempotente: imagen del dispositivo por IP en el dashboard D3 (Esc1).

La imagen de cada nodo salia de getLogoURL(osType) usando el OS detectado por
nmap (poco fiable), por eso el Pi (192.168.1.10) y la PC admin (192.168.1.20)
salian con la imagen equivocada. Se agrega un mapeo por IP con prioridad:
  192.168.1.10 -> raspberry.png   (Raspberry Pi servidor)
  192.168.1.20 -> laptop.png      (PC admin)

Uso: python3 fix_esc1_device_images.py /ruta/flows.json
"""
import json, sys, shutil, time

FLOWS = sys.argv[1] if len(sys.argv) > 1 else "/home/jeanpoll/Escritorio/tesis_escenario1/flows.json"
TPL_ID = "d5f7cb97419466c8"

OLD_DEF = "function getLogoURL(osType) {"
NEW_DEF = ('function getLogoURL(osType, ip) {\n'
           '        var byIp = { "192.168.1.10": "/images/raspberry.png", "192.168.1.20": "/images/laptop.png" };\n'
           '        if (ip && byIp[ip]) return byIp[ip];')


def main():
    flows = json.load(open(FLOWS))
    if not isinstance(flows, list):
        sys.exit("flows.json inesperado")
    tpl = next((n for n in flows if n.get("id") == TPL_ID), None)
    if tpl is None:
        sys.exit(f"falta template {TPL_ID}")
    fmt = tpl.get("format", "")
    if "byIp" in fmt:
        print("= imagenes por IP ya parcheadas")
        return
    if OLD_DEF not in fmt or "getLogoURL(d.OS)" not in fmt:
        sys.exit("no se hallaron los anclajes esperados (getLogoURL)")
    fmt = fmt.replace(OLD_DEF, NEW_DEF, 1)
    fmt = fmt.replace("getLogoURL(d.OS)", "getLogoURL(d.OS, d.IP)", 1)
    tpl["format"] = fmt
    bak = f"{FLOWS}.bak.img.{int(time.time())}"
    shutil.copy2(FLOWS, bak)
    json.dump(flows, open(FLOWS, "w"), ensure_ascii=False, indent=1)
    print(f"+ imagenes por IP (10->raspberry, 20->laptop) | backup {bak}")


if __name__ == "__main__":
    main()
