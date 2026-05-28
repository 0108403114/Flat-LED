# 運用切り替え手順（Wi-Fi / Bluetooth）

作成日: 2026-05-10  
対象: HOME_ENTERTAINMENT_HUB / Satellite Node

## 目的

- 既存の PC/TouchDesigner + Wi-Fi 運用へ即時に戻せるようにする。
- スマホ + Bluetooth 運用へ切り替える手順を固定化する。

## 前提

- 作業ディレクトリ:
  - `C:\Projects\02_HomeLiveHall_Trial01\firmware\satellite_node`
- Node1: COM3
- Node2: COM4

---

## 1. 既存 PC/TD + Wi-Fi へ戻す

### 1-1. Node1 書き込み

```bash
pio run -e esp32-s3-zero -t upload
```

### 1-2. Node2 書き込み

```bash
pio run -e esp32-s3-alt4mb -t upload
```

### 1-3. 戻し後の運用

- TouchDesigner / PC 送信スクリプトで UDP (239.255.0.1:6454) を使用
- 従来の Wi-Fi テストシーケンスを実行

---

## 2. スマホ + Bluetooth へ切り替える

### 2-1. Node1 書き込み（BLE版）

```bash
pio run -e esp32-s3-ble-node1 -t upload
```

### 2-2. Node2 書き込み（BLE版）

```bash
pio run -e esp32-s3-ble-node2 -t upload
```

### 2-3. スマホ側 Python 送信

```bash
python tools/mobile_ble_sequence.py --address BLE機器アドレス
```

例:

```bash
python tools/mobile_ble_sequence.py --address AA:BB:CC:DD:EE:FF
```

### 2-4. スマホ用 BLE コントローラアプリ（対話型）

スマホから LED Node へ接続し、手動送信やテストシーケンス送信を行う場合は以下を使用する。

```bash
python tools/mobile_ble_controller_app.py
```

アプリ機能:

- BLE デバイススキャン
- Node への接続 / 切断
- HEARTBEAT 即時送信
- BG / Dimmer のクイック CTRL 送信
- 歌詞 1 行送信
- 30 秒テストシーケンス送信

依存パッケージ（初回のみ）:

```bash
pip install bleak
```

---

## 3. クイック確認チェック

- Wi-Fiに戻したい場合: `esp32-s3-zero` / `esp32-s3-alt4mb` を書き込む
- BLEにしたい場合: `esp32-s3-ble-node1` / `esp32-s3-ble-node2` を書き込む
- どちらも書き込み後に再起動されるため、実機表示を確認してから送信開始する

---

## 4. トラブル時メモ

- 書き込み失敗時: COMポート番号を確認
- BLE送信失敗時: `--address` を再確認（接続先ノードのBLEアドレス）
- 運用を戻したい時: セクション1の2コマンドを再実行すれば復帰可能

---

## 5. PC / Wi-Fi なし当日デモ（スマホ単独）

前提:

- Node1 / Node2 は事前に BLE 版ファームを書き込み済み
  - `esp32-s3-ble-node1`
  - `esp32-s3-ble-node2`
- スマホ側 Python 実行環境と `bleak` が導入済み

### 5-1. 今日の S01-S15 テストシーケンスを実行

```bash
python tools/mobile_ble_today_sequence.py --addresses NODE1_BLE_MAC,NODE2_BLE_MAC
```

例:

```bash
python tools/mobile_ble_today_sequence.py --addresses AA:BB:CC:DD:EE:01,AA:BB:CC:DD:EE:02
```

このコマンドで、今日作成した S01-S15 の演出シーケンスを BLE 経由で送信する。

### 5-2. 手動操作が必要な場合

対話型アプリを起動して、スキャン・接続・任意送信を行う:

```bash
python tools/mobile_ble_controller_app.py
```
