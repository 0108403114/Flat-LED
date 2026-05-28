# ESP32-S3 衛星ノード初期設定ドキュメント

**プロジェクト名：** HomeLiveHall LED Satellite Node  
**作成日：** 2026-05-04  
**確定日：** 2026-05-04（実機テスト完了）

---

## 1. ハードウェア仕様

### ボード

| 項目 | 値 |
|------|-----|
| **基板** | Waveshare ESP32-S3-Zero |
| **SoC** | ESP32-S3 (revision v0.2) |
| **Flash** | 4MB |
| **RAM** | 320KB |
| **CPU クロック** | 240MHz |
| **Crystal** | 40MHz |
| **MAC アドレス** | A0:F2:62:F0:84:90 |

### USB 接続

| 項目 | 値 |
|------|-----|
| **VID:PID** | 303A:1001 |
| **COMポート** | COM3 |
| **USB チップ** | ESP32-S3 内蔵（外部変換チップなし） |
| **USB Mode** | UART（CDC ではなく）|

---

## 2. PlatformIO 設定

### `platformio.ini`（確定版）

```ini
[env:esp32-s3-zero]
platform  = espressif32
board     = dfrobot_firebeetle2_esp32s3
framework = arduino

; ボード定義のデフォルト(qio / 4MB / ARDUINO_USB_MODE=1)をそのまま使用
; ★ ARDUINO_USB_CDC_ON_BOOT は設定しない（リセットループの原因）

upload_port = COM3
monitor_port = COM3
upload_speed = 115200
monitor_speed = 115200

lib_deps =
    fastled/FastLED @ ^3.7.0

build_src_filter =
    +<*>
    +<../../shared/include>
```

### ビルド・書き込みコマンド

```powershell
# Flash 完全消去
pio run -e esp32-s3-zero -t erase

# ビルド・書き込み
pio run -e esp32-s3-zero -t upload

# シリアルモニタ
pio device monitor --port COM3 --baud 115200
```

---

## 3. LED マトリクス マッピング

### 物理構成

```
LED マトリクス: H88 × V10 = 880 LED
├── Block1 (GPIO12): LED0~439 (440個)
└── Block2 (GPIO13): LED0~439 (440個)
```

### GPIO配置

| GPIO | 接続先 | 機能 | 備考 |
|------|--------|------|------|
| **12** | Block1 Data | WS2812B 信号 | 330Ω 直列抵抗 |
| **13** | Block2 Data | WS2812B 信号 | 330Ω 直列抵抗 |

### LED 仕様

| 項目 | 値 |
|------|-----|
| **LED タイプ** | WS2812B (NeoPixel 互換) |
| **色形式** | GRB（FastLED標準） |
| **データレート** | 800kHz |
| **電源電圧** | 5V |
| **1LED 理論消費電力** | 60mA（最大・白100%時） |
| **Block あたり最大電力** | 440 × 60mA = 26.4A（理論値） |

### FastLED 設定（コード内）

```cpp
// Block1 定義
#define LED_PIN_BLOCK1 12
#define NUM_LEDS_BLOCK1 440
#define LED_TYPE WS2812B
#define COLOR_ORDER GRB

FastLED.addLeds<LED_TYPE, LED_PIN_BLOCK1, COLOR_ORDER>(
    gBlock1, NUM_LEDS_BLOCK1
).setCorrection(TypicalLEDStrip);

// Block2 定義
#define LED_PIN_BLOCK2 13
#define NUM_LEDS_BLOCK2 440

FastLED.addLeds<LED_TYPE, LED_PIN_BLOCK2, COLOR_ORDER>(
    gBlock2, NUM_LEDS_BLOCK2
).setCorrection(TypicalLEDStrip);

// 輝度制限（固定）
FastLED.setBrightness(10);  // 10/255 ≈ 3.9%
```

---

## 4. 消費電力管理

### 設計方針

| 項目 | 値 | 根拠 |
|------|-----|------|
| **最大輝度** | 10/255 | テスト固定 |
| **Block あたり実効電力** | 約 2.5A 以下 | 設計上限 |
| **電源仕様（推奨）** | 5V / 3A 級 | 各ブロック独立電源 |

### 電流計算（参考値）

輝度 10/255 時：
```
LED1個の消費電力 ≈ 60mA × (10/255) ≈ 2.4mA
Block1 総消費電力 ≈ 440 × 2.4mA ≈ 1.06A
Block2 総消費電力 ≈ 440 × 2.4mA ≈ 1.06A
合計 ≈ 2.12A
```

---

## 5. カラーリファレンス

### FastLED 基本色

```cpp
CRGB::Red       // 赤
CRGB::Green     // 緑
CRGB::Blue      // 青
CRGB::White     // 白
CRGB::Black     // 黒（消灯）
CRGB::Yellow    // 黄
CRGB::Cyan      // シアン
CRGB::Magenta   // マゼンタ
```

### カスタムカラー

```cpp
// RGB 値で直接指定
CRGB(255, 0, 0);      // 赤 (R:255, G:0, B:0)
CRGB(0, 255, 0);      // 緑 (R:0, G:255, B:0)
CRGB(0, 0, 255);      // 青 (R:0, G:0, B:255)

// HSV を RGB に変換
hsv2rgb_spectrum(hue, saturation, value);
```

---

## 6. テストモード（確定版）

```cpp
// 実装済みテストシーケンス:
// 1. 全青（3秒）
// 2. Block1 赤順次点灯（LED0→439、各50ms）
// 3. Block2 緑順次点灯（LED0→439、各50ms）
// 4. ループ
```

**実行方法：** `src/main.cpp` に含まれています

---

## 7. トラブルシューティング参照

詳細は以下を参照：

- **初期接続時のエラー:** [esp32s3_troubleshooting.md](esp32s3_troubleshooting.md)
- **別ボード接続時の手順:** [esp32_platformio_setup_guide.md](esp32_platformio_setup_guide.md)

### よくある問題

| 症状 | 原因 | 解決策 |
|------|------|--------|
| 書き込み失敗 | COM ポート占有 | シリアルモニタを閉じる |
| `rst:0x3` リセットループ | `ARDUINO_USB_CDC_ON_BOOT=1` | 使用しない |
| LED が反応しない | GPIO ピン番号誤り | `#define LED_PIN_BLOCK` を確認 |
| 文字化け | baud rate 不一致 | 115200 に統一 |

---

## 8. 本番環境へのチェックリスト

実装前に以下を確認すること：

- [ ] `platformio.ini` の `board` が `dfrobot_firebeetle2_esp32s3` か
- [ ] `upload_port` / `monitor_port` が COM3 か
- [ ] LED バッファサイズが 440 × 2 か
- [ ] `FastLED.setBrightness(10)` が設定されているか
- [ ] Block1 = GPIO12、Block2 = GPIO13 か
- [ ] 電源が 5V / 3A 以上か（各ブロック独立推奨）
- [ ] GND が共通接地されているか

---

## 9. 今後の拡張ポイント

### 次ステップ

1. **UART 通信追加** - 中央ノードからのコマンド受信
2. **プロトコル実装** - パケット解析・LED 制御シーケンス
3. **microSD 対応** - LED フレームデータ読み込み
4. **タイムアウト処理** - 通信断時のセーフカラー（白 5%）

### 既知の設計制約

- 両ブロック同時駆動時は消費電力が約 2.1A（設計余裕あり）
- 輝度は 10/255 固定（運用要件による調整可能）
- GPIO12/13 は固定（変更時は全コードに波及）

---

## ファイル一覧

| ファイル | 役割 |
|---------|------|
| `firmware/satellite_node/platformio.ini` | PlatformIO 設定 |
| `firmware/satellite_node/src/main.cpp` | テストコード（Block1/Block2 制御） |
| `shared/include/hub_protocol.h` | プロトコル定義（今後） |
| `docs/hardware/esp32s3_troubleshooting.md` | トラブル記録 |
| `docs/hardware/esp32_platformio_setup_guide.md` | セットアップガイド |
| **このファイル** | 初期設定ドキュメント |

---

## 参考資料

- [ESP32-S3 Technical Reference Manual](https://www.espressif.com/sites/default/files/documentation/esp32-s3_technical_reference_manual_en.pdf)
- [FastLED API Reference](https://fastled.io/docs/3-1-release/group__types.html)
- [WS2812B Datasheet](https://datasheets.com/datasheets/97/WS2812B-V5.pdf)
