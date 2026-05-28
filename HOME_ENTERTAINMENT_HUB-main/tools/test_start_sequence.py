#!/usr/bin/env python3
"""
LED Node 2 台同時スタートテスト

各ノードに個別の NODE 表示を出しつつ、同時に共通の演出タイムラインを送る。
必要に応じて zone/node を個別指定して、片側だけの表示も確認できる。
"""

import sys
import time

sys.path.insert(0, 'tools')

from td_sat_sender import TdLedController


def send_node_label(ctrl: TdLedController, node: int, label: str) -> None:
    ctrl.send_text_custom(label, zone=1, node=node)


def set_pair_bg(ctrl: TdLedController, node1_bg: str, node2_bg: str, trans_ms: int = 0) -> None:
    ctrl.send_ctrl(bg=node1_bg, dimmer=8, text_mode='OFF', trans_ms=trans_ms, zone=1, node=1)
    ctrl.send_ctrl(bg=node2_bg, dimmer=8, text_mode='OFF', trans_ms=trans_ms, zone=1, node=2)


def wait_with_heartbeat(ctrl: TdLedController, duration_s: float, heartbeat_interval_s: float = 1.5) -> None:
    deadline = time.time() + max(0.0, duration_s)
    next_heartbeat = time.time()
    while True:
        now = time.time()
        if now >= deadline:
            return
        if now >= next_heartbeat:
            ctrl.send_heartbeat()
            next_heartbeat = now + heartbeat_interval_s
        time.sleep(min(0.1, deadline - now))


def main() -> None:
    ctrl = TdLedController(monitor=True)

    try:
        print('========== NODE 同時起動テスト ==========', flush=True)
        print('Node 1 / Node 2 に対して、個別表示と共通タイムラインを送信します。', flush=True)
        print(flush=True)

        print('[S01:0s] NODE 番号表示', flush=True)
        send_node_label(ctrl, 1, 'NODE 1')
        send_node_label(ctrl, 2, 'NODE 2')
        wait_with_heartbeat(ctrl, 2)

        print('[S01:2s] Seat Info (Node別表示)', flush=True)
        ctrl.send_text_custom('Your SEAT GATE 11', zone=1, node=1)
        ctrl.send_text_custom('ISLE 3 SEAT 44', zone=1, node=2)
        wait_with_heartbeat(ctrl, 5)

        print('[S02:7s] TEST START (base image off)', flush=True)
        ctrl.send_ctrl(bg='OFF', dimmer=8, text_mode='CUSTOM', trans_ms=0, zone=0, node=0)
        ctrl.send_text_custom('TEST START', zone=0, node=0)
        wait_with_heartbeat(ctrl, 3)

        print('[S03:10s] Welcome + Ocean', flush=True)
        ctrl.send_ctrl(bg='OCEAN', dimmer=8, text_mode='CUSTOM', trans_ms=500, zone=0, node=0)
        ctrl.send_text_custom('Welcome!', zone=0, node=0)
        wait_with_heartbeat(ctrl, 5)

        print('[S04:15s] Countdown (normal): 10 to 6', flush=True)
        for remaining in range(10, 5, -1):
            ctrl.send_text_custom(f'COUNTDOWN {remaining:02d}', zone=0, node=0)
            wait_with_heartbeat(ctrl, 1)

        print('[S05:20s] Countdown (stylish): start at 5 (node-side sync)', flush=True)
        ctrl.send_ctrl(bg='OCEAN', dimmer=8, text_mode='CUSTOM', trans_ms=350, zone=0, node=0)
        ctrl.send_text_custom('5', zone=0, node=0)
        wait_with_heartbeat(ctrl, 6)

        print('[S06:26s] Fireworks', flush=True)
        ctrl.send_ctrl(bg='FIREWORKS_LOCAL', dimmer=8, text_mode='OFF', trans_ms=350, zone=0, node=0)
        wait_with_heartbeat(ctrl, 6)

        print('[S07:32s] FIRE background', flush=True)
        ctrl.send_ctrl(bg='FIRE', dimmer=8, text_mode='OFF', trans_ms=1000, zone=0, node=0)
        wait_with_heartbeat(ctrl, 5)

        print('[S08:37s] Node1 lyric + Node2 FIRE', flush=True)
        set_pair_bg(ctrl, 'OFF', 'FIRE', trans_ms=300)
        wait_with_heartbeat(ctrl, 0.5)
        set_pair_bg(ctrl, 'FIRE', 'OFF', trans_ms=300)
        wait_with_heartbeat(ctrl, 0.5)
        ctrl.send_ctrl(bg='OFF', dimmer=8, text_mode='LYRICS', trans_ms=0, zone=1, node=1)
        ctrl.send_ctrl(bg='FIRE', dimmer=8, text_mode='OFF', trans_ms=0, zone=1, node=2)
        ctrl.send_lyrics_line('Lyrics ABCD', song_id=0x1001, version=1, zone=1, node=1)
        wait_with_heartbeat(ctrl, 3)

        print('[S09:40s] Node2 lyric + Node1 FIRE', flush=True)
        set_pair_bg(ctrl, 'FIRE', 'OFF', trans_ms=300)
        wait_with_heartbeat(ctrl, 0.5)
        set_pair_bg(ctrl, 'OFF', 'FIRE', trans_ms=300)
        wait_with_heartbeat(ctrl, 0.5)
        ctrl.send_ctrl(bg='FIRE', dimmer=8, text_mode='OFF', trans_ms=0, zone=1, node=1)
        ctrl.send_ctrl(bg='OFF', dimmer=8, text_mode='LYRICS', trans_ms=0, zone=1, node=2)
        ctrl.send_lyrics_line('Lyrics 1234', song_id=0x1001, version=2, zone=1, node=2)
        wait_with_heartbeat(ctrl, 3)

        print('[S10:44s] STARFIELD background', flush=True)
        ctrl.send_ctrl(bg='STARFIELD', dimmer=8, text_mode='OFF', trans_ms=2500, zone=0, node=0)
        wait_with_heartbeat(ctrl, 1)

        print('[S10.5:45s] Rapid STARFIELD ON/OFF alternation', flush=True)
        for _ in range(10):
            set_pair_bg(ctrl, 'STARFIELD', 'OFF', trans_ms=120)
            wait_with_heartbeat(ctrl, 0.15)
            set_pair_bg(ctrl, 'OFF', 'STARFIELD', trans_ms=120)
            wait_with_heartbeat(ctrl, 0.15)

        print('[S11:48s] Node1 WOW! (lyrics fade-in) + Node2 STARFIELD', flush=True)
        ctrl.send_ctrl(bg='STARFIELD', dimmer=8, text_mode='LYRICS',
                       bg_out_fx='FADE', text_in_fx='FADE',
                       trans_ms=0, zone=1, node=1)
        ctrl.send_ctrl(bg='STARFIELD', dimmer=8, text_mode='OFF',
                       trans_ms=0, zone=1, node=2)
        ctrl.send_lyrics_line('Lyrics WOW!', song_id=0x1002, version=3, zone=1, node=1)
        wait_with_heartbeat(ctrl, 3)

        print('[S12:51s] STARFIELD fade out', flush=True)
        ctrl.send_ctrl(bg='STARFIELD', dimmer=8, text_mode='OFF', trans_ms=2500, zone=0, node=0)
        wait_with_heartbeat(ctrl, 4)

        print('[S13:54s] Thank You message', flush=True)
        ctrl.send_ctrl(bg='OFF', dimmer=8, text_mode='OFF', trans_ms=1000, zone=0, node=0)
        ctrl.send_text_custom('Thank You!', zone=0, node=0)
        wait_with_heartbeat(ctrl, 3)

        print('[S14:57s] Node-specific goodbye message (fade in/out)', flush=True)
        ctrl.send_ctrl(bg='OFF', dimmer=8, text_mode='CUSTOM',
                   text_in_fx='FADE', text_out_fx='FADE',
                   trans_ms=0, zone=1, node=1)
        ctrl.send_ctrl(bg='OFF', dimmer=8, text_mode='CUSTOM',
                   text_in_fx='FADE', text_out_fx='FADE',
                   trans_ms=0, zone=1, node=2)
        ctrl.send_text_custom('See you again!', zone=1, node=1)
        ctrl.send_text_custom('Bye Bye!', zone=1, node=2)
        wait_with_heartbeat(ctrl, 3)

        print('[S15:60s] Black Out', flush=True)
        ctrl.send_ctrl(bg='OFF', dimmer=0, text_mode='OFF', trans_ms=500, zone=0, node=0)
        wait_with_heartbeat(ctrl, 2)

        print('========== テスト完了 ==========', flush=True)
    finally:
        ctrl.close()


if __name__ == '__main__':
    main()