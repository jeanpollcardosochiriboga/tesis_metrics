#!/usr/bin/env python3
"""Idempotent patcher: adds GET /api/export_state to each scenario's flows.json.

Esc3 also gets a 5-second snapshot accumulator (inject + function) that pushes
the current attack stats into global.esc3_snapshots so /api/export_state can
return a time series instead of just the current value.

Usage:  python3 add_export_state.py <scenario_dir> <scenario_name>

scenario_name ∈ {esc1, esc2, esc3}
"""
from __future__ import annotations
import json, sys, os, shutil
from pathlib import Path

SPECS = {
    "esc1": {
        "tab_id": "3224d6c38c360858",
        "node_prefix": "exportstate_e1",
        "func_body": """
const audit = global.get('audit_users') || [];
msg.payload = { ts: Date.now()/1000, scenario: 'esc1', tables: { auditoria_usuarios: audit } };
msg.headers = { 'Content-Type': 'application/json' };
return msg;
""".strip(),
    },
    "esc2": {
        "tab_id": "tab-esc2",
        "node_prefix": "exportstate_e2",
        "func_body": """
const reservations = flow.get('reservations') || [];
const clicks = flow.get('clicks') || [];
// Split reservations into capturas (email submitted) and envios (email actually sent).
const capturas = reservations.map(r => ({ ts: r.ts, email: r.email, source: r.source || 'web' }));
const envios = reservations.filter(r => r.sent).map(r => ({ ts: r.sentTs || r.ts, email: r.email, status: r.sentStatus || 'ok' }));
msg.payload = { ts: Date.now()/1000, scenario: 'esc2', tables: { email_capturas: capturas, email_envios: envios, email_clicks: clicks } };
msg.headers = { 'Content-Type': 'application/json' };
return msg;
""".strip(),
    },
    "esc3": {
        "tab_id": "esc3-tab",
        "node_prefix": "exportstate_e3",
        "func_body": """
const snaps = global.get('esc3_snapshots') || [];
msg.payload = { ts: Date.now()/1000, scenario: 'esc3', tables: { esc3_stats_snapshot: snaps } };
msg.headers = { 'Content-Type': 'application/json' };
return msg;
""".strip(),
        # Esc3 also needs a snapshot accumulator
        "extra_nodes": [
            {
                "id": "exportstate_e3_snap_inject",
                "type": "inject",
                "z": "esc3-tab",
                "name": "snap 5s",
                "props": [{"p": "payload"}],
                "repeat": "5",
                "crontab": "",
                "once": True,
                "onceDelay": "5",
                "topic": "",
                "payload": "",
                "payloadType": "date",
                "x": 140, "y": 1100,
                "wires": [["exportstate_e3_snap_fn"]],
            },
            {
                "id": "exportstate_e3_snap_fn",
                "type": "function",
                "z": "esc3-tab",
                "name": "push snapshot",
                "func": (
                    "const snaps = global.get('esc3_snapshots') || [];\n"
                    "const dev = flow.get('devices');\n"
                    "// flow.devices is a dict keyed by ip|alias — count its size, not the object.\n"
                    "const devCount = (dev && typeof dev === 'object') ? Object.keys(dev).length : (dev || 0);\n"
                    "snaps.push({\n"
                    "  ts: Date.now()/1000,\n"
                    "  attacking: flow.get('attacking') || false,\n"
                    "  protection: flow.get('protection') || false,\n"
                    "  devices: devCount,\n"
                    "  pressCount: flow.get('pressCount') || 0,\n"
                    "  currentRps: flow.get('currentRps') || 0,\n"
                    "  peakRps: flow.get('peakRps') || 0,\n"
                    "  targetStatus: flow.get('targetStatus') || null,\n"
                    "  targetRt: flow.get('targetRt') || null\n"
                    "});\n"
                    "global.set('esc3_snapshots', snaps);\n"
                    "return null;\n"
                ),
                "outputs": 0,
                "noerr": 0,
                "initialize": "",
                "finalize": "",
                "libs": [],
                "x": 340, "y": 1100,
                "wires": [],
            },
        ],
    },
}


def make_nodes(spec: dict) -> list[dict]:
    p = spec["node_prefix"]
    tab = spec["tab_id"]
    return [
        {
            "id": f"{p}_in",
            "type": "http in",
            "z": tab,
            "name": "GET /api/export_state",
            "url": "/api/export_state",
            "method": "get",
            "upload": False,
            "swaggerDoc": "",
            "x": 160, "y": 1180,
            "wires": [[f"{p}_fn"]],
        },
        {
            "id": f"{p}_fn",
            "type": "function",
            "z": tab,
            "name": "build export payload",
            "func": spec["func_body"],
            "outputs": 1,
            "noerr": 0,
            "initialize": "",
            "finalize": "",
            "libs": [],
            "x": 400, "y": 1180,
            "wires": [[f"{p}_out"]],
        },
        {
            "id": f"{p}_out",
            "type": "http response",
            "z": tab,
            "name": "respond 200",
            "statusCode": "200",
            "headers": {},
            "x": 640, "y": 1180,
            "wires": [],
        },
    ]


def patch(flows_path: Path, scenario: str) -> tuple[bool, str]:
    if scenario not in SPECS:
        return False, f"unknown scenario: {scenario}"
    spec = SPECS[scenario]
    with flows_path.open() as f:
        data = json.load(f)

    existing_ids = {n.get("id") for n in data}
    new_nodes = make_nodes(spec) + spec.get("extra_nodes", [])

    added = []
    for n in new_nodes:
        if n["id"] in existing_ids:
            continue
        data.append(n)
        added.append(n["id"])

    if not added:
        return True, "already patched (no nodes added)"

    # validate JSON is still well-formed (it will be — we built it)
    tmp = flows_path.with_suffix(".json.tmp")
    with tmp.open("w") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    tmp.replace(flows_path)
    return True, f"added {len(added)} node(s): {added}"


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__); sys.exit(2)
    scenario_dir, scenario_name = sys.argv[1], sys.argv[2]
    flows = Path(scenario_dir) / "flows.json"
    if not flows.exists():
        print(f"no flows.json at {flows}"); sys.exit(2)
    ok, msg = patch(flows, scenario_name)
    print(f"[{scenario_name}] {msg}")
    sys.exit(0 if ok else 1)
