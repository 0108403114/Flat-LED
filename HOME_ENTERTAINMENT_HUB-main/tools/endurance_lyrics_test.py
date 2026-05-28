#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import time

from led_udp_test_tool import (
    SAT_CONTENT_LYRICS,
    SAT_TEXT_LYRICS,
    SAT_BG_FIRE,
    SatUdpSender,
    SatV3ContentPacket,
    SatV3CtrlPacket,
    _build_lyrics_chunk_text,
)


def send_ctrl(sender: SatUdpSender, zone: int, node: int, dimmer: int, bg: int, text_mode: int) -> None:
    pkt = SatV3CtrlPacket(zone=zone, node=node)
    pkt.dimmer = dimmer
    pkt.bg_asset = bg
    pkt.text_mode = text_mode
    pkt.trans_ms = 0
    sender.send_raw(pkt.encode())


def send_lyrics_single_chunk(
    sender: SatUdpSender,
    zone: int,
    node: int,
    song_id: int,
    version: int,
    text: str,
) -> None:
    payload = _build_lyrics_chunk_text(song_id, version, 1, 1, text)
    pkt = SatV3ContentPacket(zone=zone, node=node)
    pkt.content_type = SAT_CONTENT_LYRICS
    pkt.slot = 0
    pkt.duration_ms = 0
    pkt.text = payload
    sender.send_raw(pkt.encode())


def run_test(duration_min: int, zone: int, node_a: int, node_b: int, interval_ms: int) -> int:
    total_seconds = duration_min * 60
    interval_s = max(0.05, interval_ms / 1000.0)

    sender = SatUdpSender()
    start = time.monotonic()
    next_ctrl = start

    print(f"[START] endurance test {duration_min} min, zone={zone}, nodes=({node_a},{node_b}), interval={interval_ms}ms", flush=True)

    try:
        for minute in range(duration_min):
            elapsed_min = minute + 1
            version = elapsed_min
            # ノード側は 5x8 フォントで約14文字までしか表示できないため、
            # 分情報を先頭に短縮して必ず見えるようにする。
            line = f"M{elapsed_min:02d}/{duration_min:02d} STAB"

            # 1分ごとに歌詞更新 (2ノードへ個別送信)
            send_lyrics_single_chunk(sender, zone, node_a, song_id=0x005A, version=version, text=line)
            send_lyrics_single_chunk(sender, zone, node_b, song_id=0x005A, version=version, text=line)

            now_elapsed = int(time.monotonic() - start)
            print(f"[PROGRESS] minute={elapsed_min}/{duration_min} elapsed={now_elapsed}s lyrics='{line}'", flush=True)

            minute_end = start + (elapsed_min * 60)
            while True:
                now = time.monotonic()
                if now >= minute_end:
                    break

                if now >= next_ctrl:
                    # HEARTBEAT相当: CTRLを継続送信してsafe modeを回避
                    send_ctrl(sender, zone, node_a, dimmer=180, bg=SAT_BG_FIRE, text_mode=SAT_TEXT_LYRICS)
                    send_ctrl(sender, zone, node_b, dimmer=180, bg=SAT_BG_FIRE, text_mode=SAT_TEXT_LYRICS)
                    next_ctrl += interval_s

                # ビジー待機を避ける
                time.sleep(0.01)

        print("[DONE] endurance test completed", flush=True)
        return 0

    except KeyboardInterrupt:
        print("[ABORT] interrupted by user", flush=True)
        return 130

    finally:
        # 終了時は消灯
        try:
            send_ctrl(sender, zone, node_a, dimmer=0, bg=0, text_mode=0)
            send_ctrl(sender, zone, node_b, dimmer=0, bg=0, text_mode=0)
            print("[CLEANUP] sent OFF to both nodes", flush=True)
        except Exception as ex:
            print(f"[WARN] cleanup failed: {ex}", flush=True)
        sender.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="30分耐久: 1分ごと歌詞更新 + 継続CTRL送信")
    parser.add_argument("--duration-min", type=int, default=30, help="試験時間(分), デフォルト=30")
    parser.add_argument("--zone", type=int, default=1, help="Zone ID, デフォルト=1")
    parser.add_argument("--node-a", type=int, default=1, help="Node A, デフォルト=1")
    parser.add_argument("--node-b", type=int, default=2, help="Node B, デフォルト=2")
    parser.add_argument("--interval-ms", type=int, default=400, help="CTRL送信間隔ms, デフォルト=400")
    args = parser.parse_args()

    raise SystemExit(run_test(args.duration_min, args.zone, args.node_a, args.node_b, args.interval_ms))
