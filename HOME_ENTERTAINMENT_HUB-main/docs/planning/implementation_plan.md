# 実装計画

> **最終更新**: 2026-05-04  
> **MCU**: ESP32-S3-Zero (Waveshare, 4MB Flash + 2MB PSRAM)  
> **主電源（完成形）**: CIO SMARTCOBY Pro SLIM 35W (CIO-MB35W2C1AE-10000-S / ASIN: B0CHVY8FMG)

---

## 基本方針

- 中央ノード 1 台 + LED ノード 1 台の 2 ノード構成で MVP を完成させる。  
- MVP の目的は機能完成ではなく、ボトルネックと破綻点の早期発見に置く。  
- サテライト Wi-Fi 多ノード同期・AudioLINKCORE 本統合・複雑なシーン切替は Phase F 以降に後回しにする。  
- 通信は中央ノード → ローカル LED ノードの UART を最優先で成立させる。  
- LED は電流制限運用を必須前提とする（FastLED `setBrightness` または `setMaxPowerInMilliWatts` による制限）。

---

## MVP 合格条件

| # | 検証項目 | 合格基準 |
|---|---|---|
| 1 | マイク入力 | INMP441 が I2S で動作し、音量レベルが取得できる |
| 2 | ボタン入力 | SW1〜3 が全て正常に chatter 除去済みで検知できる |
| 3 | TFT 表示 | GMT020-01 に 3 画面（Home / Power / Sensor）を切替表示できる |
| 4 | 照度取得 | BH1750 が I2C で応答し lx 値が取得できる |
| 5 | 電流計測 | INA228 ×2 が I2C で応答し V・A・W が取得できる |
| 6 | UART 通信 | 中央ノードからのコマンドに LED ノードが追従する |
| 7 | LED 出力 | WS2812B が電流制限下で指定カラーで点灯する |
| 8 | microSD | LED ノードでアセットファイルを読み出せる |
| 9 | 安全機構 | 強制リセット・セーフティタイムアウトが動作する |
| 10 | 電源安定 | 連続 30 分動作でフレーム破綻・通信停止・電圧異常なし |

---

## MCU 再選定トリガ（S3-Zero → XIAO ESP32S3 Plus）

以下のいずれか 1 つでも発生した場合に MCU 交替を検討する：

- GPIO 本数または周辺機能の割り当てが破綻する  
- CPU 使用率が常態的に 80% を超え、処理落ちが目視できる  
- PSRAM 含めてもバッファ・表示・通信の共存が困難になる  
- Flash 4MB で OTA または資産管理が入らない

---

## GPIO 割り当て（ESP32-S3-Zero 案）

> ストラップピン: GPIO0 (BOOT), GPIO3, GPIO45, GPIO46 は変更不可または要注意。  
> Flash 内蔵使用: GPIO35〜37 は内部専用。  
> 以下はビルド前に実機ピン配置図で必ず照合すること。

### 中央ノード

| GPIO | 機能 | 接続先 | 備考 |
|---|---|---|---|
| GPIO1 | I2S BCK | INMP441 SCK | |
| GPIO2 | I2S WS | INMP441 WS | |
| GPIO3 | I2S DATA_IN | INMP441 SD | ストラップ注意: 起動後は使用可 |
| GPIO4 | WS2812B DATA | 74AHCT125 → WS2812B | 330Ω 直列 |
| GPIO5 | SW1 (Mode) | タクトスイッチ | INPUT_PULLUP |
| GPIO6 | SW2 (Scene) | タクトスイッチ | INPUT_PULLUP |
| GPIO7 | SW3 (Display/Mute) | タクトスイッチ | INPUT_PULLUP |
| GPIO8 | I2C SDA | BH1750, INA228×2 | 4.7kΩ プルアップ |
| GPIO9 | I2C SCL | BH1750, INA228×2 | 4.7kΩ プルアップ |
| GPIO10 | SPI SCK | GMT020-01 SCK | |
| GPIO11 | SPI MOSI | GMT020-01 SDA | |
| GPIO12 | SPI CS | GMT020-01 CS | |
| GPIO13 | SPI DC | GMT020-01 DC | |
| GPIO14 | SPI RST | GMT020-01 RST | |
| GPIO15 | INA228 ALERT | 割り込み入力（任意） | 未使用なら省略可 |
| GPIO17 | UART1 TX | LED ノード RX | |
| GPIO18 | UART1 RX | LED ノード TX | |
| GPIO43 | UART0 TX | USB デバッグ | デフォルト |
| GPIO44 | UART0 RX | USB デバッグ | デフォルト |

### LED ノード

| GPIO | 機能 | 接続先 | 備考 |
|---|---|---|---|
| GPIO1 | SDMMC CLK | microSD CLK | SPI モードも可 |
| GPIO2 | SDMMC CMD | microSD CMD | |
| GPIO3 | SDMMC D0 | microSD D0 | |
| GPIO4 | WS2812B DATA-1 | 74AHCT125 → LED-1 | 330Ω 直列 |
| GPIO5 | WS2812B DATA-2 | 74AHCT125 → LED-2 | 将来拡張用 |
| GPIO6 | I2C SDA | MPU-6050（完成形） | |
| GPIO7 | I2C SCL | MPU-6050（完成形） | |
| GPIO17 | UART1 TX | 中央ノード RX | |
| GPIO18 | UART1 RX | 中央ノード TX | |
| GPIO43 | UART0 TX | USB デバッグ | |
| GPIO44 | UART0 RX | USB デバッグ | |

---

## UART パケット最小仕様（MVP）

### フォーマット

```
[STX 1B] [CMD 1B] [LEN 1B] [PAYLOAD 0〜32B] [CRC8 1B] [ETX 1B]
```

| フィールド | 値 | 説明 |
|---|---|---|
| STX | 0xAA | スタートバイト |
| CMD | コマンド ID | 下表参照 |
| LEN | PAYLOAD の長さ (0〜32) | |
| PAYLOAD | コマンド依存データ | |
| CRC8 | CRC-8/MAXIM | STX〜PAYLOAD の CRC |
| ETX | 0x55 | エンドバイト |

### コマンド ID（MVP 最小セット）

| CMD | 名前 | PAYLOAD | 説明 |
|---|---|---|---|
| 0x01 | SET_BRIGHTNESS | brightness (1B, 0〜255) | 全体輝度設定 |
| 0x02 | SET_COLOR | R(1B), G(1B), B(1B) | 単色塗り |
| 0x03 | SET_EFFECT | effect_id (1B) | エフェクト種別 |
| 0x04 | PLAY_ASSET | asset_id (2B, LE) | アセット ID 再生 |
| 0x05 | STOP | なし | 停止・全消灯 |
| 0x10 | HEARTBEAT | なし | 生存確認（1 秒周期送出） |
| 0x11 | ACK | original_cmd (1B) | 受信確認応答 |
| 0xFF | RESET | なし | ノード強制リセット |

> **タイムアウト**: HEARTBEAT の ACK を 3 秒以内に受け取れない場合、LED ノードはセーフカラー（白 5%）に遷移しリセット待ちになる。

---

## アセット形式（MVP）

### ディレクトリ構成（microSD）

```
/
├── assets/
│   ├── 0001.led    ← LED フレームファイル
│   ├── 0002.led
│   └── ...
└── cfg/
    └── config.json  ← 輝度上限・デフォルトエフェクト等
```

### .led ファイル形式

```
[HEADER 8B]
  magic     : 4B = 0x4C 0x45 0x44 0x21 ("LED!")
  version   : 1B = 0x01
  led_count : 2B (LE, 最大 880)
  fps       : 1B (1〜30)
[FRAMES: 繰り返し]
  frame_data: led_count × 3B (R, G, B 順)
```

- ファイル末尾まで読み続けてループ再生する。  
- 1 フレームのサイズ: `led_count × 3` バイト。  
- MVP は `led_count = 30`, `fps = 10` 程度から開始してよい。

---

## 電源方針（確定版）

| 段階 | 電源構成 |
|---|---|
| **MVP** | USB-C 5V/2A アダプタ直給電。PD トリガ基板・DC-DC は使用しない |
| **完成形** | CIO SMARTCOBY Pro SLIM 35W → USB-C PD トリガ基板（12V 固定） → 5V/8A 固定降圧 DC-DC → 5V 母線 |

### 5V 母線分配（完成形）

```
CIO SMARTCOBY Pro SLIM 35W (10000mAh)
  └─ USB-C PD Trigger (12V 固定出力)
       └─ 5V/8A Buck DC-DC
            ├─ ESP32-S3-Zero (メイン)      〜240mA
            ├─ GMT020-01 TFT               〜 50mA
            ├─ センサ群 (BH1750, INA228×2)  〜  5mA
            ├─ WS2812B イルミ 24LED        〜432mA (30%輝度)
            └─ WS2812B マトリクス          ≦2000mA (FastLED 2A 制限)
                          合計目標: ≦3.1A / 5V = ≦15.5W
```

---

## フェーズ別タスク

### Phase A: 文書と骨組み ✅

- [x] 仕様書・ハード要件・ソフト設計・実装計画を作成
- [x] BOM 作成（MVP + 完成形）
- [x] 電源方針確定（CIO SMARTCOBY Pro SLIM 35W 決定）
- [x] GPIO 割り当て案作成
- [x] UART パケット最小仕様定義
- [x] アセット形式定義

### Phase B: ハードウェア調達・電源検証

**調達（未購入品）**

- [x] CIO SMARTCOBY Pro SLIM 35W を注文する（ASIN: B0CHVY8FMG / ¥3,980）——発注済み 2026-05-02
- [x] ESP32-S3-Zero (Waveshare) × 2 を注文する——発注済み 2026-05-02
- [ ] BH1750 モジュール (GY-302) × 1 を注文する
- [ ] GMT020-01 TFT (2.0" ST7789VW) × 1 を注文する（未入手の場合）
- [ ] INMP441 モジュール × 1 を注文する（未入手の場合）
- [ ] タクトスイッチ 6×6mm × 5 を注文する
- [ ] WS2812B テープ 60LED/m × 1m を注文する
- [ ] 74AHCT125 × 2 を注文する
- [ ] microSD スロットモジュール（SDMMC 対応）× 1 を注文する

**電源チェーン検証（バッテリー到着後）**

- [ ] PD トリガ基板単体テスト: CIO バッテリー接続 → テスターで 12V 出力確認
- [ ] 降圧 DC-DC 単体テスト: 12V 入力 → 無負荷 5.0V 確認
- [ ] 段階負荷テスト: 抵抗負荷 1A / 2A / 3A → 電圧降下 < 0.1V・発熱確認
- [ ] 5V 母線安定確認後、はじめて ESP32-S3-Zero を接続する

### Phase C: メインノード単体

- [ ] ESP32-S3-Zero を ESP-IDF プロジェクト (`firmware/controller`) に接続して書き込み確認
- [ ] UART0 (USB) デバッグ出力確認
- [ ] BH1750 I2C 疎通確認（lx 取得）
- [ ] INA228 ×2 I2C 疎通確認（V / A / W 取得、アドレス 0x40, 0x41）
- [ ] INMP441 I2S 取得確認（音量レベル表示）
- [ ] SW1〜3 ボタン入力確認（チャタリング除去）
- [ ] GMT020-01 TFT 表示確認（3 画面切替）
- [ ] WS2812B 30LED 点灯確認（電流制限あり）
- [ ] 5V USB 給電での連続 30 分安定動作確認

### Phase D: LED ノード単体

> **2026-05-04 更新**: USB CDC 経由の UART 通信パイプライン完成。LED カラー制御を実機確認済。

**2026-05-04 完了**

- [x] UART プロトコル設計 (`hub_protocol.h` フレーム仕様確定)——2026-05-02
- [x] `firmware/satellite_node` プロジェクト作成（PlatformIO + FastLED）——2026-05-04
- [x] UART1 (GPIO17/18) 受信ルーチン実装——2026-05-04
- [x] USB CDC 受信経路追加（COM3 テスト用）——2026-05-04
- [x] `ARDUINO_USB_CDC_ON_BOOT=1` 設定追加（Serial 出力不具合の根本原因解決）——2026-05-04
- [x] セーフティタイムアウト（HEARTBEAT 未受信 3 秒）実装——2026-05-04
- [x] PC テストツール作成 (`tools/led_uart_test_tool.py`)——2026-05-04
- [x] ストリーム送信ベンチ 120fps / 240 frames / Dropped:0 実測——2026-05-04
- [x] SET_COLOR コマンドで WS2812B カラー制御実機確認（赤・青切替確認）——2026-05-04

**未完了**

- [ ] ESP32-S3-Zero (2 台目) を ESP-IDF プロジェクト (`firmware/lighting_node`) に書き込み確認
- [ ] microSD スロット接続・認識確認
- [ ] .led アセットファイルをテストデータで作成、microSD に書き込み
- [ ] WS2812B 88LED (1 行分) 点灯確認（FastLED 電流制限 2A 以下）
- [ ] UART1 (GPIO17/18) 直結配線での LED 制御確認（USB-UART アダプタ使用）

### Phase E: 通信統合

> **2026-05-04 注**: USB CDC (COM3) 経由の PC→LED ノード UART 通信は完了。
> 次は UART1 直結（中央ノード↔LED ノード）の実機検証に移行する。

- [ ] 中央ノード → LED ノードへ UART1 HEARTBEAT 周期送出・ACK 確認
- [ ] SET_COLOR / SET_BRIGHTNESS コマンドで LED ノードが追従する確認
- [ ] PLAY_ASSET コマンドで microSD アセットが再生される確認
- [ ] STOP / RESET コマンド確認
- [ ] 強制リセット（RESET コマンド / タイムアウト）動作確認
- [ ] TouchDesigner から COM3 経由で hub_protocol フレームを送出する検証

### Phase F: シーン統合

- [ ] ライブ空間化シーン実装
- [ ] ヒーリング空間化シーン実装
- [ ] モード切替時のフェード処理
- [ ] microSD 上の演出データ切替と同期再生

### Phase G: AudioLINKCORE 統合

- [ ] 受信プロトコル確定
- [ ] 外部制御入力による演出更新
- [ ] Wi-Fi サテライトノードへのコマンド配信

### Phase H: 安定化・完成

- [ ] 長時間動作試験（4 時間以上）
- [ ] Wi-Fi 切断回復試験
- [ ] LED 高負荷試験（FastLED 制限を段階的に引き上げ）
- [ ] microSD 抜き差し異常系試験
- [ ] PD 電源チェーン完成形評価（バッテリー → 12V → 5V 母線での動作確認）
- [ ] 電流予算の実測値と見積もりの乖離確認（INA228 ログ分析）

---

## 優先検証項目（Phase B〜E 横断）

1. **S3-Zero の能力確認**: TFT 描画・I2S・UART・I2C を同時動作させた時の CPU 使用率
2. **PD 電源チェーン安定性**: バッテリー残量変化時の 12V / 5V 出力変動
3. **SDMMC + WS2812B 並列動作**: LED ノードで両者が共存するか
4. **UART 応答性**: 30 fps 相当のコマンド更新に間に合うか
5. **LED 負荷変動**: 輝度を上げた時の 5V 母線電圧サグと INA228 計測値

---

## 設計メモ

- SD カードはサテライト（LED ノード）側に寄せる構成が責務分離として自然。
- TFT は中央ノードのままで問題ない。
- SDMMC 4-bit にこだわらず、GPIO 制約に応じて 1-bit SPI からスタートしてよい。
- WS2812B データ線の 74AHCT125 は 3.3V → 5V 変換必須（5V データで WS2812B の誤動作を防ぐ）。
- LED 電源とロジック電源は GND 共通だが、LED の +5V と ESP32 の 3V3/5V は経路を分離する。
- INA228 のシャント抵抗は 100mΩ 品を使用。測定電流範囲: ±1.63A @ 100mΩ（20bit）。
- ローカル LED ノードはメインノードに UART で直結し、サテライト LED ノードは Wi-Fi 配信を受ける。
