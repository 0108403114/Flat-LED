# 再開用申し送りメモ

## このファイルの目的

- 次回作業再開時に、何が決まっていて何が未決かをすぐ把握する
- 次にやる作業の優先順位を迷わず判断できるようにする
- 設計判断の前提を見失わないようにする

## 現在の到達点

> **最終更新**: 2026-05-04

- プロジェクト全体の構想整理は完了している
- 中央ノードと LED ノードの責務分離は確定している
- MVP は中央ノード 1 台 + ローカル LED ノード 1 台で進める方針が確定している
- LED 消費電力に関する参考資料と注意書きは更新済み
- 通信の初期方針、ノード ID 方針、個別制御方針は初期仕様として固定済み
- firmware/controller と firmware/lighting_node には ESP-IDF の最小骨組みがある
- **firmware/satellite_node に PlatformIO + FastLED + UART 受信の実動作ファームウェアがある（2026-05-04 完成）**
- **PC → ESP32-S3-Zero (COM3) → WS2812B LED カラー制御を実機で確認済み（2026-05-04）**

## 2026-05-04 作業内容

### 完了したこと

1. **UART プロトコル実装**: `hub_protocol.h` にフレーム定義・CRC-8/MAXIM エンコード/デコードを実装
2. **`firmware/satellite_node` 新規作成**: PlatformIO + Arduino framework + FastLED 3.7.0 で LED ノードファームウェアを実装
   - WS2812B ×880 (GPIO12 / GPIO13 各 440 個)
   - USB CDC 受信 + UART1 (GPIO17/18) 受信の二重経路
   - ハートビートタイムアウト 3 秒でセーフティ白 5% 遷移
3. **PC テストツール `tools/led_uart_test_tool.py`**: color / brightness / stop / heartbeat / stream / burstcolor / listen コマンドを実装
4. **ストリーム送信ベンチ**: 120fps / 240 frames / Dropped:0 を実測確認
5. **根本的な不具合を 3 件解消**:
   - `setDTR(False)` が USB CDC の受信をブロックしていた → 削除
   - `ARDUINO_USB_CDC_ON_BOOT=1` が未設定で `Serial` が機能しなかった → `platformio.ini` に追加
   - `loop()` で USB エラー時に UART1 へフォールスルーしない設計バグ → 修正
6. **実機確認**: `SET_COLOR 255 0 0` → 赤、`SET_COLOR 0 0 255` → 青 の切り替えを目視確認

### 判明した重要な知見

- `dfrobot_firebeetle2_esp32s3` ボード定義は `ARDUINO_USB_MODE=1` (USB-JTAG/Serial) で動作する
- `ARDUINO_USB_CDC_ON_BOOT=1` を `build_flags` に追加しないと Arduino `Serial` がホスト接続前にデータを送出しない
- pyserial は `.venv` には入っておらず、プロジェクトルートの venv (`c:/Projects/02_HomeLiveHall_Trial01/.venv/`) に入れる必要がある
- Python ツールの実行コマンド: `c:/Projects/02_HomeLiveHall_Trial01/.venv/Scripts/python.exe tools/led_uart_test_tool.py`

## 次回作業の優先順位

### 最優先: UART1 直結テスト (Phase D 残項目)

USB CDC 経路での制御は確認済み。次は中央ノードとの実接続に近い UART1 (GPIO17/18) 直結での検証。

**必要なもの**: USB-UART アダプタ (CH340G など)  
**配線**: PC USB-UART アダプタ TX → ESP32 GPIO18 (RX)、GND 共通

```
python tools/led_uart_test_tool.py --port COM4 color 255 0 0
```
※ `led_uart_test_tool.py` の `port='COM3'` を引数化する必要がある

### 次点: TouchDesigner 統合 (Phase E)

COM3 経由で `hub_protocol` UART フレームを TouchDesigner から Python TOP で送信する検証。
フレームフォーマットは `led_uart_test_tool.py` の `HubUartFrame.encode()` がそのまま参照できる。

### その後: microSD アセット再生 (Phase D 残項目)

`.led` ファイル形式に従ったテストデータ作成 → microSD 書き込み → `PLAY_ASSET` コマンドで再生確認。

## 現時点で確定している重要前提

### ユースケース

1. 中央ノード + ローカル LED ノードをリビングテーブルに常設し、ランタンのように空間へなじませる
2. ライブ映像視聴時に、音に合わせてリビング全体をライブ空間化する
3. 就寝前に音楽に合わせて、ヒーリング空間を作る

### システム構成

- 中央ノード: 入力解析、UI、シーン決定、各ノードへの制御配信、家庭用常設機器としての単体起動
- ローカル LED ノード: 中央ノードと UART 直結、microSD からアセットを読み、ローカル描画する
- サテライト LED ノード: 中央ノードから Wi-Fi で制御を受け、microSD からアセットを読み、ローカル描画する

### ハード前提

- 中央ノード MCU 第一候補: Seeed Studio XIAO ESP32S3 Plus
- 中央ノード入力: INMP441 マイク、ボタン、AudioLINKCORE 外部入力
- 中央ノード表示: GMT020-01 TFT
- LED ノード: ESP32-S3 + microSD + WS2812 系 LED
- LED ノードは 4 から 6 ライン並列を最終目標とする
- MVP は 1 ライン少数 LED から始める

### 通信前提

- 中央ノード -> ローカル LED ノード: UART
- 中央ノード -> サテライト LED ノード: Wi-Fi
- 初期版コマンドは以下の 5 種
  - メインアニメーションプリセット
  - エフェクトプリセット
  - カラーパレットプリセット
  - テキスト情報
  - 強制リセット

### 初期仕様として固定済みの挙動

- サテライト識別 ID は 1 から 16 程度の短い数値
- 全体一斉制御と個別ノード指定制御を扱う
- 個別ノード指定演出は標準 3 秒で全体同期へ復帰する
- ACK は UART のみ、Wi-Fi は基本 ACK なし
- Wi-Fi の重要コマンドは 50 ms 間隔で 3 回送る
- group_id は将来拡張用に予約し、0 は全体扱い
- テキストは表示にも内部ラベルにも使う
- テキスト表示初期状態はローカル LED ノードだけ有効
- エフェクトはアニメーションへ簡易ブレンドで重ねる
- FastLED は WS2812 送出層だけに使う

### 電源前提

- WS2812 系の 60 mA / LED は理論最大参考値であり、通常運用値ではない
- 各 LED マトリクスは約 2.5 A 以内に制限して運用する前提
- 各 LED マトリクス用の電源は 5 V / 3 A 級を基本候補とする
- 中央ノード電源と LED ノード電源は分離前提で考える

## まだ決め切れていないこと

### 最優先で詰めるべきこと

1. 中央ノードの GPIO 割り当て
2. LED ノードの GPIO 割り当て
3. LED ノードで使う具体的な ESP32-S3 ボード
4. MVP で使う LED 本数と 1 ライン構成
5. MVP 用 UART パケットの最小構成
6. MVP 用アセット形式とディレクトリ構成

### 次段階で詰めること

1. 強制リセットの最終意味を MCU 再起動まで含めるか
2. テキスト情報の用途を表示中心にするか演出埋め込みも広げるか
3. Wi-Fi 完全版パケットの厳密定義
4. group_id と将来のゾーン制御の拡張方法
5. AudioLINKCORE 受信仕様の詳細

## 次回再開時の推奨スタート地点

次回は、以下の順番で着手するのが最短です。

1. 中央ノードの MVP GPIO 割り当て表を作る
2. LED ノードの MVP GPIO 割り当て表を作る
3. LED ノードの MVP 構成を 1 ラインで仮確定する
4. UART 最小パケット仕様を仮確定する
5. その後に firmware/controller と firmware/lighting_node の最小実装へ入る

## 次回すぐやるタスクリスト

### Task 1: 中央ノード GPIO 割り当て

- TFT
- INMP441
- ボタン
- UART TX/RX
- 必要ならデバッグ用予備ピン

### Task 2: LED ノード GPIO 割り当て

- WS2812 1 ライン出力
- microSD
- UART RX/TX
- 状態表示 LED
- 将来の 4 ライン化余地

### Task 3: MVP 条件固定

- LED 本数
- 初期輝度
- 電流制限条件
- 電源構成

### Task 4: 最小通信仕様

- Sync Preset の最小フィールド
- Force Reset の最小フィールド
- UART ACK の最小形式

### Task 5: 最小動作確認

- 中央ノード単体
- LED ノード単体
- UART 接続動作

## 参照すべきファイル

- docs/planning/current_architecture_summary.md
- docs/planning/implementation_plan.md
- docs/software/communication_protocol.md
- docs/software/software_architecture.md
- docs/hardware/hardware_requirements.md
- docs/hardware/parts_list.md
- docs/hardware/led_power_consumption_reference.md
- shared/include/hub_protocol.h

## 注意点

- 古い LED 電流の理論最大値をそのまま設計値として使わない
- LED ノードはまず 1 ライン少数 LED から始める
- XIAO ESP32S3 Plus は有力候補だが、GPIO と SDMMC の実装しやすさは未確定
- 最終構成を先に作ろうとせず、MVP の成立性確認を優先する
- 本プロジェクトの中央ノードは PC 代替ではなく、家庭内に常設する本番機として成立させる前提で考える