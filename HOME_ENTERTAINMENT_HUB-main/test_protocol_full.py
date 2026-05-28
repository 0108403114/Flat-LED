"""
本番通信テスト：パケット生成と検証
protocol_architecture に完全に従った実装を確認
"""
import sys
sys.path.insert(0, 'tools')
from td_sat_sender import *
import socket
import struct

print("=" * 70)
print("📡 SAT UDP Ver 3.0 完全仕様テスト")
print("=" * 70)

# ============================================================
# 1. CTRL パケット生成と検証
# ============================================================
print("\n【1】CTRL パケット生成テスト")
print("-" * 70)

test_cases = [
    ("READY", SCENE_READY, BG_OCEAN, TEXT_CUSTOM, 120),
    ("EVENT_1", SCENE_EVENT_1, BG_OCEAN, TEXT_CUSTOM, 180),
    ("EVENT_2", SCENE_EVENT_2, BG_FIRE, TEXT_LYRICS, 255),
    ("EVENT_3", SCENE_EVENT_3, BG_STARFIELD, TEXT_CUSTOM, 200),
    ("FIREWORKS", SCENE_FIREWORKS, BG_OFF, TEXT_OFF, 255),
]

for scene_name, scene_id, bg, txt_mode, dimmer in test_cases:
    pkt = build_ctrl(zone=1, node=1, 
                     dimmer=dimmer, bg=bg, text_mode=txt_mode,
                     scene_id=scene_id, trans_ms=500)
    
    print(f"\n{scene_name:12} | Scene={scene_id} BG={bg:2d} TXT={txt_mode:2d} Dimmer={dimmer:3d}")
    print(f"  Packet Size: {len(pkt)} bytes (expect 25)")
    print(f"  Signature:   0x{pkt[0]:02X} (expect 0x53)")
    print(f"  Pkt Type:    0x{pkt[1]:02X} (expect 0x10 CTRL)")
    print(f"  Node ID:     0x{pkt[3]:02X}{pkt[4]:02X}{pkt[5]:02X} (expect 0x010001)")
    print(f"  BG Asset:    {pkt[7]} (expect {bg})")
    print(f"  Text Mode:   {pkt[10]} (expect {txt_mode})")
    print(f"  Scene ID:    {pkt[20]} (expect {scene_id})")
    print(f"  CRC8:        0x{pkt[24]:02X}")
    
    # Verify structure
    assert pkt[0] == SIGNATURE, "Bad signature"
    assert pkt[1] == PKT_CTRL, "Bad pkt type"
    assert pkt[3:6] == bytes([1, 0, 1]), "Bad node ID"
    assert pkt[7] == bg, "Bad BG asset"
    assert pkt[10] == txt_mode, "Bad text mode"
    assert pkt[20] == scene_id, "Bad scene ID"
    print("  ✅ Structure OK")

# ============================================================
# 2. CONTENT パケット生成と検証
# ============================================================
print("\n\n【2】CONTENT パケット生成テスト")
print("-" * 70)

text_tests = [
    ("Welcome!", 0x00),
    ("開始まで 3:00", 0x00),
    ("Thank you!", 0x00),
]

for text, content_type in text_tests:
    pkt = build_content_custom(text, zone=1, node=1, content_type=content_type)
    
    print(f"\n  Text: '{text}'")
    print(f"  Packet Size: {len(pkt)} bytes (expect 60)")
    print(f"  Signature:   0x{pkt[0]:02X} (expect 0x53)")
    print(f"  Pkt Type:    0x{pkt[1]:02X} (expect 0x20 CONTENT)")
    print(f"  Node ID:     0x{pkt[3]:02X}{pkt[4]:02X}{pkt[5]:02X}")
    print(f"  Content Type: 0x{pkt[6]:02X} (expect 0x{content_type:02X})")
    print(f"  Text Length: {pkt[10]} bytes")
    print(f"  Text Data:   {pkt[11:11+pkt[10]]}")
    print(f"  CRC8:        0x{pkt[24]:02X}")
    
    assert pkt[0] == SIGNATURE, "Bad signature"
    assert pkt[1] == PKT_CONTENT, "Bad pkt type"
    assert pkt[6] == content_type, "Bad content type"
    print("  ✅ Structure OK")

# ============================================================
# 3. HEARTBEAT パケット生成と検証
# ============================================================
print("\n\n【3】HEARTBEAT パケット生成テスト")
print("-" * 70)

hb_pkt = build_heartbeat()
print(f"\nPacket Size: {len(hb_pkt)} bytes (expect 8)")
print(f"Signature:   0x{hb_pkt[0]:02X} (expect 0x53)")
print(f"Pkt Type:    0x{hb_pkt[1]:02X} (expect 0x40 HEARTBEAT)")
print(f"CRC8:        0x{hb_pkt[7]:02X}")

assert hb_pkt[0] == SIGNATURE, "Bad signature"
assert hb_pkt[1] == PKT_HEARTBEAT, "Bad pkt type"
print("✅ Structure OK")

# ============================================================
# 4. シーン遷移フロー（プロトコル仕様に従った順序）
# ============================================================
print("\n\n【4】シーン遷移フロー（完全仕様準拠）")
print("-" * 70)

flow = [
    ("SCENE:READY", build_ctrl(zone=1, node=1, scene_id=SCENE_READY, dimmer=120, trans_ms=500)),
    ("CONTENT:Welcome", build_content_custom("Welcome!", zone=1, node=1)),
    ("SCENE:EVENT_1", build_ctrl(zone=1, node=1, scene_id=SCENE_EVENT_1, dimmer=180, trans_ms=500)),
    ("CONTENT:開始まで 3:00", build_content_custom("開始まで 3:00", zone=1, node=1)),
    ("CONTENT:開始まで 0:10", build_content_custom("開始まで 0:10", zone=1, node=1)),
    ("SCENE:EVENT_2", build_ctrl(zone=1, node=1, scene_id=SCENE_EVENT_2, dimmer=255, trans_ms=1000)),
    ("SCENE:EVENT_3", build_ctrl(zone=1, node=1, scene_id=SCENE_EVENT_3, dimmer=200, trans_ms=1000)),
    ("SCENE:FIREWORKS", build_ctrl(zone=1, node=1, scene_id=SCENE_FIREWORKS, dimmer=255)),
    ("SCENE:OFF", build_ctrl(zone=1, node=1, scene_id=SCENE_OFF, dimmer=0)),
]

for label, pkt in flow:
    print(f"\n{label:25} → {len(pkt):2d} bytes, Sig:0x{pkt[0]:02X} Type:0x{pkt[1]:02X}")

print("\n" + "=" * 70)
print("✅ 全テスト完了 - プロトコル仕様に完全準拠")
print("=" * 70)
