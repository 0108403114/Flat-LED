#!/usr/bin/env python3
"""
両ノード同時動作テスト
グローバルブロードキャストで両方のノードに同じコマンドを送信
"""
import sys
sys.path.insert(0, 'tools')
from td_sat_sender import TdLedController
import time

ctrl = TdLedController()

print("=" * 70)
print("両ノード同時動作テスト")
print("=" * 70)
print()
print("ネットワークに接続している両方のLEDノードに同時にコマンドを送信します。")
print("両方のLEDストリップが同じように変化するか確認してください。")
print()

# Test 1: READY scene (OCEAN background)
print("[1/5] READY scene を送信...")
print("  期待: 両方のLED が OCEAN 背景 (シアン/青の波状)で点灯")
print("  テキスト: Welcome!")
print()
ctrl.send_scene('READY', zone=0, node=0)
time.sleep(0.3)
ctrl.send_text_custom('Welcome!', zone=0, node=0)
time.sleep(3)

# Test 2: EVENT_1 (OCEAN, brightness up)
print("[2/5] EVENT_1 scene を送信...")
print("  期待: 両方のLED が OCEAN 背景で明るくなる (dim: 120→180)")
print()
ctrl.send_scene('EVENT_1', zone=0, node=0)
time.sleep(3)

# Test 3: EVENT_2 (FIRE background)
print("[3/5] EVENT_2 scene を送信...")
print("  期待: 両方のLED が FIRE 背景 (赤/オレンジの炎)で全明る度 (dim: 255)")
print()
ctrl.send_scene('EVENT_2', zone=0, node=0)
time.sleep(3)

# Test 4: EVENT_3 (STARFIELD background)
print("[4/5] EVENT_3 scene を送信...")
print("  期待: 両方のLED が STARFIELD 背景 (白いドット)で点灯")
print("  テキスト: Thank you!")
print()
ctrl.send_scene('EVENT_3', zone=0, node=0)
time.sleep(0.3)
ctrl.send_text_custom('Thank you!', zone=0, node=0)
time.sleep(3)

# Test 5: FIREWORKS effect
print("[5/5] FIREWORKS effect を送信...")
print("  期待: 両方のLED にランダムな白い円が表示される")
print()
ctrl.send_scene('FIREWORKS', zone=0, node=0)
time.sleep(3)

# Return to READY
print("テストを READY に戻します...")
ctrl.send_scene('READY', zone=0, node=0)
time.sleep(0.5)

print()
print("=" * 70)
print("テスト完了")
print("=" * 70)
print()
print("【確認ポイント】")
print("✓ 両方のLED が同時に同じシーンに変わっているか")
print("✓ タイミングのズレが最小限か (< 100ms)")
print("✓ 明るさが同じレベルか")
print()
print("【結果】")
print("- 両方同時に動作:  2ノード稼働確認 ✓ MVP 達成")
print("- 片方だけ動作:    1ノード のみ稼働")
print("- 両方とも動作無:  ハードウェア問題の可能性")
print()

ctrl.close()
