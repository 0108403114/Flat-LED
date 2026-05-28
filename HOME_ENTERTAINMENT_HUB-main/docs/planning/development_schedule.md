# 開発スケジュール

> **作成日**: 2026-05-02  
> **対象**: HOME_ENTERTAINMENT_HUB プロジェクト（中央ノード + LED ノード）  
> **前提**: 週末・平日夜を中心にした個人開発ペース

---

## マイルストーン概要

| マイルストーン | 内容 | 目安期間 |
|---|---|---|
| **M0** | 部品調達完了 | 〜2026-05-中旬 |
| **M1** | 電源チェーン検証完了 | M0 + 1 週間 |
| **M2** | 中央ノード単体動作確認 | M1 + 2 週間 |
| **M3** | LED ノード単体動作確認 | M2 + 2 週間 |
| **M4** | UART 通信統合（MVP 完成） | M3 + 1 週間 |
| **M5** | シーン統合・演出実装 | M4 + 3 週間 |
| **M6** | AudioLINKCORE 統合 | M5 + 2 週間 |
| **M7** | 安定化・完成形電源移行 | M6 + 2 週間 |

---

## Phase B: ハードウェア調達・電源検証

**期間目安**: 2026-05-02 〜 2026-05-中旬

### Week 1（調達）
- [x] CIO SMARTCOBY Pro SLIM 35W を Amazon で注文（ASIN: B0CHVY8FMG / ¥3,980）——発注済み 2026-05-02
- [x] ESP32-S3-Zero × 2 を Waveshare / 国内代理店で注文——発注済み 2026-05-02
- [ ] BH1750 モジュール × 1 を注文
- [ ] GMT020-01 TFT × 1 を注文（未入手の場合）
- [ ] INMP441 モジュール × 1 を注文（未入手の場合）
- [ ] 小物パーツ（タクトスイッチ、WS2812B テープ、74AHCT125、microSD スロット、抵抗・コンデンサ）を注文

### Week 2（電源検証 → M1）
- [ ] PD トリガ基板単体テスト（12V 出力確認）
- [ ] 降圧 DC-DC 単体テスト（5.0V 確認）
- [ ] 段階負荷テスト（1A / 2A / 3A）
- [ ] 🏁 **M1達成**: 5V 母線 3A 運転で電圧降下 < 0.1V、発熱問題なし

---

## Phase C: 中央ノード単体

**期間目安**: 2026-05-中旬 〜 2026-05-下旬

### Week 3
- [ ] ESP-IDF 環境確認（`firmware/controller`）
- [ ] ESP32-S3-Zero に書き込み・デバッグ出力確認
- [ ] BH1750 I2C 疎通確認
- [ ] INA228 ×2 I2C 疎通確認

### Week 4
- [ ] INMP441 I2S 確認（音量レベル取得）
- [ ] SW1〜3 ボタン入力確認
- [ ] GMT020-01 TFT 表示（Home / Power / Sensor 3 画面）
- [ ] WS2812B 30LED 点灯（電流制限あり）
- [ ] 30 分連続安定動作確認
- [ ] 🏁 **M2達成**: 中央ノード単体の MVP 合格条件 1〜5, 7 を全て通過

---

## Phase D: LED ノード単体

**期間目安**: 2026-05-下旬 〜 2026-06-上旬

### Week 5
- [ ] ESP32-S3-Zero (2 台目) に書き込み・デバッグ出力確認
- [ ] microSD スロット認識、.led ファイル読み出し
- [ ] WS2812B 88LED (1 行分) 点灯確認（FastLED 2A 制限）

### Week 6
- [ ] セーフティタイムアウト動作確認（HEARTBEAT 未受信 3 秒）
- [ ] UART1 受信での LED 制御確認
- [ ] 🏁 **M3達成**: LED ノード単体の MVP 合格条件 7〜9 を通過

---

## Phase E: 通信統合（MVP 完成）

**期間目安**: 2026-06-上旬 〜 2026-06-中旬

### Week 7
- [ ] 中央ノード ↔ LED ノード UART HEARTBEAT / ACK サイクル確認
- [ ] SET_COLOR / SET_BRIGHTNESS で LED 追従確認
- [ ] PLAY_ASSET で microSD 再生確認
- [ ] STOP / RESET 確認
- [ ] 連続 30 分安定動作（2 ノード接続）
- [ ] 🏁 **M4達成（MVP 完成）**: 全 MVP 合格条件（#1〜#10）通過

---

## Phase F: シーン統合・演出実装

**期間目安**: 2026-06-中旬 〜 2026-07-上旬

### Week 8〜9
- [ ] ライブ空間化シーン実装
- [ ] ヒーリング空間化シーン実装
- [ ] モード切替フェード処理
- [ ] microSD 演出データ切替・同期再生
- [ ] 🏁 **M5達成**: 2 シーン以上が実機で動作

---

## Phase G: AudioLINKCORE 統合

**期間目安**: 2026-07-上旬 〜 2026-07-中旬

### Week 10〜11
- [ ] 受信プロトコル確定
- [ ] 外部制御入力による演出更新
- [ ] Wi-Fi サテライトノードへのコマンド配信（将来対応の骨組み）
- [ ] 🏁 **M6達成**: 外部制御で演出が切り替わる

---

## Phase H: 安定化・完成形電源移行

**期間目安**: 2026-07-中旬 〜 2026-07-下旬

### Week 12〜13
- [ ] 4 時間以上の長時間動作試験
- [ ] Wi-Fi 切断回復試験
- [ ] LED 高負荷試験
- [ ] microSD 抜き差し異常系試験
- [ ] **完成形電源移行**: バッテリー → 12V PD → 5V 母線での全体動作確認
- [ ] INA228 ログで電流予算の実測値・見積もり乖離を確認
- [ ] 🏁 **M7達成（完成）**: 全フェーズ合格・安定動作確認

---

## 現在地（2026-05-10 更新）

```
Phase A ██████████ 100% 完了
Phase B ████░░░░░░  40% 電源チェーン実負荷試験が残り
Phase C ░░░░░░░░░░   0% 中央ノード単体未着手
Phase D ████████░░  80% サテライト LED ノード実機動作確認済み (microSD未)
Phase E ██████████ 100% 完了 (Wi-Fi UDP/シーン/歌詞/Force Reset/2台同期)
Phase F ██████████ 100% 完了 (BG3種/テキスト/フェード/シーン4種/30分試験)
Phase G ████████░░  80% 演出シーケンス調整完了、中央ノード実装は未着手
Phase H ░░░░░░░░░░   0%
```

**実機確認済み（2026-05-10 時点）**
- ESP32-S3-Zero × 2: Zone1/Node1 (COM3), Zone1/Node2 (COM4)
- UDP マルチキャスト 239.255.0.1:6454, 署名 0x53, CRC, Target 振り分け
- FIRE / OCEAN / STARFIELD 背景、5x8 ASCII テキスト描画、クロスフェード
- LIVE / HEALING / ENTRY / OFF シーン + execute_at_ms 相対遅延
- 30 分連続安定試験完走（safe mode 遷移なし）
- S08/S09 ノード別交互表示 + 片側歌詞表示を実機確認
- S11 歌詞フェードインの立ち上がり調整（ramp 短縮）を実機確認
- S14 Node別 CUSTOM メッセージのフェードイン/アウトを実機確認

**Phase G 完了タスク（2026-05-06 時点）**
- `tools/td_sat_sender.py` — TD から直接 UDP 送信するモジュール作成
- `touchdesigner-mcp-td/modules/led_control_example.py` — TD Script DAT テンプレート
- `tools/td_led_mcp_client.py` — MCP 経由 LED 制御 CLI（init/scene/bg/dimmer/lyrics/hb-start 等）
- `tools/td_hb_setup.py` — TD 内バックグラウンドスレッドによる HB 自動送信
- `tools/td_ui_builder.py` — TD パッチ UI ビルダー（LIVE/HEALING/ENTRY/OFF ボタン、DIMMER スライダー、歌詞入力）
- `tools/td_ui_builder.py` — Execute DAT に controller 自動初期化（lazy bootstrap）を追加
- TD MCP 経由の LIVE/HEALING/OFF シーン実機送信確認
- TD 内 HB スレッド (`hb_thread: running`) の安定動作確認
- TD Save Warning 修正（Socket/Thread 非 pickle オブジェクトを Storage に格納しない設計）
- TD ノードレイアウト整列（/project1, mcp_webserver_base 内, td_led_ui 内）

**制御元: TouchDesigner / Python テストツール**  
中央ノード（HomeLiveHall コントローラ）本体は未実装。  
現在は PC 上の `tools/led_udp_test_tool.py` と `tools/td_led_mcp_client.py` から制御。

**Phase G 残タスク（2026-05-10 時点）**
- AudioLINKCORE 受信プロトコルの具体化
- 中央ノード実装の最小スケルトン着手（controller 側）

**今日の残りアクション（2026-05-10）**  
→ 仕様・設計ドキュメントの整合更新（本更新）を確定し、次回は controller 最小実装開始

---

## リスクと対策

| リスク | 影響 | 対策 |
|---|---|---|
| PD トリガ基板で 12V が出ない | Phase B 停止 | 別の PD トリガ基板（CH224K 等）を予備調達する |
| ESP32-S3-Zero の GPIO 不足 | Phase C 再設計 | XIAO ESP32S3 Plus に切り替える |
| WS2812B と SDMMC の競合 | Phase D 停止 | SPI モード SDMMC または GPIO 再割り当てで回避 |
| TFT + I2S + I2C 同時動作で CPU 飽和 | Phase C 再設計 | FreeRTOS タスク優先度調整、または MCU 交替 |
| バッテリー 35W 実効出力不足 | Phase H 停止 | 5V 母線を 2A + LED 枝を別電源化で分離 |
