# ESP32 系ボード PlatformIO セットアップガイド

新しいESP32系ボードを接続するときのセットアップ手順・確認事項をまとめたガイドです。  
このプロジェクトでの実際のトラブル経験（→ [esp32s3_troubleshooting.md](esp32s3_troubleshooting.md)）を踏まえています。

---

## Step 1: ボードの仕様を事前に確認する

新しいボードを使う前に以下の情報を必ず調べておく。

| 確認項目 | 調べ方 | よくある落とし穴 |
|---------|--------|----------------|
| **Flash サイズ** | データシート / 購入ページ | 同名ボードでも 4MB / 8MB / 16MB の違いがある |
| **USB チップの種類** | ボード写真・回路図 | CP2102 / CH340 = UART変換チップあり / ESP32-S3 など = USB内蔵 |
| **ボード定義名** | PlatformIO Boards ページ | 近似ボードで代用する場合は Flash サイズを要確認 |

```powershell
# PlatformIO で対応ボード定義を検索する
pio boards espressif32 | Select-String "キーワード"

# 例: ESP32-S3 系の 4MB ボードを探す
pio boards espressif32 | Select-String "esp32s3" | Select-String "4MB"
```

---

## Step 2: ボードを PC に接続して認識を確認する

```powershell
pio device list
```

**確認ポイント：**
- COMポート番号（例: COM3, COM4）
- VID:PID（例: `303A:1001` = ESP32-S3 内蔵USB、`10C4:EA60` = CP210x）
- 認識されない場合 → USB ドライバのインストールが必要

### USB チップ別ドライバ

| VID:PID | チップ | ドライバ |
|---------|--------|---------|
| `303A:1001` | ESP32-S3/S2 内蔵USB | ドライバ不要（または Zadig で WinUSB） |
| `10C4:EA60` | Silicon Labs CP210x | CP210x Universal Windows Driver |
| `1A86:7523` | CH340 | CH340 ドライバ |
| `0403:6001` | FTDI FT232 | FTDI ドライバ |

---

## Step 3: platformio.ini を作成する

### テンプレート（UART変換チップ付きボード用）

CP2102 / CH340 などのUART変換チップが載っているボード（ESP32 無印、ESP32-C3 など）はこちら。

```ini
[env:myboard]
platform  = espressif32
board     = <board_id>        ; pio boards で調べた ID
framework = arduino

upload_port = COM4            ; pio device list で確認した番号
monitor_port = COM4
upload_speed = 921600         ; UART変換ボードは高速化可能
monitor_speed = 115200
```

### テンプレート（USB内蔵ボード用）

ESP32-S3 / ESP32-S2 など USB が直接チップに繋がっているボードはこちら。

```ini
[env:myboard]
platform  = espressif32
board     = <board_id>        ; 4MBのボード定義を使う
framework = arduino

; ★ ARDUINO_USB_CDC_ON_BOOT は設定しない（RWDTリセットループの原因になる）
; ボード定義のデフォルト ARDUINO_USB_MODE=1 をそのまま使う

upload_port = COM4
monitor_port = COM4
upload_speed = 115200         ; USB内蔵は 115200 が安定
monitor_speed = 115200
```

### Flash サイズが一致しない場合の追加設定

```ini
; ボード定義のデフォルトと実際の Flash サイズが違う場合のみ追加
board_build.flash_size = 4MB
board_upload.flash_size = 4MB
board_upload.maximum_size = 3342336  ; 4MB Flash の実効サイズ
```

---

## Step 4: 最初は最小コードで動作確認する

いきなり本番コードを書き込まず、まず **LED 点滅** または **Serial ハートビート** で起動を確認する。

### UART変換チップ付きボード用（Serial確認）

```cpp
#include <Arduino.h>

void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.println("[Boot] OK");
}

void loop() {
    static uint32_t tick = 0;
    Serial.printf("[HB] tick=%lu\n", (unsigned long)tick++);
    delay(1000);
}
```

### USB内蔵ボード用（GPIO点滅確認）

Serialを使わず GPIO の HIGH/LOW で動作確認する（Serial初期化がリセットを誘発することがある）。

```cpp
#include <Arduino.h>

static const int kLedPin = 10;  // 空きGPIOを指定

void setup() {
    pinMode(kLedPin, OUTPUT);
}

void loop() {
    digitalWrite(kLedPin, HIGH);
    delay(500);
    digitalWrite(kLedPin, LOW);
    delay(500);
}
```

---

## Step 5: 書き込み・動作確認

```powershell
# 初回は Flash を完全消去してからビルド・書き込みする
cd firmware\satellite_node
pio run -e myboard -t erase
pio run -e myboard -t upload

# シリアルモニタで確認
pio device monitor --port COM4 --baud 115200
```

**正常時のログ（USB内蔵ボード）：**
```
ESP-ROM:esp32s3-20210327
Build:Mar 27 2021
rst:0x1 (POWERON),boot:0x8 (SPI_FAST_FLASH_BOOT)   ← rst:0x1 = 正常電源投入リセット
mode:DIO, clock div:1
...
[Boot] OK
[HB] tick=0
```

**異常時のログ（リセットループ）：**
```
rst:0x3 (RTC_SW_SYS_RST),boot:0x8 (SPI_FAST_FLASH_BOOT)   ← 毎回 rst:0x3 が繰り返される
```

---

## トラブル別チェックリスト

### 書き込みが失敗する

- [ ] シリアルモニタを閉じてから書き込んでいるか
- [ ] `upload_port` が `pio device list` の結果と一致しているか
- [ ] ボードが書き込みモード（BOOT ボタン）に入れているか（自動リセット非対応ボードの場合）
- [ ] USB ケーブルがデータ通信対応か（充電専用ケーブルは書き込み不可）

### 書き込めるが起動しない / リセットループになる

- [ ] `board_build.flash_size` が実際のチップ容量と一致しているか（**最頻出**）
- [ ] USB内蔵ボードで `ARDUINO_USB_CDC_ON_BOOT=1` を設定していないか（**ESP32-S3 で頻出**）
- [ ] Flash 全消去（`pio run -t erase`）後に再書き込みしたか
- [ ] ボード定義が正しい `flash_mode`（qio/dio）を使っているか

### シリアル出力が文字化けする

- [ ] `monitor_speed` と `Serial.begin()` の baud rate が一致しているか（両方 `115200`）
- [ ] USB内蔵ボードで `monitor_filters = esp32_exception_decoder` を設定しているか（任意）

---

## ボード別 推奨設定メモ

| ボード | board ID | Flash | USB | 備考 |
|--------|----------|-------|-----|------|
| Waveshare ESP32-S3-Zero | `dfrobot_firebeetle2_esp32s3` | 4MB | 内蔵 | `CDC_ON_BOOT`設定しない |
| ESP32-DevKitC v4 | `esp32dev` | 4MB | CP2102 | upload_speed 921600 可 |
| ESP32-C3-DevKitM-1 | `esp32-c3-devkitm-1` | 4MB | 内蔵 | RISC-V コア |
| ESP32-S3-DevKitC-1 (N8) | `esp32-s3-devkitc-1` | **8MB** | 内蔵 | 4MBボードで使う場合は flash_size 要上書き |

---

## 参考リンク

- [PlatformIO Espressif32 Boards](https://docs.platformio.org/en/latest/boards/index.html#espressif32)
- [ESP32-S3 Technical Reference Manual](https://www.espressif.com/sites/default/files/documentation/esp32-s3_technical_reference_manual_en.pdf)
- [Arduino-ESP32 USB CDC on Boot](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/usb_cdc.html)
