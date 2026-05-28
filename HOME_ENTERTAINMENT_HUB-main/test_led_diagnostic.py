"""
LED Node Diagnostic Tool
ファームウェアの受信/処理状況を診断する。
実装後、LED ノードのシリアル出力をこのツールで監視して、
何がうまくいっていないかを特定する。
"""
import sys
sys.path.insert(0, 'tools')
from td_sat_sender import TdLedController
import time

print("=" * 80)
print("🔍 LED Node Diagnostic Test")
print("=" * 80)

ctrl = TdLedController()

# テスト 1：HEARTBEAT のみ (ノードがセーフティ白から抜け出すか確認)
print("\n【TEST 1】HEARTBEAT テスト")
print("-" * 80)
print("予期する動作: ノードが白点灯 → green flashing (接続中) に変わる")
print("送信中... 3秒間ハートビートを送信")
for i in range(3):
    ctrl.send_heartbeat()
    time.sleep(1)
print("✓ HEARTBEAT 送信完了")

# テスト 2：READY シーン (OCEAN + CUSTOM テキスト用意)
print("\n【TEST 2】READY シーン + Welcome テキスト")
print("-" * 80)
print("予期する動作:")
print("  1. BG が OCEAN に変わる")
print("  2. 輝度が 120 に落ちる")
print("  3. 'Welcome!' テキストが白で表示される（ダーク背景付き）")
print("送信中...")
ctrl.send_scene('READY', zone=1, node=1)
time.sleep(0.5)
ctrl.send_text_custom('Welcome!', zone=1, node=1)
time.sleep(0.5)
ctrl.send_heartbeat()
print("✓ READY + Welcome 送信完了")

# テスト 3：EVENT_1 (カウントダウン)
print("\n【TEST 3】EVENT_1 + カウントダウン表示")
print("-" * 80)
print("予期する動作:")
print("  1. BG が OCEAN に変わる（既に OCEAN なので変化なし）")
print("  2. 輝度が 180 に上がる")
print("  3. 'EVENT_1' という テキストが表示される")
print("  4. 複数のカウントダウン段階を送信")
print("送信中...")
ctrl.send_scene('EVENT_1', zone=1, node=1)
time.sleep(0.5)

# 複数のカウントダウンレベルを送信
countdown_levels = ["開始まで 3:00", "開始まで 1:30", "開始まで 0:10"]
for countdown_text in countdown_levels:
    ctrl.send_text_custom(countdown_text, zone=1, node=1)
    time.sleep(0.3)
    ctrl.send_heartbeat()

print("✓ EVENT_1 + Countdown 送信完了")

# テスト 4：EVENT_2 (FIRE + 歌詞)
print("\n【TEST 4】EVENT_2 + 歌詞表示")
print("-" * 80)
print("予期する動作:")
print("  1. BG が FIRE に変わる")
print("  2. 輝度が 255 に上がる（全灯）")
print("  3. 歌詞テキストが表示される")
print("  4. FIRE アニメーションが再生される")
print("送信中...")
ctrl.send_scene('EVENT_2', zone=1, node=1)
time.sleep(0.5)
ctrl.send_lyrics_line('Song Lyrics Line 1', zone=1, node=1)
time.sleep(0.5)
ctrl.send_heartbeat()
print("✓ EVENT_2 + Lyrics 送信完了")

# テスト 5：EVENT_3 (STARFIELD + Thanks)
print("\n【TEST 5】EVENT_3 + Thanks メッセージ")
print("-" * 80)
print("予期する動作:")
print("  1. BG が STARFIELD に変わる")
print("  2. 輝度が 200 になる")
print("  3. 'Thank you!' テキストが表示される")
print("送信中...")
ctrl.send_scene('EVENT_3', zone=1, node=1)
time.sleep(0.5)
ctrl.send_text_custom('Thank you!', zone=1, node=1)
time.sleep(0.5)
ctrl.send_heartbeat()
print("✓ EVENT_3 + Thanks 送信完了")

# テスト 6：FIREWORKS (花火)
print("\n【TEST 6】FIREWORKS シーン")
print("-" * 80)
print("予期する動作:")
print("  1. 背景が OFF になる")
print("  2. 花火エフェクトが即座に描画される")
print("  3. 3×3〜5×5 の円状に 10〜20 個のホワイト LED が光る")
print("送信中...")
ctrl.send_scene('FIREWORKS', zone=1, node=1)
time.sleep(0.5)
ctrl.send_heartbeat()
print("✓ FIREWORKS 送信完了")

# テスト 7：OFF (全消灯)
print("\n【TEST 7】OFF - 全消灯")
print("-" * 80)
print("予期する動作: すべての LED が消える")
print("送信中...")
ctrl.send_scene('OFF', zone=1, node=1)
time.sleep(0.5)
ctrl.send_heartbeat()
print("✓ OFF 送信完了")

ctrl.close()

print("\n" + "=" * 80)
print("✅ 診断テスト完了")
print("=" * 80)
print("\n【次のステップ】")
print("1. LED ノードのシリアル出力を確認してください")
print("   - [UDP] recv XXX bytes が表示されているか")
print("   - [CTRL] ... が表示されているか")
print("   - エラーメッセージが表示されていないか")
print("2. LED が以下の順序で動作しているか確認：")
print("   - White (5%) → Green blinking → OCEAN+低輝度 → OCEAN+高輝度")
print("   → FIRE+全灯 → STARFIELD → Fireworks → Off")
print("3. すべてが OK なら、Day 2 フェーズへ進んでください")
