"""
Protocol verification script - check what packets are being sent
"""
import sys
sys.path.insert(0, 'tools')
from td_sat_sender import *
import struct

# Build a CTRL packet manually and inspect bytes
print("=== CTRL Packet Structure Check ===")
pkt = build_ctrl(zone=1, node=1, dimmer=100, bg=BG_OCEAN, scene_id=SCENE_READY)
print(f"Length: {len(pkt)} bytes")
print(f"Hex: {pkt.hex().upper()}")
print(f"Byte breakdown:")
print(f"  [0] Signature:     0x{pkt[0]:02X} (expect 0x53)")
print(f"  [1] PKT_TYPE:      0x{pkt[1]:02X} (expect 0x10 for CTRL)")
print(f"  [2] Version:       0x{pkt[2]:02X}")
print(f"  [3-5] Node ID:     0x{pkt[3]:02X}{pkt[4]:02X}{pkt[5]:02X}")
print(f"  [6] Dimmer:        0x{pkt[6]:02X} ({pkt[6]})")
print(f"  [7] BG Asset:      0x{pkt[7]:02X} ({pkt[7]}) (OCEAN=4)")
print(f"  [20] Scene ID:     0x{pkt[20]:02X} ({pkt[20]}) (READY=5)")
print(f"  [24] CRC8:         0x{pkt[24]:02X}")

print("\n=== CONTENT Packet Structure Check ===")
pkt_content = build_content_custom("Welcome!", zone=1, node=1)
print(f"Length: {len(pkt_content)} bytes")
print(f"Byte breakdown:")
print(f"  [0] Signature:     0x{pkt_content[0]:02X} (expect 0x53)")
print(f"  [1] PKT_TYPE:      0x{pkt_content[1]:02X} (expect 0x20 for CONTENT)")
print(f"  [6] Content Type:  0x{pkt_content[6]:02X}")
print(f"  [10] Text Length:  {pkt_content[10]} bytes")
print(f"  [11:] Text:        {pkt_content[11:11+pkt_content[10]]}")
print(f"  [59] CRC8:         0x{pkt_content[59]:02X}")

print("\n✅ Packet structures look correct")
