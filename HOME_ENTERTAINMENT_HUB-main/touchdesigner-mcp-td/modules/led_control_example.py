"""
led_control_example.py
======================
TouchDesigner Script DAT に貼り付けて使う LED 制御テンプレート。

【TD セットアップ手順】
1. 新しい Script DAT を作成
2. このファイルの内容を貼り付ける (またはパスを参照)
3. Timer CHOP (周期 1.5秒) → Execute DAT でハートビートを定期送信
4. Button Comp の onClick Callback からシーン関数を呼ぶ

【ファイル構成】
  C:/Projects/02_HomeLiveHall_Trial01/
    tools/
      td_sat_sender.py   ← 制御ロジック本体
    touchdesigner-mcp-td/
      modules/
        led_control_example.py  ← このファイル (TD テンプレート)
"""

import sys
import importlib

# -------------------------------------------------------
# 初期化 (Script DAT の onSetupParameters、または
#         Extension の __init__ で 1 回だけ呼ぶ)
# -------------------------------------------------------
TOOLS_PATH = 'C:/Projects/02_HomeLiveHall_Trial01/tools'

def init_controller():
    """
    コントローラを初期化して TD の storage に保存する。
    Script DAT の onSetupParameters や、
    Constant CHOP の最初のフレームで呼ぶ。
    """
    if TOOLS_PATH not in sys.path:
        sys.path.insert(0, TOOLS_PATH)

    # 開発中はモジュールを毎回リロードする (変更が即反映される)
    import td_sat_sender
    importlib.reload(td_sat_sender)

    ctrl = td_sat_sender.TdLedController()
    # TD の storage に保存 (global op からアクセス可能)
    op('led_ctrl_store').store('ctrl', ctrl)
    print('[LED] controller initialized')
    return ctrl


def get_controller():
    """Storage からコントローラを取得する。"""
    return op('led_ctrl_store').fetch('ctrl', None)


# -------------------------------------------------------
# シーン制御関数 (Button Comp の Callback から呼ぶ)
# -------------------------------------------------------
def scene_live():
    """LIVE シーン: FIRE + 歌詞テキスト表示"""
    ctrl = get_controller()
    if ctrl:
        ctrl.send_scene('LIVE')

def scene_healing():
    """HEALING シーン: OCEAN + テキスト OFF"""
    ctrl = get_controller()
    if ctrl:
        ctrl.send_scene('HEALING')

def scene_entry():
    """ENTRY シーン: STARFIELD"""
    ctrl = get_controller()
    if ctrl:
        ctrl.send_scene('ENTRY')

def scene_off():
    """OFF シーン: 消灯"""
    ctrl = get_controller()
    if ctrl:
        ctrl.send_scene('OFF')


# -------------------------------------------------------
# 輝度スライダー (Slider COMP の onValueChange から呼ぶ)
# -------------------------------------------------------
def set_dimmer(value_0_to_1: float):
    """
    Slider COMP の value (0.0〜1.0) を dimmer (0〜255) に変換して送信。
    """
    ctrl = get_controller()
    if ctrl:
        dimmer = int(value_0_to_1 * 255)
        ctrl.send_dimmer(dimmer)


# -------------------------------------------------------
# 歌詞テキスト (Text COMP の onValueChange から呼ぶ)
# -------------------------------------------------------
def send_lyrics(text: str):
    """
    Text COMP から歌詞を送信する。
    14 文字 (ASCII) = LED マトリクス横幅 88px に収まる目安。
    """
    ctrl = get_controller()
    if ctrl:
        ctrl.send_lyrics_line(text)


# -------------------------------------------------------
# ハートビート (Timer CHOP → Execute DAT で定期呼び出し)
# -------------------------------------------------------
def heartbeat():
    """
    1.5 秒ごとに呼ぶ。3 秒途絶えると LED がセーフ白に遷移する。

    TD 設定例:
      Timer CHOP: length=1.5sec, loop=on, active=on
      Execute DAT: onTimerPulse → heartbeat()
    """
    ctrl = get_controller()
    if ctrl:
        ctrl.send_heartbeat()


# -------------------------------------------------------
# BG を直接指定 (開発・デバッグ用)
# -------------------------------------------------------
def set_bg(bg_name: str, dimmer: int = 200, trans_ms: int = 500):
    """
    bg_name: 'FIRE' / 'OCEAN' / 'STARFIELD' / 'RAINBOW' / 'PULSE' / 'OFF'
    """
    ctrl = get_controller()
    if ctrl:
        ctrl.send_ctrl(bg=bg_name, dimmer=dimmer, trans_ms=trans_ms)


# -------------------------------------------------------
# TD Script DAT のエントリポイント
# -------------------------------------------------------
# Script DAT を「Run」した際に呼ばれる
# (Script DAT > Parameters > Run で使用)
def onRun(scriptDat):
    init_controller()
    print('[LED] Script DAT ready')
