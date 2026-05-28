#!/usr/bin/env python3
"""
mobile_direct_sequence.py
=========================
Phone-only sender for SAT UDP Ver 3.0 demo.

Purpose:
- Run from Android phone (Termux / Pydroid) and send a 30s demo sequence directly to LED nodes.
- No TouchDesigner required.
- Uses only Python standard library.

Usage examples:
  python mobile_direct_sequence.py
  python mobile_direct_sequence.py --group 239.255.0.1 --port 6454
  python mobile_direct_sequence.py --ttl 2 --song-id 0x1201
"""

import argparse
import socket
import sys
import time

# Protocol constants
SIGNATURE = 0x53
PKT_CTRL = 0x10
PKT_CONTENT = 0x20
PKT_HEARTBEAT = 0x40

CTRL_SIZE = 25
CONTENT_SIZE = 60
HEARTBEAT_SIZE = 8
CONTENT_TEXT_MAX = 48

SCENE_NONE = 0

BG_OFF = 0
BG_FIRE = 3
BG_OCEAN = 4
BG_STARFIELD = 5

TEXT_OFF = 0
TEXT_LYRICS = 1
TEXT_CUSTOM = 5

FX_CUT = 0
FX_FADE = 1

CONTENT_LYRICS = 0x05

DEFAULT_GROUP = "239.255.0.1"
DEFAULT_PORT = 6454

_seq = 0


def crc8_maxim(data: bytes) -> int:
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8C if (crc & 1) else (crc >> 1)
    return crc


def next_seq() -> int:
    global _seq
    _seq = (_seq + 1) & 0xFF
    return _seq


def nid(zone: int, node: int) -> bytes:
    return bytes([zone & 0xFF, (node >> 8) & 0xFF, node & 0xFF])


def build_ctrl(zone: int, node: int,
               dimmer: int,
               bg: int,
               text_mode: int,
               bg_in_fx: int = FX_CUT,
               bg_out_fx: int = FX_CUT,
               text_in_fx: int = FX_CUT,
               text_out_fx: int = FX_CUT,
               trans_ms: int = 0,
               scene_id: int = SCENE_NONE) -> bytes:
    n = nid(zone, node)
    buf = bytearray(CTRL_SIZE)
    buf[0] = SIGNATURE
    buf[1] = PKT_CTRL
    buf[2] = 0x03
    buf[3] = n[0]
    buf[4] = n[1]
    buf[5] = n[2]
    buf[6] = dimmer & 0xFF
    buf[7] = bg & 0xFF
    buf[8] = bg_in_fx & 0xFF
    buf[9] = bg_out_fx & 0xFF
    buf[10] = text_mode & 0xFF
    buf[11] = text_in_fx & 0xFF
    buf[12] = text_out_fx & 0xFF
    buf[13] = (trans_ms >> 8) & 0xFF
    buf[14] = trans_ms & 0xFF
    # execute_at_ms [15-18] = 0
    # flags [19] = 0
    buf[20] = scene_id & 0xFF
    # reserved [21-22] = 0
    buf[23] = next_seq()
    buf[24] = crc8_maxim(buf[:24])
    return bytes(buf)


def build_lyrics(zone: int, node: int, text: str, song_id: int, version: int) -> bytes:
    payload = f"S{song_id:04X}|V{version:02d}|C01/01|{text}"
    encoded = payload.encode("ascii", errors="replace")[:CONTENT_TEXT_MAX]

    n = nid(zone, node)
    buf = bytearray(CONTENT_SIZE)
    buf[0] = SIGNATURE
    buf[1] = PKT_CONTENT
    buf[2] = 0x03
    buf[3] = n[0]
    buf[4] = n[1]
    buf[5] = n[2]
    buf[6] = CONTENT_LYRICS
    buf[7] = 0
    buf[8] = 0
    buf[9] = 0
    buf[10] = len(encoded)
    buf[11:11 + len(encoded)] = encoded
    buf[59] = crc8_maxim(buf[:59])
    return bytes(buf)


def build_heartbeat() -> bytes:
    buf = bytearray(HEARTBEAT_SIZE)
    buf[0] = SIGNATURE
    buf[1] = PKT_HEARTBEAT
    buf[2] = 0x03
    buf[7] = crc8_maxim(buf[:7])
    return bytes(buf)


class Sender:
    def __init__(self, targets: list[str], port: int, ttl: int):
        self.targets = [t.strip() for t in targets if t.strip()]
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)

    def send(self, data: bytes) -> None:
        for target in self.targets:
            self.sock.sendto(data, (target, self.port))

    def close(self) -> None:
        self.sock.close()


def send_hb_every(sender: Sender, next_hb_ref: dict, interval_s: float = 1.5) -> None:
    now = time.time()
    if now >= next_hb_ref["t"]:
        sender.send(build_heartbeat())
        next_hb_ref["t"] = now + interval_s


def wait_s(sender: Sender, seconds: float, next_hb_ref: dict) -> None:
    end_t = time.time() + max(0.0, seconds)
    while True:
        now = time.time()
        if now >= end_t:
            return
        send_hb_every(sender, next_hb_ref)
        time.sleep(min(0.05, end_t - now))


def run_30s_sequence(sender: Sender, song_id: int) -> None:
    next_hb_ref = {"t": time.time()}

    print("[00.0] S01 OCEAN + LYRICS mode")
    sender.send(build_ctrl(0, 0, dimmer=8, bg=BG_OCEAN, text_mode=TEXT_LYRICS, trans_ms=500))
    wait_s(sender, 1.0, next_hb_ref)

    print("[01.0] Lyrics #1 (Node1)")
    sender.send(build_ctrl(1, 1, dimmer=8, bg=BG_OCEAN, text_mode=TEXT_LYRICS, text_in_fx=FX_FADE, trans_ms=0))
    sender.send(build_lyrics(1, 1, "HELLO TOKYO", song_id=song_id, version=1))
    wait_s(sender, 4.0, next_hb_ref)

    print("[05.0] Lyrics #2 (Node2)")
    sender.send(build_ctrl(1, 2, dimmer=8, bg=BG_OCEAN, text_mode=TEXT_LYRICS, text_in_fx=FX_FADE, trans_ms=0))
    sender.send(build_lyrics(1, 2, "WE START NOW", song_id=song_id, version=2))
    wait_s(sender, 5.0, next_hb_ref)

    print("[10.0] STARFIELD switch")
    sender.send(build_ctrl(0, 0, dimmer=8, bg=BG_STARFIELD, text_mode=TEXT_OFF, trans_ms=1200))
    wait_s(sender, 2.0, next_hb_ref)

    print("[12.0] Lyrics #3 (Node1, fade + left scroll)")
    sender.send(build_ctrl(1, 1, dimmer=8, bg=BG_STARFIELD, text_mode=TEXT_LYRICS,
                           bg_out_fx=FX_FADE, text_in_fx=FX_FADE, trans_ms=0))
    sender.send(build_lyrics(1, 1, "LIGHT THE SKY", song_id=song_id, version=3))
    wait_s(sender, 6.0, next_hb_ref)

    print("[18.0] FIRE switch")
    sender.send(build_ctrl(0, 0, dimmer=8, bg=BG_FIRE, text_mode=TEXT_OFF, trans_ms=700))
    wait_s(sender, 2.0, next_hb_ref)

    print("[20.0] Lyrics #4 (Node2)")
    sender.send(build_ctrl(1, 2, dimmer=8, bg=BG_FIRE, text_mode=TEXT_LYRICS, text_in_fx=FX_FADE, trans_ms=0))
    sender.send(build_lyrics(1, 2, "FEEL THE BEAT", song_id=song_id, version=4))
    wait_s(sender, 5.0, next_hb_ref)

    print("[25.0] Final phrase (Global)")
    sender.send(build_ctrl(0, 0, dimmer=8, bg=BG_OFF, text_mode=TEXT_LYRICS, text_in_fx=FX_FADE, trans_ms=300))
    sender.send(build_lyrics(0, 0, "THANK YOU", song_id=song_id, version=5))
    wait_s(sender, 3.0, next_hb_ref)

    print("[28.0] OFF")
    sender.send(build_ctrl(0, 0, dimmer=0, bg=BG_OFF, text_mode=TEXT_OFF, trans_ms=500))
    wait_s(sender, 2.0, next_hb_ref)


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Phone-only SAT UDP 30s sequence sender")
    p.add_argument("--target", default=DEFAULT_GROUP,
                   help="Destination IP(s). Use one IP for multicast or comma-separated IPs for unicast. Example: 239.255.0.1 or 192.168.0.31,192.168.0.32")
    p.add_argument("--port", default=DEFAULT_PORT, type=int, help="UDP port (default: 6454)")
    p.add_argument("--ttl", default=2, type=int, help="Multicast TTL")
    p.add_argument("--song-id", default="0x1201", help="Song ID in hex or decimal")
    return p.parse_args(argv)


def parse_song_id(v: str) -> int:
    v = v.strip().lower()
    if v.startswith("0x"):
        return int(v, 16)
    return int(v, 10)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    song_id = parse_song_id(args.song_id)
    targets = [t.strip() for t in args.target.split(",") if t.strip()]

    sender = Sender(targets, args.port, args.ttl)
    print(f"[mobile_direct_sequence] send to {','.join(targets)}:{args.port} ttl={args.ttl}")

    try:
        run_30s_sequence(sender, song_id)
        print("[mobile_direct_sequence] done")
        return 0
    except KeyboardInterrupt:
        print("[mobile_direct_sequence] interrupted")
        return 130
    finally:
        sender.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
