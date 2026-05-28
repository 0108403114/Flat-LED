#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
td_hb_setup.py
==============
TouchDesigner MCP 経由で TD 内にハートビート自動送信スレッドを起動する。

使い方:
  python td_hb_setup.py          # ハートビートスレッド起動 (init も自動)
  python td_hb_setup.py stop     # スレッド停止
  python td_hb_setup.py check    # スレッド状態確認
"""

import sys
import json
import urllib.request
import urllib.error

TD_MCP_URL = "http://127.0.0.1:9981/api/td/server/exec"
TOOLS_PATH  = "C:/Projects/02_HomeLiveHall_Trial01/tools"
STORE_OP    = "/project1"
HB_INTERVAL = 1.5  # 秒


def td_exec(script: str) -> dict:
    body = json.dumps({"script": script}).encode("utf-8")
    req = urllib.request.Request(
        TD_MCP_URL, data=body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read())


# ============================================================
#  TD 内で動かすスレッドのソースコード
# ============================================================
HB_THREAD_SCRIPT = f"""
import sys, threading, time

# td_sat_sender がロード済みか確認
mod = sys.modules.get('td_sat_sender')
if mod is None or not hasattr(mod, '_global_ctrl'):
    result = 'ERROR: controller not initialized (run init first)'
else:
    # 既存スレッドを停止
    mod._hb_active = False
    existing = getattr(mod, '_hb_thread', None)
    if existing and existing.is_alive():
        existing.join(timeout=2.0)

    HB_INTERVAL = {HB_INTERVAL}

    def _hb_loop():
        while getattr(mod, '_hb_active', False):
            ctrl = getattr(mod, '_global_ctrl', None)
            if ctrl:
                ctrl.send_heartbeat()
            time.sleep(HB_INTERVAL)

    mod._hb_active = True
    t = threading.Thread(target=_hb_loop, daemon=True, name='led_hb')
    t.start()
    mod._hb_thread = t
    result = f'HB thread started (interval={{HB_INTERVAL}}s, alive={{t.is_alive()}})'
"""

STOP_SCRIPT = f"""
import sys
mod = sys.modules.get('td_sat_sender')
if mod:
    mod._hb_active = False
    result = 'HB thread stop signal sent'
else:
    result = 'module not loaded'
"""

CHECK_SCRIPT = f"""
import sys, threading
mod  = sys.modules.get('td_sat_sender')
ctrl = getattr(mod, '_global_ctrl', None) if mod else None
if mod:
    t = getattr(mod, '_hb_thread', None)
    running = t.is_alive() if t else False
else:
    running = False
result = {{
    'hb_thread_running': running,
    'controller': 'initialized' if ctrl else 'NOT initialized',
}}
"""

INIT_SCRIPT = f"""
import sys, importlib
sys.path.insert(0, '{TOOLS_PATH}')
import td_sat_sender
importlib.reload(td_sat_sender)
ctrl = td_sat_sender.TdLedController()
td_sat_sender._global_ctrl = ctrl
if hasattr(op('{STORE_OP}'), 'unstore'):
    op('{STORE_OP}').unstore('led_ctrl')
result = 'controller initialized'
"""


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "start"

    if cmd == "stop":
        r = td_exec(STOP_SCRIPT)
        print("[OK]" if r.get("success") else "[ERROR]", r.get("data", {}).get("result") or r.get("error"))
        return

    if cmd == "check":
        r = td_exec(CHECK_SCRIPT)
        if r.get("success"):
            for k, v in r["data"]["result"].items():
                print(f"  {k}: {v}")
        else:
            print("[ERROR]", r.get("error"))
        return

    # start (デフォルト)
    # 1. コントローラが未初期化なら init
    chk = td_exec(CHECK_SCRIPT)
    if chk.get("success"):
        status = chk["data"]["result"]
        if status["controller"] == "NOT initialized":
            print("[init] Controller not found — initializing...")
            ir = td_exec(INIT_SCRIPT)
            if not ir.get("success"):
                print("[ERROR] init failed:", ir.get("error"))
                sys.exit(1)
            print("[OK]", ir["data"]["result"])
            if ir["data"].get("stdout"):
                print(ir["data"]["stdout"].strip())

    # 2. ハートビートスレッド起動
    r = td_exec(HB_THREAD_SCRIPT)
    if r.get("success"):
        print("[OK]", r["data"]["result"])
    else:
        print("[ERROR]", r.get("error"))
        sys.exit(1)

    # 3. 状態確認
    chk2 = td_exec(CHECK_SCRIPT)
    if chk2.get("success"):
        for k, v in chk2["data"]["result"].items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
