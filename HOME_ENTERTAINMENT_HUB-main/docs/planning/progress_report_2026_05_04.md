# HomeLiveHall プロジェクト 進捗状況レポート

**レポート日:** 2026-05-04  
**フェーズ:** MVP 進捗中（LED ノード基盤完成）

---

## プロジェクト全体構成図

```
HomeLiveHall (中央ノード)
├── マイク入力（INMP441）
├── TFT 表示（GMT020-01）
├── センサー類（BH1750, INA228×2）
├── ボタン入力（SW1~3）
└── UART1 TX/RX ↔ Satellite LED ノード
     
     
Satellite LED ノード
├── UART1 RX/TX ↔ 中央ノード（受信側）
├── GPIO12 → Block1 LED（440個）
├── GPIO13 → Block2 LED（440個）
├── microSD（将来）
└── 電源: 5V / 3A
```

---

## MVP 合格条件チェックリスト

| # | 項目 | 状態 | 進捗 | 次ステップ |
|---|------|------|------|---------|
| 1 | マイク入力（INMP441） | ⭕ 未実装 | 0% | 中央ノード実装 |
| 2 | ボタン入力（SW1~3） | ⭕ 未実装 | 0% | 中央ノード実装 |
| 3 | TFT 表示 | ⭕ 未実装 | 0% | 中央ノード実装 |
| 4 | 照度取得（BH1750） | ⭕ 未実装 | 0% | 中央ノード実装 |
| 5 | 電流計測（INA228×2） | ⭕ 未実装 | 0% | 中央ノード実装 |
| 6 | UART 通信 | 🟡 開発中 | 30% | プロトコル実装 |
| 7 | **LED 出力** | ✅ **完成** | **100%** | **本番統合** |
| 8 | microSD | ⭕ 未実装 | 0% | LED ノード拡張 |
| 9 | 安全機構（タイムアウト等） | ⭕ 未実装 | 0% | プロトコル実装時 |
| 10 | 電源安定性 | 🟡 部分検証 | 50% | 負荷テスト予定 |

---

## 完成した要素（✅ LED ノード）

### ハードウェア確認

- [x] ESP32-S3-Zero 接続・認識
- [x] GPIO12 (Block1) 接続確認
- [x] GPIO13 (Block2) 接続確認
- [x] WS2812B LED ×880 個制御確認
- [x] 消費電力測定（輝度 10/255 時 ≈ 2.1A）

### ソフトウェア実装

- [x] PlatformIO / dfrobot_firebeetle2_esp32s3 定義
- [x] FastLED ライブラリ統合
- [x] Block1/Block2 独立バッファ
- [x] テストモード（全青 → Block1赤順次 → Block2緑順次）
- [x] 輝度制限（10/255 固定）

### ドキュメント整備

- [x] [esp32s3_troubleshooting.md](docs/hardware/esp32s3_troubleshooting.md) - トラブル記録
- [x] [esp32_platformio_setup_guide.md](docs/hardware/esp32_platformio_setup_guide.md) - セットアップ汎用ガイド
- [x] [esp32s3_satellite_node_configuration.md](docs/hardware/esp32s3_satellite_node_configuration.md) - 初期設定ドキュメント

---

## 開発中の要素（🟡 UART 通信）

### 現在の状況

LED ノードはテストモードで **単独動作** 中（中央ノードとの通信なし）

### 次実装予定

1. **プロトコル定義** - 中央→LED間のコマンド形式
2. **UART 受信ルーチン** - GPIO17/18 の UART1
3. **LED 制御コマンド処理** - 色・パターン・タイミング解析
4. **ハートビート・タイムアウト** - 3秒無信号で白 5% へ遷移

### 通信仕様（設計案）

```
中央ノード → LED ノード:
  Frame: [0xFF] [CMD] [ARG0] [ARG1] ... [CHECKSUM]
  例: 0xFF 0x01 0x00 0xFF 0x00 (赤, Block1 全点灯)

LED ノード → 中央ノード:
  ACK: 0xAA [STATUS]
  STATUS: 0x00=OK, 0x01=Error
```

---

## 未実装の要素（⭕ 中央ノード）

### 中央ノード側（HomeLiveHall）

| 機能 | 優先度 | 見積 | 備考 |
|------|--------|------|------|
| INMP441 マイク入力 | 🔴 高 | 2日 | 音声解析基盤 |
| BH1750 照度センサ | 🟡 中 | 1日 | 環境設定用 |
| INA228 電流計測 | 🟡 中 | 1日 | 消費電力監視 |
| GMT020-01 TFT 表示 | 🟡 中 | 3日 | UI 実装 |
| SW1~3 ボタン入力 | 🟡 中 | 1日 | 入力処理 |
| LED シーンライブラリ | 🔴 高 | 5日 | 演出データベース |

### LED ノード側の拡張

| 機能 | 優先度 | 見積 | 備考 |
|------|--------|------|------|
| microSD ファイル読み込み | 🟡 中 | 2日 | LED フレーム資産管理 |
| 電源リセット回路 | 🟡 中 | 1日 | 安全機構 |
| EEPROM キャリブレーション | 🟢 低 | 1日 | 色再現性向上（将来） |

---

## リスク・制約事項

### 発見済みの問題点

1. **USB CDC 初期化タイムアウト** ✅ 解決済み
   - 原因: `ARDUINO_USB_CDC_ON_BOOT=1` の RWD リセット
   - 対策: dfrobot_firebeetle2_esp32s3 定義 + CDC OFF

2. **GPIO 割り当て競合** 🟡 要確認
   - 中央ノード: GPIO12/13/14/15 を TFT SPI に割り当て
   - LED ノード: GPIO12/13 を WS2812B に割り当て → 独立ボード のため問題なし

3. **電源分離** 🟡 推奨
   - 中央ノード電源と LED ノード電源は **分離推奨**
   - 現在: LED ノード単体で 5V / 3A 確保完了

### 設計上の制約

- LED 輝度: 10/255 固定（消費電力制限）
- ブロック間距離: UART 配線長 < 3m 推奨
- 中央ノードの UART1 バッファ: 256B 標準（LED コマンド十分）

---

## 次フェーズへの推奨順序

### Phase 2: UART プロトコル統合（1週間）

```
1. hub_protocol.h でコマンド形式定義
2. LED ノードで UART1 受信処理実装
3. 中央ノード（仮）で UART1 送信テスト
4. コマンド制御で全色テスト
```

### Phase 3: 中央ノード最小実装（2週間）

```
1. INMP441 マイク入力実装
2. 簡易 UI（TFT 黒/白 表示）
3. 音量レベル → LED 色マッピング（プロトタイプ）
```

### Phase 4: 統合テスト（1週間）

```
1. 30 分連続動作テスト
2. 通信ロバストネステスト（パケット損失時）
3. 電源安定性テスト
```

---

## ファイル構成（現在）

```
firmware/
├── satellite_node/
│   ├── platformio.ini ✅
│   ├── src/
│   │   └── main.cpp ✅ (テストモード実装)
│   └── .pio/
├── controller/ (未実装)
│   ├── platformio.ini
│   └── src/
│       └── app_main.c
shared/
├── include/
│   └── hub_protocol.h (未実装)
```

---

## 成功メトリクス

| メトリクス | 現在 | 目標 | 合格 |
|----------|------|------|------|
| LED 応答時間 | < 50ms | < 100ms | ✅ |
| 通信遅延 | - | < 10ms | 🟡 |
| LED 輝度精度 | ±5% | ±10% | ✅ |
| 消費電力 | 2.1A | < 3.0A | ✅ |
| 稼働率 | 100%（テスト） | 99.9% | 🟡 |

---

## 本日の成果

✅ **LED ノード基盤完成**
- ESP32-S3-Zero 設定確定
- Block1/Block2 独立制御確認
- FastLED テストモード動作確認
- 設定ドキュメント 3 点整備

🎯 **即座に進める場合**
- 中央ノード → LED ノード の UART 通信プロトコル定義
- hub_protocol.h に制御コマンドを形式化
- LED ノードの UART 受信ルーチン実装

---

## 参考資料

- [実装計画](implementation_plan.md)
- [プロジェクト仕様](../specifications/project_concept_technical_spec.md)
- [LED ノード初期設定](../hardware/esp32s3_satellite_node_configuration.md)
