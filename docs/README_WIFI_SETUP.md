# Wi-Fi LED Control Setup Guide

## 概要

このプロジェクトは、ESP32-S3 を中心としたワイヤレス LED 制御システムです。

### システムアーキテクチャ

```
┌─────────────────────────────────────────────────────────────┐
│                 家の Wi-Fi ネットワーク                        │
│               FXC-5G-E25OZX / 2.4GHz/5GHz                    │
└─────────────────────────────────────────────────────────────┘
         │                              │
         ↓                              ↓
    ┌─────────┐              ┌──────────────────┐
    │   PC    │              │   ESP32-S3       │
    │ (Python)│◄────UDP───────┤  中央ノード      │
    └─────────┘   ポート5000  │  (controller)    │
                              └──────────────────┘
                                      │
                                ┌─────┴─────┐
                                │ UART      │ I2C
                                ↓           ↓
                          ┌──────────┐  ┌─────────┐
                          │ LED Node │  │ BH1750  │
                          │ UART受信 │  │ INA228  │
                          └──────────┘  └─────────┘
                                │
                                ↓
                          ┌──────────────┐
                          │ WS2812B LED  │
                          │  × 880 個    │
                          └──────────────┘
```

---

## セットアップ手順

### ステップ 1: 必要なツールをインストール

#### Windows の場合

**Python 3.x** をインストール：
- https://www.python.org/downloads/
- インストール時に「Add Python to PATH」にチェック

**ESP-IDF** をインストール：
- https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/get-started/windows-setup.html

#### Linux / macOS の場合

```bash
# Python (通常既にインストール済み)
python3 --version

# ESP-IDF
git clone --recursive https://github.com/espressif/esp-idf.git
cd esp-idf
./install.sh
source export.sh
```

### ステップ 2: 中央ノード（Controller）のセットアップ

#### 2.1 ファームウェアをコンパイル

```bash
# プロジェクトディレクトリに移動
cd firmware/controller

# ビルド
idf.py build

# ボードを接続して書き込み
idf.py -p /dev/ttyUSB0 flash  # Linux/macOS
idf.py -p COM3 flash           # Windows
```

**ボードが見つからない場合：**
- USB ケーブルが正しく接続されているか確認
- ドライバをインストール（CP2102 チップの場合）

#### 2.2 シリアルモニタで起動ログを確認

```bash
idf.py -p /dev/ttyUSB0 monitor  # Linux/macOS
idf.py -p COM3 monitor           # Windows
```

**期待される出力例：**
```
I (1234) wifi:connected to ap SSID:FXC-5G-E25OZX password:cu4nm3s4
I (1567) tcpip_adapter: sta ip: 192.168.1.123, mask: 255.255.255.0, gw: 192.168.1.1
I (1890) controller: UDP socket listening on port 5000
```

**IP アドレスをメモしてください！** （例：`192.168.1.123`）

### ステップ 3: LED ノード（Lighting Node）のセットアップ

#### 3.1 ファームウェアをコンパイル

```bash
# プロジェクトディレクトリに移動
cd firmware/lighting_node

# ビルド
idf.py build

# ボードを接続して書き込み（別のボード）
idf.py -p /dev/ttyUSB1 flash  # 別のシリアルポート
```

#### 3.2 接続確認

LED ノードが起動したら、シリアルモニタで以下のログが出るまで待ります：

```
I (1000) lighting_node: waiting for UART commands...
```

### ステップ 4: PC の IP アドレスを確認

```bash
# Windows
ipconfig

# Linux / macOS
ifconfig
```

**IPv4 アドレス** をメモしてください（例：`192.168.1.100`）

### ステップ 5: テストスクリプトを実行

#### 方法 A: シンプルテスト（推奨）

```bash
cd tools

# 中央ノードの IP を指定
python test_wifi_led_simple.py 192.168.1.123

# RGB 循環が始まります
```

#### 方法 B: 自動検出（IP を自動検索）

```bash
python test_wifi_led_auto_detect.py

# ローカルネットワークを自動スキャンして ESP32 を検索
```

#### 方法 C: 対話型コントローラ（リアルタイム制御）

```bash
python test_wifi_led_interactive.py

# IP を入力後、対話型プロンプトで色を選択
# プリセット色: 1-8
# カスタム色: 255,128,0 または #FF8000
```

---

## トラブルシューティング

### ESP32 が Wi-Fi に接続できない

**チェックリスト：**

1. **SSID とパスワードが正しいか**
   ```c
   // firmware/controller/main_wifi.c を確認
   #define WIFI_SSID "FXC-5G-E25OZX"
   #define WIFI_PASS "cu4nm3s4"
   ```

2. **2.4GHz Wi-Fi をサポートしているか**
   - 5GHz のみでは接続できません
   - ルーター設定を確認

3. **ESP32-S3 を再起動**
   ```bash
   idf.py -p COM3 monitor
   # Ctrl+T → Ctrl+A で再起動
   ```

### PC から ESP32 に接続できない

**チェックリスト：**

1. **IP アドレスが正しいか確認**
   ```bash
   ping 192.168.1.123
   ```

2. **ファイアウォールが UDP ポート 5000 をブロックしていないか**

3. **PC と ESP32 が同じネットワークにいるか**
   - 2.4GHz Wi-Fi に接続しているか確認

### LED が点灯しない

**チェックリスト：**

1. **LED ノードがシリアルコマンドを受け取っているか**
   ```bash
   idf.py -p /dev/ttyUSB1 monitor
   # "SET_COLOR" ログが出ているか確認
   ```

2. **GPIO4/GPIO5 が正しく接続されているか**
   ```
   ESP32 GPIO4 ──── LED Strip 1
   ESP32 GPIO5 ──── LED Strip 2
   ```

3. **LED の電源が十分か**
   - 880個の LED には多くの電流が必要です
   - 専用の電源供給をおすすめします

---

## 次のステップ

- **Wi-Fi をさらに最適化**
- **複数の LED ノードをサポート**
- **スマホアプリで制御**
- **Web UI でリアルタイム制御**

---

## 参考資料

- [ESP-IDF ドキュメント](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/)
- [WS2812B LED ストリップ仕様](https://cdn-shop.adafruit.com/datasheets/WS2812B.pdf)

---

**問題が発生した場合は、Issue を作成してください！** 🙏
