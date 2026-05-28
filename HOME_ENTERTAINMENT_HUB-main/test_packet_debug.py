#!/usr/bin/env python3
import sys
sys.path.insert(0, 'tools')
from td_sat_sender import TdLedController, build_ctrl, SCENE_READY, SCENE_EVENT_1, SCENE_FIREWORKS

ctrl = TdLedController()

# Test: Build READY CTRL packet with zone=1, node=2
print("=== READY packet (zone=1, node=2) ===")
pkt = build_ctrl(zone=1, node=2, scene_id=SCENE_READY)
print(f'Packet length: {len(pkt)}')
print(f'Packet bytes: {" ".join(f"{b:02x}" for b in pkt)}')
print()
print(f'[0] signature: 0x{pkt[0]:02x}')
print(f'[1] type: 0x{pkt[1]:02x}')
print(f'[3-5] node_id: 0x{pkt[3]:02x}{pkt[4]:02x}{pkt[5]:02x}')
print(f'[6] dimmer: {pkt[6]}')
print(f'[7] bg: {pkt[7]}')
print(f'[10] text_mode: {pkt[10]}')
print(f'[20] scene_id: {pkt[20]}')
print(f'[24] crc: 0x{pkt[24]:02x}')
print()

# Test: Build EVENT_1 CTRL packet with zone=1, node=2
print("=== EVENT_1 packet (zone=1, node=2) ===")
pkt = build_ctrl(zone=1, node=2, scene_id=SCENE_EVENT_1)
print(f'Packet length: {len(pkt)}')
print(f'[7] bg: {pkt[7]}')
print(f'[10] text_mode: {pkt[10]}')
print(f'[20] scene_id: {pkt[20]}')
print()

# Test: Build FIREWORKS CTRL packet with zone=1, node=2
print("=== FIREWORKS packet (zone=1, node=2) ===")
pkt = build_ctrl(zone=1, node=2, scene_id=SCENE_FIREWORKS)
print(f'Packet length: {len(pkt)}')
print(f'[7] bg: {pkt[7]}')
print(f'[10] text_mode: {pkt[10]}')
print(f'[20] scene_id: {pkt[20]}')

ctrl.close()
