#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
td_ui_builder.py
================
TouchDesigner MCP 経由で /project1/td_led_ui を構築・配線する。

Usage:
  python tools/td_ui_builder.py
"""

import json
import urllib.parse
import urllib.request

TD_BASE = "http://127.0.0.1:9981"
TD_EXEC_URL = TD_BASE + "/api/td/server/exec"
TD_NODES_URL = TD_BASE + "/api/nodes"


def td_exec(script: str) -> dict:
    body = json.dumps({"script": script}).encode("utf-8")
    req = urllib.request.Request(
        TD_EXEC_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=12) as resp:
        return json.loads(resp.read())


def create_node(parent_path: str, node_type: str, node_name: str) -> dict:
    body = json.dumps(
        {
            "parentPath": parent_path,
            "nodeType": node_type,
            "nodeName": node_name,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        TD_NODES_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=12) as resp:
        return json.loads(resp.read())


def delete_node(node_path: str) -> dict:
    q = urllib.parse.quote(node_path, safe="")
    req = urllib.request.Request(f"{TD_NODES_URL}?nodePath={q}", method="DELETE")
    with urllib.request.urlopen(req, timeout=12) as resp:
        return json.loads(resp.read())


UI_EXEC_TEMPLATE = """
# me - this DAT
# frame-end polling UI bridge for LED controller

import sys
import time
import importlib
import threading

base = op('/project1/td_led_ui')
TOOLS_PATH = 'C:/Projects/02_HomeLiveHall_Trial01/tools'


def _ensure_ctrl():
    mod = sys.modules.get('td_sat_sender')
    ctrl = getattr(mod, '_global_ctrl', None) if mod else None
    if ctrl:
        return ctrl

    # TD 起動直後は毎フレーム初期化を試すと負荷が高いので間引く
    now = time.time()
    last_try = float(base.fetch('bootstrap_last_try_ts', 0.0))
    if now - last_try < 2.0:
        return None
    base.store('bootstrap_last_try_ts', now)

    try:
        if TOOLS_PATH not in sys.path:
            sys.path.insert(0, TOOLS_PATH)
        import td_sat_sender
        importlib.reload(td_sat_sender)
        ctrl = td_sat_sender.TdLedController()
        td_sat_sender._global_ctrl = ctrl
        base.store('ui_bootstrap_state', 'controller initialized')
        return ctrl
    except Exception as e:
        base.store('ui_bootstrap_state', 'init error: ' + str(e))
        return None


def _get_ctrl():
    return _ensure_ctrl()


def _edge(key, now):
    prev = bool(base.fetch('prev_' + key, False))
    base.store('prev_' + key, bool(now))
    return (not prev) and bool(now)


def _changed(key, now, eps=0.5):
    prev = float(base.fetch('prev_' + key, now))
    base.store('prev_' + key, float(now))
    return abs(float(now) - prev) >= eps


def _get_lyrics_text():
    s = op('/project1/td_led_ui/txt_lyrics/string')
    if s and s.numRows > 0 and s.numCols > 0:
        return str(s[0, 0].val)
    return ''


def _get_field_text(field_path, default=''):
    s = op(field_path + '/string')
    if s and s.numRows > 0 and s.numCols > 0:
        return str(s[0, 0].val)
    return default


def onFrameEnd(frame):
    ctrl = _get_ctrl()
    if not ctrl:
        return

    if _edge('live', op('{btn_live_path}').par.value0.eval()):
        ctrl.send_scene('LIVE')
        base.store('ui_last_action', 'scene LIVE')

    if _edge('healing', op('{btn_healing_path}').par.value0.eval()):
        ctrl.send_scene('HEALING')
        base.store('ui_last_action', 'scene HEALING')

    if _edge('entry', op('{btn_entry_path}').par.value0.eval()):
        ctrl.send_scene('ENTRY')
        base.store('ui_last_action', 'scene ENTRY')

    if _edge('off', op('{btn_off_path}').par.value0.eval()):
        ctrl.send_scene('OFF')
        base.store('ui_last_action', 'scene OFF')

    if _edge('ready', op('{btn_ready_path}').par.value0.eval()):
        ctrl.send_scene('READY')
        base.store('ui_last_action', 'scene READY')

    if _edge('event', op('{btn_event_path}').par.value0.eval()):
        ctrl.send_scene('EVENT_1')
        base.store('ui_last_action', 'scene EVENT_1')

    dim = op('{sld_dimmer_path}').par.value0.eval()
    if _changed('dimmer', dim, eps=1.0):
        ctrl.send_dimmer(int(max(0, min(255, round(dim)))))
        base.store('ui_last_action', 'dimmer ' + str(int(round(dim))))

    if _edge('send_lyrics', op('{btn_send_lyrics_path}').par.value0.eval()):
        text = _get_lyrics_text().strip()
        if text:
            ctrl.send_lyrics_line(text[:14])
            base.store('ui_last_action', 'lyrics ' + text[:14])

    if _edge('lyrics_file_start', op('{btn_lyrics_file_start_path}').par.value0.eval()):
        fp = _get_field_text('{txt_lyrics_file_path}').strip()
        timed_mode = bool(op('{btn_lyrics_timed_toggle_path}').par.value0.eval())
        mod = sys.modules.get('td_sat_sender')
        if not fp:
            base.store('ui_last_action', 'lyrics file path is empty')
        elif not mod:
            base.store('ui_last_action', 'td_sat_sender module not loaded')
        else:
            mod._lyrics_active = False
            old_t = getattr(mod, '_lyrics_thread', None)
            if old_t and old_t.is_alive():
                old_t.join(timeout=1.0)

            def _stop_requested():
                return not getattr(mod, '_lyrics_active', False)

            def _lyrics_runner(path, timed):
                try:
                    c = getattr(mod, '_global_ctrl', None)
                    if c:
                        sent = c.play_lyrics_file(
                            file_path=path,
                            interval_s=2.0,
                            timed=timed,
                            song_id=1,
                            version=1,
                            zone=0,
                            node=0,
                            start_delay_s=0.2,
                            stop_flag_getter=_stop_requested,
                        )
                        base.store('ui_last_action', 'lyrics file done lines=' + str(sent))
                    else:
                        base.store('ui_last_action', 'controller not initialized')
                except Exception as e:
                    base.store('ui_last_action', 'lyrics file error: ' + str(e))
                finally:
                    mod._lyrics_active = False

            mod._lyrics_active = True
            t = threading.Thread(
                target=_lyrics_runner,
                args=(fp, timed_mode),
                daemon=True,
                name='lyrics_player'
            )
            t.start()
            mod._lyrics_thread = t
            base.store('ui_last_action', 'lyrics file start (' + ('timed' if timed_mode else 'interval') + ')')

    if _edge('lyrics_file_stop', op('{btn_lyrics_file_stop_path}').par.value0.eval()):
        mod = sys.modules.get('td_sat_sender')
        if mod:
            mod._lyrics_active = False
            base.store('ui_last_action', 'lyrics file stop')

    hb_on = bool(op('{btn_hb_toggle_path}').par.value0.eval())
    mod = sys.modules.get('td_sat_sender')
    if mod:
        prev_hb = bool(base.fetch('prev_hb_toggle', False))
        if hb_on != prev_hb:
            base.store('prev_hb_toggle', hb_on)
            if hb_on:
                mod._hb_active = True
                t = getattr(mod, '_hb_thread', None)
                if not (t and t.is_alive()):
                    import threading, time

                    def _hb_loop():
                        while getattr(mod, '_hb_active', False):
                            c = getattr(mod, '_global_ctrl', None)
                            if c:
                                c.send_heartbeat()
                            time.sleep(1.5)

                    t = threading.Thread(target=_hb_loop, daemon=True, name='led_hb')
                    t.start()
                    mod._hb_thread = t
                base.store('ui_last_action', 'hb on')
            else:
                mod._hb_active = False
                base.store('ui_last_action', 'hb off')

    return
"""


def configure_ui(paths: dict) -> dict:
    ui_exec_text = UI_EXEC_TEMPLATE.format(**paths)
    script = f"""
ui = op('/project1/td_led_ui')
ui.par.w = 1060
ui.par.h = 520
ui.par.x = 800
ui.par.y = 200

ui_map = {{
    '{paths['btn_live_path']}':              ('LIVE',               20, 430, 100, 60, 'momentary'),
    '{paths['btn_healing_path']}':           ('HEALING',           130, 430, 100, 60, 'momentary'),
    '{paths['btn_entry_path']}':             ('ENTRY',             240, 430, 100, 60, 'momentary'),
    '{paths['btn_off_path']}':               ('OFF',               350, 430, 100, 60, 'momentary'),
    '{paths['btn_ready_path']}':             ('READY',             460, 430, 100, 60, 'momentary'),
    '{paths['btn_event_path']}':             ('EVENT',             570, 430, 100, 60, 'momentary'),
    '{paths['btn_send_lyrics_path']}':       ('SEND LYR',          680, 430, 100, 60, 'momentary'),
    '{paths['btn_hb_toggle_path']}':         ('HB AUTO',           790, 430, 100, 60, 'toggledown'),
    '{paths['btn_lyrics_file_start_path']}': ('PLAY FILE',         900, 430, 100, 60, 'momentary'),
    '{paths['btn_lyrics_file_stop_path']}':  ('STOP FILE',         900, 360, 100, 56, 'momentary'),
    '{paths['btn_lyrics_timed_toggle_path']}': ('TIMED',           900, 290, 100, 56, 'toggledown'),
}}

for path, (label, x, y, w, h, btype) in ui_map.items():
    b = op(path)
    b.par.label = label
    b.par.x = x
    b.par.y = y
    b.par.w = w
    b.par.h = h
    b.par.buttontype = btype

sld = op('{paths['sld_dimmer_path']}')
sld.par.label = 'DIMMER'
sld.par.x = 20
sld.par.y = 360
sld.par.w = 360
sld.par.h = 36
sld.par.valuerange0l = 0
sld.par.valuerange0h = 255
sld.par.value0 = 200

txt = op('{paths['txt_lyrics_path']}')
txt.par.x = 20
txt.par.y = 20
txt.par.w = 840
txt.par.h = 320

txt_file = op('{paths['txt_lyrics_file_path']}')
txt_file.par.x = 20
txt_file.par.y = 360
txt_file.par.w = 840
txt_file.par.h = 56

txt_file_str = op('{paths['txt_lyrics_file_path']}/string')
if txt_file_str and txt_file_str.numRows > 0 and txt_file_str.numCols > 0:
    txt_file_str[0, 0] = 'C:/Projects/02_HomeLiveHall_Trial01/tools/sample_lyrics_timed.txt'

timed_btn = op('{paths['btn_lyrics_timed_toggle_path']}')
timed_btn.par.value0 = 1

exec_dat = op('{paths['ui_exec_path']}')
exec_dat.par.active = True
exec_dat.par.frameend = True
exec_dat.par.fromop = '/project1/td_led_ui'
exec_dat.text = {json.dumps(ui_exec_text)}

# Network Editor 上でノードが重ならないよう配置する
root_layout = {{
    'mcp_webserver_base': (-900, 450),
    'led_control': (-500, 450),
    'led_control_callbacks': (-120, 450),
    'td_led_ui': (-900, 80),
}}
root = op('/project1')
for name, (nx, ny) in root_layout.items():
    n = root.op(name)
    if n:
        n.nodeX = nx
        n.nodeY = ny

mcp = op('/project1/mcp_webserver_base')
if mcp:
    mcp_layout = {{
        'import_modules': (-600, 120),
        'mcp_webserver_script': (-220, 120),
        'mpc_webserver': (180, 120),
        'parameter1': (560, 120),
    }}
    for name, (nx, ny) in mcp_layout.items():
        n = mcp.op(name)
        if n:
            n.nodeX = nx
            n.nodeY = ny

ui_node_layout = {{
    'ui_exec': (-980, 330),
    'btn_live': (-760, 330),
    'btn_healing': (-580, 330),
    'btn_entry': (-400, 330),
    'btn_off': (-220, 330),
    'btn_ready': (-40, 330),
    'btn_event': (140, 330),
    'btn_send_lyrics': (320, 330),
    'btn_hb_toggle': (500, 330),
    'btn_lyrics_file_start': (680, 330),
    'btn_lyrics_file_stop': (680, 260),
    'btn_lyrics_timed_toggle': (680, 190),
    'sld_dimmer': (-700, 80),
    'txt_lyrics': (80, 80),
    'txt_lyrics_file': (940, 80),
}}
for name, (nx, ny) in ui_node_layout.items():
    n = ui.op(name)
    if n:
        n.nodeX = nx
        n.nodeY = ny

ui.store('ui_last_action', 'ui built')
result = '/project1/td_led_ui configured'
"""
    return td_exec(script)


def main() -> None:
    # 1) old UI があれば削除
    try:
        delete_node("/project1/td_led_ui")
    except Exception:
        pass

    # 2) ノード作成
    create_plan = [
        ("/project1", "containerCOMP", "td_led_ui"),
        ("/project1/td_led_ui", "buttonCOMP", "btn_live"),
        ("/project1/td_led_ui", "buttonCOMP", "btn_healing"),
        ("/project1/td_led_ui", "buttonCOMP", "btn_entry"),
        ("/project1/td_led_ui", "buttonCOMP", "btn_off"),
        ("/project1/td_led_ui", "buttonCOMP", "btn_ready"),
        ("/project1/td_led_ui", "buttonCOMP", "btn_event"),
        ("/project1/td_led_ui", "buttonCOMP", "btn_send_lyrics"),
        ("/project1/td_led_ui", "buttonCOMP", "btn_hb_toggle"),
        ("/project1/td_led_ui", "buttonCOMP", "btn_lyrics_file_start"),
        ("/project1/td_led_ui", "buttonCOMP", "btn_lyrics_file_stop"),
        ("/project1/td_led_ui", "buttonCOMP", "btn_lyrics_timed_toggle"),
        ("/project1/td_led_ui", "sliderCOMP", "sld_dimmer"),
        ("/project1/td_led_ui", "fieldCOMP", "txt_lyrics"),
        ("/project1/td_led_ui", "fieldCOMP", "txt_lyrics_file"),
        ("/project1/td_led_ui", "executeDAT", "ui_exec"),
    ]

    created = {}
    for parent, ntype, name in create_plan:
        r = create_node(parent, ntype, name)
        if not r.get("success"):
            print("[ERROR] create failed:", name, r.get("error"))
            raise SystemExit(1)
        created[name] = r["data"]["result"]["path"]

    # 3) パラメータと実行コードを配線
    paths = {
        "btn_live_path": created["btn_live"],
        "btn_healing_path": created["btn_healing"],
        "btn_entry_path": created["btn_entry"],
        "btn_off_path": created["btn_off"],
        "btn_ready_path": created["btn_ready"],
        "btn_event_path": created["btn_event"],
        "btn_send_lyrics_path": created["btn_send_lyrics"],
        "btn_hb_toggle_path": created["btn_hb_toggle"],
        "btn_lyrics_file_start_path": created["btn_lyrics_file_start"],
        "btn_lyrics_file_stop_path": created["btn_lyrics_file_stop"],
        "btn_lyrics_timed_toggle_path": created["btn_lyrics_timed_toggle"],
        "sld_dimmer_path": created["sld_dimmer"],
        "txt_lyrics_path": created["txt_lyrics"],
        "txt_lyrics_file_path": created["txt_lyrics_file"],
        "ui_exec_path": created["ui_exec"],
    }
    r = configure_ui(paths)
    if not r.get("success"):
        print("[ERROR] configure failed:", r.get("error"))
        raise SystemExit(1)

    print("[OK]", r.get("data", {}).get("result"))


if __name__ == "__main__":
    main()
