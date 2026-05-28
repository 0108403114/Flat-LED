#!/usr/bin/env python3
"""
mobile_ble_sequence.py
======================
Bluetooth LE sender for SAT UDP Ver 3.0 payloads.

This script sends SAT packets over BLE GATT write to the LED node firmware
built with USE_BLE_BRIDGE=1.

Requirements:
  pip install bleak

Example:
  python mobile_ble_sequence.py --address XX:XX:XX:XX:XX:XX
"""

import argparse
import asyncio
import sys

try:
    from bleak import BleakClient
except ImportError as exc:
    raise SystemExit("bleak is required: pip install bleak") from exc

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

FX_CUT = 0
FX_FADE = 1

CONTENT_LYRICS = 0x05

BLE_RX_CHAR_UUID = "a0f00002-8c3d-4f70-9f2a-9a11444a0001"

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


def build_ctrl(zone: int, node: int, dimmer: int, bg: int, text_mode: int,
               bg_in_fx: int = FX_CUT, bg_out_fx: int = FX_CUT,
               text_in_fx: int = FX_CUT, text_out_fx: int = FX_CUT,
               trans_ms: int = 0, scene_id: int = SCENE_NONE) -> bytes:
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
    buf[20] = scene_id & 0xFF
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


async def send_packet(client: BleakClient, packet: bytes) -> None:
    await client.write_gatt_char(BLE_RX_CHAR_UUID, packet, response=False)


async def wait_s(client: BleakClient, seconds: float, hb_every: float = 1.5) -> None:
    end_t = asyncio.get_running_loop().time() + max(0.0, seconds)
    next_hb = 0.0
    while True:
        now = asyncio.get_running_loop().time()
        if now >= end_t:
            return
        if now >= next_hb:
            await send_packet(client, build_heartbeat())
            next_hb = now + hb_every
        await asyncio.sleep(min(0.05, end_t - now))


async def run_30s_sequence(client: BleakClient, song_id: int) -> None:
    print("[00.0] S01 OCEAN + LYRICS mode")
    await send_packet(client, build_ctrl(0, 0, 8, BG_OCEAN, TEXT_LYRICS, trans_ms=500))
    await wait_s(client, 1.0)

    print("[01.0] Lyrics #1 (Node1)")
    await send_packet(client, build_ctrl(1, 1, 8, BG_OCEAN, TEXT_LYRICS, text_in_fx=FX_FADE, trans_ms=0))
    await send_packet(client, build_lyrics(1, 1, "HELLO TOKYO", song_id, 1))
    await wait_s(client, 4.0)

    print("[05.0] Lyrics #2 (Node2)")
    await send_packet(client, build_ctrl(1, 2, 8, BG_OCEAN, TEXT_LYRICS, text_in_fx=FX_FADE, trans_ms=0))
    await send_packet(client, build_lyrics(1, 2, "WE START NOW", song_id, 2))
    await wait_s(client, 5.0)

    print("[10.0] STARFIELD switch")
    await send_packet(client, build_ctrl(0, 0, 8, BG_STARFIELD, TEXT_OFF, trans_ms=1200))
    await wait_s(client, 2.0)

    print("[12.0] Lyrics #3 (Node1)")
    await send_packet(client, build_ctrl(1, 1, 8, BG_STARFIELD, TEXT_LYRICS,
                                         bg_out_fx=FX_FADE, text_in_fx=FX_FADE, trans_ms=0))
    await send_packet(client, build_lyrics(1, 1, "LIGHT THE SKY", song_id, 3))
    await wait_s(client, 6.0)

    print("[18.0] FIRE switch")
    await send_packet(client, build_ctrl(0, 0, 8, BG_FIRE, TEXT_OFF, trans_ms=700))
    await wait_s(client, 2.0)

    print("[20.0] Lyrics #4 (Node2)")
    await send_packet(client, build_ctrl(1, 2, 8, BG_FIRE, TEXT_LYRICS, text_in_fx=FX_FADE, trans_ms=0))
    await send_packet(client, build_lyrics(1, 2, "FEEL THE BEAT", song_id, 4))
    await wait_s(client, 5.0)

    print("[25.0] Final phrase")
    await send_packet(client, build_ctrl(0, 0, 8, BG_OFF, TEXT_LYRICS, text_in_fx=FX_FADE, trans_ms=300))
    await send_packet(client, build_lyrics(0, 0, "THANK YOU", song_id, 5))
    await wait_s(client, 3.0)

    print("[28.0] OFF")
    await send_packet(client, build_ctrl(0, 0, 0, BG_OFF, TEXT_OFF, trans_ms=500))
    await wait_s(client, 2.0)


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="BLE SAT packet sender (30s demo)")
    p.add_argument("--address", required=True, help="BLE MAC address of target node")
    p.add_argument("--song-id", default="0x1201", help="Song ID (hex/decimal)")
    return p.parse_args(argv)


def parse_song_id(v: str) -> int:
    v = v.strip().lower()
    if v.startswith("0x"):
        return int(v, 16)
    return int(v, 10)


async def amain(args: argparse.Namespace) -> int:
    song_id = parse_song_id(args.song_id)
    print(f"connect: {args.address}")

    async with BleakClient(args.address) as client:
        if not client.is_connected:
            print("BLE connection failed")
            return 2
        print("connected")
        await run_30s_sequence(client, song_id)

    print("done")
    return 0


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    return asyncio.run(amain(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
