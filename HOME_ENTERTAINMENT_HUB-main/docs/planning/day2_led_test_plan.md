# Day 2 LED 実機テスト詳細計画 (2026-05-09)

## 現在の状態

✅ **通信レイヤー**: 完全に機能中
- ファームウェア起動・WiFi 接続 OK
- CTRL パケット受信・処理 OK  
- CONTENT パケット受信・処理 OK
- HEARTBEAT 受信 OK
- 全シーン定義が apply_ctrl_packet() で展開されている OK
- gCustomText バッファに Welcome! など保存されている OK

## 診断テスト

### Step 1: GPIO12/GPIO13 の LED 出力確認

**問題**: FastLED が GPIO12/GPIO13 に信号を出力しているか確認が必要

```cpp
// main.cpp Line 1059-1062
FastLED.addLeds<LED_TYPE, LED_PIN_BLOCK1, COLOR_ORDER>(
    gBlock1, NUM_LEDS_BLOCK1).setCorrection(TypicalLEDStrip);
FastLED.addLeds<LED_TYPE, LED_PIN_BLOCK2, COLOR_ORDER>(
    gBlock2, NUM_LEDS_BLOCK2).setCorrection(TypicalLEDStrip);
```

**テスト方法**:
1. 物理 LED ストリップ (WS2812B) を GPIO12 / GPIO13 に接続
2. 起動ビジュアル (緑×3点滅) が見えるか確認
3. セーフティ白 5% が点灯するか確認

### Step 2: シーン描画フロー確認

**現在のレンダリングロジック** (loop() @ Line 1160-1185):
```cpp
if (!gSafeMode && !gNavActive) {
    if (now - gAnimLastMs >= 20) {  // 50fps
        gAnimLastMs = now;
        
        // 1. BG クリアまたはアニメーション更新
        if (gBgAsset == SAT_V3_BG_OFF) {
            fill_solid(gBlock1, NUM_LEDS_BLOCK1, CRGB::Black);
            fill_solid(gBlock2, NUM_LEDS_BLOCK2, CRGB::Black);
        } else {
            update_bg_anim();  // OCEAN / FIRE / STARFIELD
        }
        
        // 2. フェードトランジション処理
        if (gFadeActive) { /* ... */ }
        
        // 3. テキストオーバーレイ
        if (gTextMode == SAT_V3_TEXT_LYRICS && gLyrics.current_line[0] != '\0') {
            draw_text_layer(gLyrics.current_line, CRGB::White);
        } else if (gTextMode == SAT_V3_TEXT_CUSTOM && gCustomText[0] != '\0') {
            draw_text_layer(gCustomText, CRGB::White);
        }
        
        // 4. FastLED.show() で LED に送信
        FastLED.show();
    }
}
```

**潜在的な問題**:
- [ ] gSafeMode が false に設定されているか?
- [ ] gNavActive が false か?
- [ ] 20ms タイマーが正しく機能しているか?
- [ ] FastLED.show() が呼ばれているか?

### Step 3: 各シーン別の期待値

| シーン | 背景 | 輝度 | テキスト | 期待動作 |
|-------|------|------|---------|---------|
| **READY** | OCEAN (青波動) | 120 (47%) | Welcome! | 低輝度で波が流れる + Welcome 白表示 |
| **EVENT_1** | OCEAN | 180 (71%) | "開始まで 3:00" | 中輝度で波 + カウントダウン表示 |
| **EVENT_2** | FIRE (赤炎) | 255 (100%) | 歌詞 | 全灯で炎が揺らぐ + 歌詞表示 |
| **EVENT_3** | STARFIELD (星) | 200 (78%) | "Thank you!" | 星が瞬く + メッセージ表示 |
| **FIREWORKS** | OFF | 255 | なし | 花火 (3×3～5×5 円) が複数 |
| **OFF** | OFF | - | なし | 完全消灯 |

### Step 4: LED 表示が無い場合の診断手順

**If LED が全く光らない:**

1. **ハードウェア確認**
   - [ ] WS2812B LED ストリップが GPIO12 に正しく接続されているか?
   - [ ] 電源供給は十分か? (WS2812B は 1 個あたり最大 60mA)
   - [ ] GND は共通か?
   - [ ] GPIO12/13 からの信号は出ているか? (オシロスコープで確認)

2. **FastLED 初期化確認**
   - [ ] Line 1066: `FastLED.setMaxPowerInVoltsAndMilliamps(5, 2500)` で電流制限されていないか?
   - [ ] `fill_solid(..., CRGB::White)` が `led_fill(0, 255, 0)` で緑を表示できるか?

3. **ソフト状態確認**
   - [ ] シリアルログで `[CTRL] ... bg=4` などが表示されているか? (表示されていない場合は通信エラー)
   - [ ] `gSafeMode` が false に変わっているか?

**If LED が表示されるが、色や動きが違う:**

1. **色の問題**
   - WS2812B の GRB 順序が正しいか確認 (RGB ではなく GRB)
   - COLOR_ORDER が `GRB` に設定されているか? (main.cpp Line 52)

2. **アニメーション速度**
   - FIRE / OCEAN / STARFIELD の速度が期待と異なる場合、update_bg_anim() の定数を調整

3. **テキスト表示**
   - テキストが見えない場合、draw_text_layer() の実装を確認
   - row_offset=1 で 1 行目に表示されるはず

### Step 5: テスト送信スクリプト

```python
import sys
sys.path.insert(0, 'tools')
from td_sat_sender import TdLedController
import time

ctrl = TdLedController()

# Test 1: READY
print("🔵 Test 1: READY (OCEAN, dim=120)")
ctrl.send_scene('READY', zone=1, node=1)
time.sleep(1)
ctrl.send_text_custom('Welcome!', zone=1, node=1)
time.sleep(2)

# Test 2: EVENT_1
print("🔵 Test 2: EVENT_1 (OCEAN, dim=180)")
ctrl.send_scene('EVENT_1', zone=1, node=1)
time.sleep(2)

# Test 3: EVENT_2
print("🔵 Test 3: EVENT_2 (FIRE, dim=255)")
ctrl.send_scene('EVENT_2', zone=1, node=1)
time.sleep(2)

# Test 4: EVENT_3
print("🔵 Test 4: EVENT_3 (STARFIELD, dim=200)")
ctrl.send_scene('EVENT_3', zone=1, node=1)
time.sleep(2)

# Test 5: FIREWORKS
print("🔵 Test 5: FIREWORKS")
ctrl.send_scene('FIREWORKS', zone=1, node=1)
time.sleep(2)

# Test 6: OFF
print("🔵 Test 6: OFF (消灯)")
ctrl.send_scene('OFF', zone=1, node=1)
time.sleep(1)

ctrl.close()
print("✅ Test sequence complete")
```

## 次のアクション

1. **LED ストリップを GPIO12 に接続**
2. **シリアルモニターで起動ログを確認**: `[LED Node] Boot Zone=1 Node=1`
3. **診断テストを送信**: `python test_led_diagnostic.py`
4. **LED の反応を観察** してから、以下を確認：
   - 色が正しく表示されているか
   - アニメーションが動いているか
   - テキストが表示されているか
   - タイミングが正しいか

## 期待される動作フロー (成功時)

```
起動 → 緑×3点滅 → 白 5% (safe mode) → HEARTBEAT 受信後通常動作
  ↓
OCEAN (青波) ← READY シーン
  ↓ Welcome! テキスト表示
  ↓ (1秒待機)
  ↓
OCEAN (輝度アップ) ← EVENT_1 シーン
  ↓ "開始まで 3:00" 表示
  ↓ (1秒待機)
  ↓
FIRE (赤炎, 全灯) ← EVENT_2 シーン
  ↓ 歌詞表示
  ↓ (1秒待機)
  ↓
STARFIELD (星瞬き) ← EVENT_3 シーン
  ↓ "Thank you!" 表示
  ↓ (1秒待機)
  ↓
花火 (ホワイト円) ← FIREWORKS シーン
  ↓ (2秒待機)
  ↓
消灯 (OFF)
```

---

**作成者**: GitHub Copilot  
**作成日**: 2026-05-09 16:30 JST
