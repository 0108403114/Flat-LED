#!/usr/bin/env python3
"""
mobile_ble_controller_app.py
============================
Interactive BLE controller app for smartphone/PC Python runtime.

Features:
- Scan BLE devices
- Connect to one or more LED nodes
- Send HEARTBEAT / CTRL / LYRICS
- Run built-in 30s demo sequence

Requirements:
  pip install bleak

Quick start:
  python tools/mobile_ble_controller_app.py
"""

import asyncio
import sys
from typing import Dict, List

try:
    from bleak import BleakClient, BleakScanner
except ImportError as exc:
    raise SystemExit("bleak is required. Install with: pip install bleak") from exc

SIGNATURE = 0x53
PKT_CTRL = 0x10
PKT_CONTENT = 0x20
PKT_HEARTBEAT = 0x40

CTRL_SIZE = 25
CONTENT_SIZE = 60
HEARTBEAT_SIZE = 8
CONTENT_TEXT_MAX = 48

BG_OFF = 0
BG_FIRE = 3
BG_OCEAN = 4
BG_STARFIELD = 5

TEXT_OFF = 0
TEXT_LYRICS = 1

FX_CUT = 0
FX_FADE = 1

CONTENT_LYRICS = 0x05

BLE_SERVICE_UUID = "a0f00001-8c3d-4f70-9f2a-9a11444a0001"
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
               trans_ms: int = 0) -> bytes:
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


async def ainput(prompt: str) -> str:
    return await asyncio.to_thread(input, prompt)


async def scan_devices(timeout_s: float = 5.0):
    print(f"[scan] searching {timeout_s:.1f}s...")
    devices = await BleakScanner.discover(timeout=timeout_s)
    if not devices:
        print("[scan] no devices found")
        return
    for i, d in enumerate(devices, start=1):
        name = d.name or "(no-name)"
        print(f"  {i:02d}. {name}  {d.address}")


def connected_clients(clients: Dict[str, BleakClient]) -> List[BleakClient]:
    return [c for c in clients.values() if c.is_connected]


async def send_packet_all(clients: Dict[str, BleakClient], packet: bytes) -> None:
    active = connected_clients(clients)
    if not active:
        print("[send] no connected client")
        return

    for c in active:
        await c.write_gatt_char(BLE_RX_CHAR_UUID, packet, response=False)


async def connect_device(clients: Dict[str, BleakClient], address: str) -> None:
    address = address.strip()
    if not address:
        return

    if address in clients and clients[address].is_connected:
        print(f"[connect] already connected: {address}")
        return

    client = BleakClient(address)
    await client.connect()
    if client.is_connected:
        clients[address] = client
        print(f"[connect] ok: {address}")
    else:
        print(f"[connect] failed: {address}")


async def disconnect_device(clients: Dict[str, BleakClient], address: str) -> None:
    address = address.strip()
    if not address:
        return

    client = clients.get(address)
    if not client:
        print(f"[disconnect] not found: {address}")
        return

    if client.is_connected:
        await client.disconnect()
    clients.pop(address, None)
    print(f"[disconnect] done: {address}")


async def disconnect_all(clients: Dict[str, BleakClient]) -> None:
    for addr, client in list(clients.items()):
        if client.is_connected:
            await client.disconnect()
        clients.pop(addr, None)
    print("[disconnect] all done")


async def send_quick_ctrl(clients: Dict[str, BleakClient]) -> None:
    bg_map = {
        "OFF": BG_OFF,
        "OCEAN": BG_OCEAN,
        "FIRE": BG_FIRE,
        "STARFIELD": BG_STARFIELD,
    }

    bg_name = (await ainput("BG [OFF/OCEAN/FIRE/STARFIELD]: ")).strip().upper() or "OFF"
    bg = bg_map.get(bg_name, BG_OFF)
    dimmer_txt = (await ainput("Dimmer 0-255 [8]: ")).strip() or "8"
    trans_txt = (await ainput("Transition ms [500]: ")).strip() or "500"

    try:
        dimmer = max(0, min(255, int(dimmer_txt)))
        trans_ms = max(0, int(trans_txt))
    except ValueError:
        print("[ctrl] invalid number")
        return

    pkt = build_ctrl(0, 0, dimmer=dimmer, bg=bg, text_mode=TEXT_OFF, trans_ms=trans_ms)
    await send_packet_all(clients, pkt)
    print(f"[ctrl] sent bg={bg_name} dim={dimmer} trans={trans_ms}ms")


async def send_lyrics_once(clients: Dict[str, BleakClient]) -> None:
    target = (await ainput("Target [1/2/G]: ")).strip().upper() or "G"
    text = (await ainput("Lyrics text: ")).strip()
    if not text:
        print("[lyrics] empty text")
        return

    version_txt = (await ainput("Version [1]: ")).strip() or "1"
    try:
        version = int(version_txt)
    except ValueError:
        print("[lyrics] invalid version")
        return

    if target == "1":
        zone, node = 1, 1
    elif target == "2":
        zone, node = 1, 2
    else:
        zone, node = 0, 0

    pkt_ctrl = build_ctrl(zone, node, dimmer=8, bg=BG_OFF, text_mode=TEXT_LYRICS,
                          text_in_fx=FX_FADE, trans_ms=0)
    pkt_lyrics = build_lyrics(zone, node, text, song_id=0x1201, version=version)

    await send_packet_all(clients, pkt_ctrl)
    await send_packet_all(clients, pkt_lyrics)
    print(f"[lyrics] sent target={target} text='{text}' version={version}")


async def wait_with_hb(clients: Dict[str, BleakClient], seconds: float, hb_every: float = 1.5) -> None:
    end_t = asyncio.get_running_loop().time() + max(0.0, seconds)
    next_hb = 0.0
    while True:
        now = asyncio.get_running_loop().time()
        if now >= end_t:
            return
        if now >= next_hb:
            await send_packet_all(clients, build_heartbeat())
            next_hb = now + hb_every
        await asyncio.sleep(min(0.05, end_t - now))


async def run_30s_sequence(clients: Dict[str, BleakClient]) -> None:
    if not connected_clients(clients):
        print("[seq] no connected client")
        return

    print("[00.0] OCEAN + LYRICS mode")
    await send_packet_all(clients, build_ctrl(0, 0, 8, BG_OCEAN, TEXT_LYRICS, trans_ms=500))
    await wait_with_hb(clients, 1.0)

    print("[01.0] Lyrics #1 Node1")
    await send_packet_all(clients, build_ctrl(1, 1, 8, BG_OCEAN, TEXT_LYRICS, text_in_fx=FX_FADE, trans_ms=0))
    await send_packet_all(clients, build_lyrics(1, 1, "HELLO TOKYO", 0x1201, 1))
    await wait_with_hb(clients, 4.0)

    print("[05.0] Lyrics #2 Node2")
    await send_packet_all(clients, build_ctrl(1, 2, 8, BG_OCEAN, TEXT_LYRICS, text_in_fx=FX_FADE, trans_ms=0))
    await send_packet_all(clients, build_lyrics(1, 2, "WE START NOW", 0x1201, 2))
    await wait_with_hb(clients, 5.0)

    print("[10.0] STARFIELD")
    await send_packet_all(clients, build_ctrl(0, 0, 8, BG_STARFIELD, TEXT_OFF, trans_ms=1200))
    await wait_with_hb(clients, 2.0)

    print("[12.0] Lyrics #3 Node1")
    await send_packet_all(clients, build_ctrl(1, 1, 8, BG_STARFIELD, TEXT_LYRICS,
                                              bg_out_fx=FX_FADE, text_in_fx=FX_FADE, trans_ms=0))
    await send_packet_all(clients, build_lyrics(1, 1, "LIGHT THE SKY", 0x1201, 3))
    await wait_with_hb(clients, 6.0)

    print("[18.0] FIRE")
    await send_packet_all(clients, build_ctrl(0, 0, 8, BG_FIRE, TEXT_OFF, trans_ms=700))
    await wait_with_hb(clients, 2.0)

    print("[20.0] Lyrics #4 Node2")
    await send_packet_all(clients, build_ctrl(1, 2, 8, BG_FIRE, TEXT_LYRICS, text_in_fx=FX_FADE, trans_ms=0))
    await send_packet_all(clients, build_lyrics(1, 2, "FEEL THE BEAT", 0x1201, 4))
    await wait_with_hb(clients, 5.0)

    print("[25.0] Final phrase")
    await send_packet_all(clients, build_ctrl(0, 0, 8, BG_OFF, TEXT_LYRICS, text_in_fx=FX_FADE, trans_ms=300))
    await send_packet_all(clients, build_lyrics(0, 0, "THANK YOU", 0x1201, 5))
    await wait_with_hb(clients, 3.0)

    print("[28.0] OFF")
    await send_packet_all(clients, build_ctrl(0, 0, 0, BG_OFF, TEXT_OFF, trans_ms=500))
    await wait_with_hb(clients, 2.0)

    print("[seq] done")


def show_menu(clients: Dict[str, BleakClient]) -> None:
    active = connected_clients(clients)
    print("\n=== Mobile BLE Controller ===")
    print(f"Connected: {len(active)}")
    for c in active:
        print(f"  - {c.address}")
    print("1) Scan BLE devices")
    print("2) Connect device")
    print("3) Disconnect device")
    print("4) Send HEARTBEAT now")
    print("5) Send quick CTRL (BG/dimmer)")
    print("6) Send one LYRICS")
    print("7) Run 30s test sequence")
    print("8) Send OFF")
    print("9) Disconnect all")
    print("q) Quit")


async def app_main() -> int:
    clients: Dict[str, BleakClient] = {}
    print(f"Service UUID: {BLE_SERVICE_UUID}")
    print(f"RX Char UUID: {BLE_RX_CHAR_UUID}")

    try:
        while True:
            show_menu(clients)
            cmd = (await ainput("Select: ")).strip().lower()

            if cmd == "1":
                await scan_devices(5.0)
            elif cmd == "2":
                addr = (await ainput("BLE address: ")).strip()
                await connect_device(clients, addr)
            elif cmd == "3":
                addr = (await ainput("BLE address to disconnect: ")).strip()
                await disconnect_device(clients, addr)
            elif cmd == "4":
                await send_packet_all(clients, build_heartbeat())
                print("[hb] sent")
            elif cmd == "5":
                await send_quick_ctrl(clients)
            elif cmd == "6":
                await send_lyrics_once(clients)
            elif cmd == "7":
                await run_30s_sequence(clients)
            elif cmd == "8":
                await send_packet_all(clients, build_ctrl(0, 0, 0, BG_OFF, TEXT_OFF, trans_ms=300))
                print("[off] sent")
            elif cmd == "9":
                await disconnect_all(clients)
            elif cmd == "q":
                break
            else:
                print("Unknown command")
    finally:
        await disconnect_all(clients)

    return 0


def main() -> int:
    return asyncio.run(app_main())


if __name__ == "__main__":
    raise SystemExit(main())
