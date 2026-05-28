#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
td_led_mcp_client.py
====================
TouchDesigner MCP サーバー (http://127.0.0.1:9981) 経由で
LED サテライトノードを制御するクライアント。

【使い方】
  python td_led_mcp_client.py init              # TD 内にコントローラを初期化
  python td_led_mcp_client.py scene LIVE        # シーン切替
  python td_led_mcp_client.py scene HEALING
  python td_led_mcp_client.py scene ENTRY
  python td_led_mcp_client.py scene OFF
  python td_led_mcp_client.py bg FIRE 200 500   # BG, dimmer, trans_ms
  python td_led_mcp_client.py dimmer 128
  python td_led_mcp_client.py lyrics "Hello"
  python td_led_mcp_client.py heartbeat         # 1回だけ送信
  python td_led_mcp_client.py keepalive         # Ctrl+C まで定期 HB 送信
  python td_led_mcp_client.py status            # TD 側の状態確認

【仕組み】
  PC → POST /api/td/server/exec → TD 内 Python
    → td_sat_sender.TdLedController → UDP マルチキャスト → ESP32 LED
"""

import sys
import json
import time
import urllib.request
import urllib.error
import argparse

TD_MCP_URL    = "http://127.0.0.1:9981/api/td/server/exec"
TOOLS_PATH    = "C:/Projects/02_HomeLiveHall_Trial01/tools"
CTRL_STORE_OP = "/project1"


# ============================================================
def td_exec(script: str) -> dict:
    """TD MCP サーバーに Python スクリプトを送信して実行する"""
    body = json.dumps({"script": script}).encode("utf-8")
    req = urllib.request.Request(
        TD_MCP_URL, data=body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        return {"success": False, "error": str(e), "data": None}


def check_td_connection() -> bool:
    """TD MCP サーバーへの接続確認"""
    try:
        r = urllib.request.urlopen("http://127.0.0.1:9981/", timeout=3)
        return r.status == 200
    except Exception:
        return False


# ============================================================
#  コマンド実装
# ============================================================

def cmd_init(args):
    """TD 内に TdLedController を初期化してモジュールグローバルへ保持"""
    script = f"""
import sys, importlib
sys.path.insert(0, '{TOOLS_PATH}')
import td_sat_sender
importlib.reload(td_sat_sender)
ctrl = td_sat_sender.TdLedController()
td_sat_sender._global_ctrl = ctrl  # バックグラウンドスレッド用
if hasattr(op('{CTRL_STORE_OP}'), 'unstore'):
    op('{CTRL_STORE_OP}').unstore('led_ctrl')
result = 'LED controller initialized'
"""
    r = td_exec(script)
    if r.get("success"):
        print(f"[OK] {r['data']['result']}")
        if r["data"].get("stdout"):
            print(r["data"]["stdout"].strip())
    else:
        print(f"[ERROR] {r.get('error')}")
        sys.exit(1)


def cmd_scene(args):
    """シーンプリセットを送信"""
    scene = args.scene.upper()
    script = f"""
import sys
mod = sys.modules.get('td_sat_sender')
ctrl = getattr(mod, '_global_ctrl', None) if mod else None
if ctrl is None:
    result = 'ERROR: controller not initialized (run init first)'
else:
    ctrl.send_scene('{scene}')
    result = 'scene={scene} sent'
"""
    r = td_exec(script)
    _print_result(r)


def cmd_bg(args):
    """BG アセットを指定して送信"""
    bg       = args.bg.upper()
    dimmer   = args.dimmer
    trans_ms = args.trans_ms
    script = f"""
import sys
mod = sys.modules.get('td_sat_sender')
ctrl = getattr(mod, '_global_ctrl', None) if mod else None
if ctrl is None:
    result = 'ERROR: controller not initialized'
else:
    ctrl.send_ctrl(bg='{bg}', dimmer={dimmer}, trans_ms={trans_ms})
    result = 'bg={bg} dimmer={dimmer} trans={trans_ms}ms sent'
"""
    r = td_exec(script)
    _print_result(r)


def cmd_dimmer(args):
    """輝度だけ変更"""
    script = f"""
import sys
mod = sys.modules.get('td_sat_sender')
ctrl = getattr(mod, '_global_ctrl', None) if mod else None
if ctrl is None:
    result = 'ERROR: controller not initialized'
else:
    ctrl.send_dimmer({args.value})
    result = 'dimmer={args.value} sent'
"""
    r = td_exec(script)
    _print_result(r)


def cmd_lyrics(args):
    """歌詞テキストを送信"""
    text = args.text.replace("'", "\\'")
    script = f"""
import sys
mod = sys.modules.get('td_sat_sender')
ctrl = getattr(mod, '_global_ctrl', None) if mod else None
if ctrl is None:
    result = 'ERROR: controller not initialized'
else:
    ctrl.send_lyrics_line('{text}')
    result = 'lyrics sent'
"""
    r = td_exec(script)
    _print_result(r)


def cmd_lyrics_file_start(args):
    """TD内で歌詞ファイルを読み込み、時間制御でバックグラウンド送信"""
    file_path = args.file_path.replace('\\', '/')
    song_id = int(args.song_id)
    version = int(args.version)
    interval_s = float(args.interval)
    start_delay_s = float(args.start_delay)
    zone = int(args.zone)
    node = int(args.node)
    timed = "True" if args.mode in ("auto", "timed") else "False"

    script = f"""
import sys, threading, os
mod = sys.modules.get('td_sat_sender')
ctrl = getattr(mod, '_global_ctrl', None) if mod else None
path = r'{file_path}'
if ctrl is None:
    result = 'ERROR: controller not initialized'
elif not os.path.exists(path):
    result = 'ERROR: file not found: ' + path
else:
    mod._lyrics_active = False
    old_t = getattr(mod, '_lyrics_thread', None)
    if old_t and old_t.is_alive():
        old_t.join(timeout=1.0)

    def _stop_requested():
        return not getattr(mod, '_lyrics_active', False)

    def _runner():
        try:
            ctrl.play_lyrics_file(
                file_path=path,
                interval_s={interval_s},
                timed={timed},
                song_id={song_id},
                version={version},
                zone={zone},
                node={node},
                start_delay_s={start_delay_s},
                stop_flag_getter=_stop_requested,
            )
        finally:
            mod._lyrics_active = False

    mod._lyrics_active = True
    t = threading.Thread(target=_runner, daemon=True, name='lyrics_player')
    t.start()
    mod._lyrics_thread = t
    result = 'lyrics file started: ' + path
"""
    r = td_exec(script)
    _print_result(r)


def cmd_lyrics_file_stop(args):
    """TD内の歌詞ファイル再生スレッドを停止"""
    script = """
import sys
mod = sys.modules.get('td_sat_sender')
if mod:
    mod._lyrics_active = False
    result = 'lyrics playback stop signal sent'
else:
    result = 'module not loaded'
"""
    r = td_exec(script)
    _print_result(r)


def cmd_lyrics_file_check(args):
    """TD内の歌詞ファイル再生スレッド状態を確認"""
    script = """
import sys
mod = sys.modules.get('td_sat_sender')
t = getattr(mod, '_lyrics_thread', None) if mod else None
active = bool(getattr(mod, '_lyrics_active', False)) if mod else False
result = {
    'lyrics_thread': 'running' if (t and t.is_alive()) else 'stopped',
    'lyrics_active_flag': active,
}
"""
    r = td_exec(script)
    if r.get('success'):
        for k, v in r['data']['result'].items():
            print(f"  {k}: {v}")
    else:
        print(f"[ERROR] {r.get('error')}")


def cmd_heartbeat(args):
    """ハートビートを 1 回送信"""
    script = f"""
import sys
mod = sys.modules.get('td_sat_sender')
ctrl = getattr(mod, '_global_ctrl', None) if mod else None
if ctrl is None:
    result = 'ERROR: controller not initialized'
else:
    ctrl.send_heartbeat()
    result = 'heartbeat sent'
"""
    r = td_exec(script)
    _print_result(r)


def cmd_keepalive(args):
    """Ctrl+C まで 1.5 秒ごとにハートビートを送信し続ける"""
    interval = 1.5
    print(f"[keepalive] Sending heartbeat every {interval}s  (Ctrl+C to stop)")

    # まずコントローラが初期化されているか確認
    r = td_exec(
        "import sys\n"
        "mod = sys.modules.get('td_sat_sender')\n"
        "result = 'ctrl_ok' if (mod and hasattr(mod, '_global_ctrl')) else 'ctrl_none'"
    )
    if r.get("data", {}).get("result") == "ctrl_none":
        print("[keepalive] Controller not initialized — running init first...")
        cmd_init(argparse.Namespace())

    try:
        while True:
            r = td_exec(f"""
import sys
mod = sys.modules.get('td_sat_sender')
ctrl = getattr(mod, '_global_ctrl', None) if mod else None
if ctrl: ctrl.send_heartbeat()
result = 'hb'
""")
            if not r.get("success"):
                print(f"[keepalive] HB error: {r.get('error')}")
            else:
                print(f"[keepalive] HB sent at {time.strftime('%H:%M:%S')}")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[keepalive] stopped")


def cmd_status(args):
    """TD 側のコントローラ状態を確認"""
    if not check_td_connection():
        print("[ERROR] TD MCP server not reachable at http://127.0.0.1:9981")
        sys.exit(1)

    script = f"""
import sys
mod  = sys.modules.get('td_sat_sender')
ctrl = getattr(mod, '_global_ctrl', None) if mod else None
hb_t = getattr(mod, '_hb_thread', None) if mod else None
result = {{
    'td_python': sys.version.split()[0],
    'controller': 'initialized' if ctrl else 'NOT initialized',
    'hb_thread': 'running' if (hb_t and hb_t.is_alive()) else 'stopped',
    'store_op': '{CTRL_STORE_OP}',
}}
"""
    r = td_exec(script)
    if r.get("success"):
        print("[TD Status]")
        for k, v in r["data"]["result"].items():
            print(f"  {k}: {v}")
    else:
        print(f"[ERROR] {r.get('error')}")


def cmd_hb_start(args):
    """TD 内でハートビートスレッドを起動"""
    script = f"""
import sys, threading, time
mod = sys.modules.get('td_sat_sender')
if mod is None or not hasattr(mod, '_global_ctrl'):
    result = 'ERROR: controller not initialized (run init first)'
else:
    mod._hb_active = False
    existing = getattr(mod, '_hb_thread', None)
    if existing and existing.is_alive():
        existing.join(timeout=1.0)
    def _hb_loop():
        while getattr(mod, '_hb_active', False):
            ctrl = getattr(mod, '_global_ctrl', None)
            if ctrl:
                ctrl.send_heartbeat()
            time.sleep(1.5)
    mod._hb_active = True
    t = threading.Thread(target=_hb_loop, daemon=True, name='led_hb')
    t.start()
    mod._hb_thread = t
    result = f'HB thread alive={{t.is_alive()}}'
"""
    r = td_exec(script)
    _print_result(r)


def cmd_hb_stop(args):
    """TD 内のハートビートスレッドを停止"""
    script = """
import sys
mod = sys.modules.get('td_sat_sender')
if mod:
    mod._hb_active = False
    result = 'HB thread stop signal sent'
else:
    result = 'module not loaded'
"""
    r = td_exec(script)
    _print_result(r)


def cmd_hb_check(args):
    """ハートビートスレッドの状態確認"""
    script = f"""
import sys
mod  = sys.modules.get('td_sat_sender')
ctrl = getattr(mod, '_global_ctrl', None) if mod else None
t    = getattr(mod, '_hb_thread', None) if mod else None
result = {{
    'hb_thread': 'running' if (t and t.is_alive()) else 'stopped',
    'controller': 'initialized' if ctrl else 'NOT initialized',
}}
"""
    r = td_exec(script)
    if r.get("success"):
        for k, v in r["data"]["result"].items():
            print(f"  {k}: {v}")
    else:
        print(f"[ERROR] {r.get('error')}")


def _print_result(r: dict):
    if r.get("success"):
        data = r.get("data", {})
        print(f"[OK] {data.get('result', '')}")
        if data.get("stdout"):
            print(data["stdout"].strip())
    else:
        print(f"[ERROR] {r.get('error')}")
        if "not initialized" in str(r.get("error", "")):
            print("  → Run: python td_led_mcp_client.py init")
        sys.exit(1)


# ============================================================
#  CLI エントリポイント
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="TouchDesigner MCP 経由 LED 制御クライアント"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init",      help="TD 内に LED コントローラを初期化")
    sub.add_parser("heartbeat", help="ハートビートを 1 回送信")
    sub.add_parser("keepalive", help="Ctrl+C まで定期ハートビート送信 (PC側ループ)")
    sub.add_parser("hb-start",  help="TD 内バックグラウンドスレッドでHB自動送信開始")
    sub.add_parser("hb-stop",   help="TD 内HBスレッドを停止")
    sub.add_parser("hb-check",  help="TD 内HBスレッドの状態確認")
    sub.add_parser("status",    help="TD 接続状態と初期化状態を確認")

    p_scene = sub.add_parser("scene", help="シーンプリセット送信")
    p_scene.add_argument("scene", choices=["LIVE","HEALING","ENTRY","OFF",
                                            "live","healing","entry","off"])

    p_bg = sub.add_parser("bg", help="BG アセット送信")
    p_bg.add_argument("bg", choices=["FIRE","OCEAN","STARFIELD","RAINBOW","PULSE","OFF",
                                     "fire","ocean","starfield","rainbow","pulse","off"])
    p_bg.add_argument("dimmer",   nargs="?", type=int,  default=200)
    p_bg.add_argument("trans_ms", nargs="?", type=int,  default=500)

    p_dim = sub.add_parser("dimmer", help="輝度変更 (0-255)")
    p_dim.add_argument("value", type=int)

    p_lyr = sub.add_parser("lyrics", help="歌詞テキスト送信")
    p_lyr.add_argument("text")

    p_lf_start = sub.add_parser("lyrics-file-start", help="歌詞ファイルを時間制御で再生開始 (TD内スレッド)")
    p_lf_start.add_argument("file_path", help="歌詞テキストファイルのパス")
    p_lf_start.add_argument("--mode", choices=["auto", "timed", "interval"], default="auto",
                            help="auto/timed: タイムスタンプ優先, interval: 固定間隔")
    p_lf_start.add_argument("--interval", type=float, default=2.0,
                            help="タイムスタンプなし行の送信間隔(秒)")
    p_lf_start.add_argument("--start-delay", type=float, default=0.5,
                            help="再生開始遅延(秒)")
    p_lf_start.add_argument("--song-id", type=int, default=1)
    p_lf_start.add_argument("--version", type=int, default=1)
    p_lf_start.add_argument("--zone", type=int, default=0)
    p_lf_start.add_argument("--node", type=int, default=0)

    sub.add_parser("lyrics-file-stop", help="歌詞ファイル再生を停止")
    sub.add_parser("lyrics-file-check", help="歌詞ファイル再生の状態確認")

    args = parser.parse_args()

    if not check_td_connection():
        print("[ERROR] TD MCP server not reachable at http://127.0.0.1:9981")
        print("  → TouchDesigner が起動していて mcp_webserver_base が動作しているか確認")
        sys.exit(1)

    dispatch = {
        "init":      cmd_init,
        "scene":     cmd_scene,
        "bg":        cmd_bg,
        "dimmer":    cmd_dimmer,
        "lyrics":    cmd_lyrics,
        "lyrics-file-start": cmd_lyrics_file_start,
        "lyrics-file-stop":  cmd_lyrics_file_stop,
        "lyrics-file-check": cmd_lyrics_file_check,
        "heartbeat": cmd_heartbeat,
        "keepalive": cmd_keepalive,
        "hb-start":  cmd_hb_start,
        "hb-stop":   cmd_hb_stop,
        "hb-check":  cmd_hb_check,
        "status":    cmd_status,
    }
    dispatch[args.cmd](args)


if __name__ == "__main__":
    main()
