#!/usr/bin/env python3
"""Generates ops-console/data/flows.json. Run after editing this file.

The flows expose:
  - 'Demo' tab: 3 big START buttons (Esc1/2/3) + 1 PANIC stop + status
  - 'Avanzado' tab: per-scenario UP/DOWN/RESTART/LOGS + status refresh
All actions SSH from the container to the Pi using the mounted ed25519 key.
"""
from __future__ import annotations
import json
from pathlib import Path

PI = "raspberry1@192.168.1.10"
KEY = "/usr/src/node-red/.ssh/id_ed25519"
SSH = f"ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=8 -i {KEY} {PI}"
COMPOSE = {
    "esc1": "/home/raspberry1/tesis_escenario1/docker-compose.yml",
    "esc2": "/home/raspberry1/tesis_escenario2/docker-compose.yml",
    "esc3": "/home/raspberry1/tesis_escenario3/docker-compose.yml",
}


def start_only(scenario: str) -> str:
    other = [s for s in COMPOSE if s != scenario]
    parts = [f"docker compose -f {COMPOSE[s]} down" for s in other]
    parts.append(f"docker compose -f {COMPOSE[scenario]} up -d")
    parts.append("sleep 2; docker ps --format '{{.Names}}'")
    return f"{SSH} \"" + " ; ".join(parts) + "\""


def stop_all() -> str:
    parts = [f"docker compose -f {COMPOSE[s]} down" for s in COMPOSE]
    parts.append("docker ps --format '{{.Names}}'")
    return f"{SSH} \"" + " ; ".join(parts) + "\""


def up(scenario: str) -> str:
    return f"{SSH} \"docker compose -f {COMPOSE[scenario]} up -d ; docker ps --format '{{{{.Names}}}}'\""


def down(scenario: str) -> str:
    return f"{SSH} \"docker compose -f {COMPOSE[scenario]} down ; docker ps --format '{{{{.Names}}}}'\""


def restart(scenario: str) -> str:
    return f"{SSH} \"docker compose -f {COMPOSE[scenario]} restart ; docker ps --format '{{{{.Names}}}}'\""


def logs(scenario: str, container: str) -> str:
    return f"{SSH} \"docker logs --tail 40 {container} 2>&1\""


def status() -> str:
    return f"{SSH} \"docker ps --format '{{{{.Names}}}}: {{{{.Status}}}}'\""


# Node templates ------------------------------------------------------------

def tab(node_id, label, order):
    return {"id": node_id, "type": "tab", "label": label, "disabled": False,
            "info": "", "env": []}


def ui_base():
    # Minimal ui_base — Node-RED dashboard fills in defaults for unset keys.
    return {
        "id": "ui_base",
        "type": "ui_base",
        "theme": {
            "name": "theme-light",
            "lightTheme": {"default": "#0094CE", "baseColor": "#0094CE",
                           "baseFont": "-apple-system,BlinkMacSystemFont,Segoe UI,Roboto",
                           "edited": False, "reset": False},
            "darkTheme": {"default": "#097479", "baseColor": "#097479",
                          "baseFont": "-apple-system,BlinkMacSystemFont,Segoe UI,Roboto",
                          "edited": False, "reset": False},
            "customTheme": {"name": "Custom", "default": "#4B7930",
                            "baseColor": "#4B7930",
                            "baseFont": "-apple-system,BlinkMacSystemFont,Segoe UI,Roboto"},
            "themeState": {},
            "angularTheme": {"primary": "indigo", "accents": "blue", "warn": "red",
                             "background": "grey", "palette": "light"}
        },
        "site": {"name": "Tesis Operator", "hideToolbar": "false",
                 "allowSwipe": "false", "lockMenu": "false",
                 "allowTempTheme": "true", "dateFormat": "DD/MM/YYYY",
                 "sizes": {"sx": 48, "sy": 48, "gx": 6, "gy": 6, "cx": 6, "cy": 6, "px": 0, "py": 0}}
    }


def ui_tab(node_id, name, order, icon="dashboard"):
    return {"id": node_id, "type": "ui_tab", "name": name, "icon": icon,
            "order": order, "disabled": False, "hidden": False}


def ui_group(node_id, name, tab_id, order, width=12):
    return {"id": node_id, "type": "ui_group", "name": name, "tab": tab_id,
            "order": order, "disp": True, "width": str(width),
            "collapse": False, "className": ""}


def ui_button(node_id, group, label, color, bgcolor, payload, order=1, width=4, height=2):
    # Each button is wired to its own dedicated exec node (id = btn_id + '_exec').
    # That exec node has the shell command baked in at flow-load time, which avoids
    # the shell-quoting traps of trying to pass commands through msg.payload.
    return {
        "id": node_id, "type": "ui_button", "z": "demo_tab", "name": label,
        "group": group, "order": order, "width": str(width), "height": str(height),
        "passthru": False, "label": label, "tooltip": "",
        "color": color, "bgcolor": bgcolor, "className": "",
        "icon": "", "payload": "", "payloadType": "str",
        "topic": label, "topicType": "str",
        "wires": [[f"{node_id}_exec"]]
    }


def button_exec_node(node_id, name, cmd):
    return {
        "id": f"{node_id}_exec", "type": "exec", "z": "demo_tab",
        "name": name, "command": cmd, "addpay": "", "append": "",
        "useSpawn": "false", "timer": "30", "winHide": False, "oldrc": False,
        "wires": [["fmt_out", "fmt_status"], [], []]
    }


def ui_template(node_id, group, name, content, format_html, order=1, width=12, height=4):
    return {
        "id": node_id, "type": "ui_template", "z": "demo_tab",
        "group": group, "name": name, "order": order,
        "width": str(width), "height": str(height),
        "format": format_html, "storeOutMessages": False,
        "fwdInMessages": True, "resendOnRefresh": True,
        "templateScope": "local", "className": "", "wires": [[]]
    }


def exec_node(node_id, name, cmd, wires_stdout):
    return {
        "id": node_id, "type": "exec", "z": "demo_tab", "name": name,
        "command": cmd, "addpay": "", "append": "",
        "useSpawn": "false", "timer": "20", "winHide": False, "oldrc": False,
        "wires": [wires_stdout, [], []]
    }


def function_node(node_id, name, func, wires):
    return {
        "id": node_id, "type": "function", "z": "demo_tab", "name": name,
        "func": func, "outputs": 1, "noerr": 0, "initialize": "", "finalize": "",
        "libs": [], "wires": [wires]
    }


# Build the flow ----------------------------------------------------------

def build():
    nodes = []

    # tabs (admin tabs)
    nodes.append(tab("demo_tab", "Demo (wizard)", 1))
    nodes.append(tab("adv_tab",  "Avanzado",      2))

    # ui_tabs + ui_groups (ui_base is auto-created by node-red-dashboard on
    # first run; including it here triggers a circular-dep error in v3.6.6).
    nodes.append(ui_tab("ui_demo", "Demo", 1, icon="play_arrow"))
    nodes.append(ui_tab("ui_adv",  "Avanzado", 2, icon="settings"))

    nodes.append(ui_group("g_demo_btns",   "Iniciar / Detener demo", "ui_demo", 1, width=12))
    nodes.append(ui_group("g_demo_status", "Estado del Pi",           "ui_demo", 2, width=12))
    nodes.append(ui_group("g_demo_out",    "Último comando",     "ui_demo", 3, width=12))

    nodes.append(ui_group("g_adv_e1",     "Escenario 1",              "ui_adv", 1, width=6))
    nodes.append(ui_group("g_adv_e2",     "Escenario 2",              "ui_adv", 2, width=6))
    nodes.append(ui_group("g_adv_e3",     "Escenario 3",              "ui_adv", 3, width=6))
    nodes.append(ui_group("g_adv_status", "Estado",                   "ui_adv", 4, width=6))
    nodes.append(ui_group("g_adv_out",    "Último comando",      "ui_adv", 5, width=12))

    # Format output into both ui_text widgets
    nodes.append({
        "id": "fmt_out", "type": "function", "z": "demo_tab",
        "name": "format last-output",
        "func": (
            "const txt = (msg.payload || '').toString().trim() || '(sin salida)';\n"
            "const ts  = new Date().toLocaleTimeString();\n"
            "return { payload: `[${ts}]\\n${txt}` };\n"
        ),
        "outputs": 1, "noerr": 0, "initialize": "", "finalize": "", "libs": [],
        "wires": [["txt_demo_out", "txt_adv_out"]]
    })

    nodes.append({
        "id": "fmt_status", "type": "function", "z": "demo_tab",
        "name": "extract running scenario",
        "func": (
            "const out = (msg.payload || '').toString();\n"
            "const lines = out.split(/\\n/).map(s => s.trim()).filter(Boolean);\n"
            "let scn = '(ninguno)';\n"
            "if (lines.some(l => l.startsWith('esc1-'))) scn = 'esc1';\n"
            "else if (lines.some(l => l.startsWith('esc2-') || l.startsWith('jp-esc2-'))) scn = 'esc2';\n"
            "else if (lines.some(l => l.startsWith('esc3-'))) scn = 'esc3';\n"
            "const ts = new Date().toLocaleTimeString();\n"
            "return { payload: `${ts}  \\u2022  escenario activo: ${scn}\\n${lines.join('\\n')}` };\n"
        ),
        "outputs": 1, "noerr": 0, "initialize": "", "finalize": "", "libs": [],
        "wires": [["txt_demo_status", "txt_adv_status"]]
    })

    # Status & output panels
    nodes.append({
        "id": "txt_demo_status", "type": "ui_text", "z": "demo_tab",
        "group": "g_demo_status", "order": 1, "width": "12", "height": "4",
        "name": "demo status", "label": "", "format": "<pre style='white-space:pre-wrap;margin:0'>{{msg.payload}}</pre>",
        "layout": "row-spread", "className": ""
    })
    nodes.append({
        "id": "txt_demo_out", "type": "ui_text", "z": "demo_tab",
        "group": "g_demo_out", "order": 1, "width": "12", "height": "6",
        "name": "demo out", "label": "", "format": "<pre style='white-space:pre-wrap;margin:0;font-size:11px'>{{msg.payload}}</pre>",
        "layout": "row-spread", "className": ""
    })
    nodes.append({
        "id": "txt_adv_status", "type": "ui_text", "z": "demo_tab",
        "group": "g_adv_status", "order": 1, "width": "6", "height": "4",
        "name": "adv status", "label": "", "format": "<pre style='white-space:pre-wrap;margin:0'>{{msg.payload}}</pre>",
        "layout": "row-spread", "className": ""
    })
    nodes.append({
        "id": "txt_adv_out", "type": "ui_text", "z": "demo_tab",
        "group": "g_adv_out", "order": 1, "width": "12", "height": "6",
        "name": "adv out", "label": "", "format": "<pre style='white-space:pre-wrap;margin:0;font-size:11px'>{{msg.payload}}</pre>",
        "layout": "row-spread", "className": ""
    })

    def add_button(node_id, group, label, color, bgcolor, cmd, order, w, h):
        nodes.append(ui_button(node_id, group, label, color, bgcolor, "",
                               order=order, width=w, height=h))
        nodes.append(button_exec_node(node_id, label, cmd))

    # ---- Demo tab buttons ----
    add_button("btn_demo_e1",    "g_demo_btns", "INICIAR DEMO ESC1",   "#fff", "#1e88e5", start_only("esc1"), 1, 4, 3)
    add_button("btn_demo_e2",    "g_demo_btns", "INICIAR DEMO ESC2",   "#fff", "#1e88e5", start_only("esc2"), 2, 4, 3)
    add_button("btn_demo_e3",    "g_demo_btns", "INICIAR DEMO ESC3",   "#fff", "#1e88e5", start_only("esc3"), 3, 4, 3)
    add_button("btn_demo_panic", "g_demo_btns", "PANIC: APAGAR TODO",  "#fff", "#cc2222", stop_all(),         4, 12, 2)
    add_button("btn_demo_status","g_demo_btns", "Refrescar estado",    "#fff", "#666666", status(),           5, 12, 1)

    # ---- Avanzado tab buttons ----
    for scn in ("esc1", "esc2", "esc3"):
        g = {"esc1": "g_adv_e1", "esc2": "g_adv_e2", "esc3": "g_adv_e3"}[scn]
        log_ct = {"esc1": "esc1-nodered", "esc2": "jp-esc2-nodered", "esc3": "esc3-nodered"}[scn]
        add_button(f"btn_adv_{scn}_up",    g, f"UP {scn}",      "#fff", "#2e7d32", up(scn),     1, 3, 1)
        add_button(f"btn_adv_{scn}_down",  g, f"DOWN {scn}",    "#fff", "#c62828", down(scn),   2, 3, 1)
        add_button(f"btn_adv_{scn}_rstrt", g, f"RESTART {scn}", "#fff", "#f9a825", restart(scn),3, 3, 1)
        add_button(f"btn_adv_{scn}_logs",  g, f"LOGS {scn}",    "#fff", "#1565c0", logs(scn, log_ct), 4, 3, 1)

    add_button("btn_adv_status", "g_adv_status", "Refrescar docker ps", "#fff", "#666", status(), 1, 6, 1)

    return nodes


if __name__ == "__main__":
    flows = build()
    out = Path(__file__).parent / "data" / "flows.json"
    out.write_text(json.dumps(flows, indent=4, ensure_ascii=False))
    print(f"wrote {out} ({len(flows)} nodes)")
