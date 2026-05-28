# ESP32-S3 初回接続トラブルシューティング記録

- **対象ボード:** Waveshare ESP32-S3-Zero（4MB Flash / 320KB RAM / 240MHz）
- **開発環境:** PlatformIO + espressif32 v6.11.0 + Arduino framework
- **記録日:** 2026-05-04

---

## 問題 1: Flash サイズ不一致によるブート失敗

### 症状

書き込み直後にシリアルモニタで以下のエラーが表示され、起動しない。

```
E (84) spi_flash: Detected size(4096k) smaller than the size in the binary image header(8192k)
```

### 原因

`esp32-s3-devkitc-1` ボード定義のデフォルト Flash サイズが **8MB** に設定されている。  
Waveshare ESP32-S3-Zero は **4MB Flash** であるため、ヘッダが実際のチップ容量と不一致になる。

### 解決策

`platformio.ini` に 4MB を明示指定し、Flash を完全消去してから再書き込みする。

```ini
board_build.flash_size = 4MB
board_upload.flash_size = 4MB
board_upload.maximum_size = 3342336
```

```powershell
pio run -e <env> -t erase
pio run -e <env> -t upload
```

---

## 問題 2: COM ポート占有による書き込み失敗

### 症状

書き込みコマンドを実行すると以下のエラーが発生する。

```
A fatal error occurred: Could not open COM3, the port doesn't exist
```

### 原因

**シリアルモニタが COM ポートを保持したまま** アップロードを実行したため、esptool がポートを開けない。

### 解決策

シリアルモニタを終了してからアップロードを実行する。  
また `platformio.ini` にポートを明示指定することで再現性を排除する。

```ini
upload_port = COM4
monitor_port = COM4
```

---

## 問題 3: rst:0x3 (RTC_SW_SYS_RST) リセットループ ← **主要問題**

### 症状

書き込みは成功するが、起動直後から以下のリセットループが無限に繰り返され、アプリコードが一切実行されない。

```
ESP-ROM:esp32s3-20210327
Build:Mar 27 2021
rst:0x3 (RTC_SW_SYS_RST),boot:0x8 (SPI_FAST_FLASH_BOOT)
Saved PC:0x403cd9aa
SPIWP:0xee
mode:DIO, clock div:1
...（繰り返し）
```

### 試行したが効果がなかった対策

| 試行内容 | 結果 |
|---------|------|
| FastLED ライブラリ削除 | 変化なし |
| GPIO 操作コード削除 | 変化なし |
| コードを Serial ハートビートのみに最小化 | 変化なし |
| `flash_mode = dio` → `qio`（デフォルト）に戻す | 変化なし |
| `ARDUINO_USB_CDC_ON_BOOT=1` の付与・削除 | 変化なし |
| ボード定義を `dfrobot_firebeetle2_esp32s3` に変更 | 変化なし（`CDC_ON_BOOT=1` のまま） |
| Flash 全消去後に再書き込み | 変化なし |
| ボード実機の交換（2台目に差し替え） | 変化なし → 個体問題ではないと判断 |

### 根本原因

**`-DARDUINO_USB_CDC_ON_BOOT=1` によるTinyUSB CDC初期化のタイムアウト。**

`ARDUINO_USB_CDC_ON_BOOT=1` を有効にすると、Arduinoフレームワークはブート時にTinyUSBのCDCスタックを初期化し、PCとのUSBシリアル接続確立を待機する。  
ESP32-S3 の RTC ウォッチドッグ（RWDT）がこの待機時間を超過と判定し、`RTC_SW_SYS_RST` リセットを発行し続ける。

### 解決策

`dfrobot_firebeetle2_esp32s3` ボード定義を使用し、**`ARDUINO_USB_CDC_ON_BOOT` を設定しない**（= ボード定義のデフォルト `ARDUINO_USB_MODE=1` を使用）。

**確定した `platformio.ini` 設定（`esp32-s3-alt4mb` 環境）：**

```ini
[env:esp32-s3-alt4mb]
platform  = espressif32
board     = dfrobot_firebeetle2_esp32s3
framework = arduino

; ボード定義のデフォルト(qio / 4MB / ARDUINO_USB_MODE=1)をそのまま使用
; ARDUINO_USB_CDC_ON_BOOT は設定しない
upload_port = COM4
monitor_port = COM4
upload_speed = 115200
monitor_speed = 115200

lib_deps =
    fastled/FastLED @ ^3.7.0
```

**動作確認：**  
Flash 全消去 → クリーンビルド → 書き込み後、シリアルモニタが静止（リセットループ消滅）。

---

## 各問題のまとめ

| # | 問題 | 原因 | 解決策 |
|---|------|------|--------|
| 1 | Flash サイズ不一致 | ボード定義のデフォルトが 8MB | `platformio.ini` に `flash_size = 4MB` を明示 |
| 2 | COM ポート占有 | モニタ実行中のアップロード | モニタ終了後にアップロード実行 |
| 3 | `rst:0x3` リセットループ | `ARDUINO_USB_CDC_ON_BOOT=1` でRWDTタイムアウト | `dfrobot_firebeetle2_esp32s3` ボード定義を使用し CDC_ON_BOOT を設定しない |

---

## 補足: ボード定義の違い

| 項目 | `esp32-s3-devkitc-1` | `dfrobot_firebeetle2_esp32s3` |
|------|---------------------|-------------------------------|
| デフォルト Flash | 8MB | **4MB** |
| Flash Mode | qio | qio |
| USB Mode | `ARDUINO_USB_MODE=1` | `ARDUINO_USB_MODE=1` |
| CDC on Boot | 明示なし（要手動設定） | **設定なし（安定）** |

Waveshare ESP32-S3-Zero を使用する場合は `dfrobot_firebeetle2_esp32s3` がほぼそのまま使える最も近いボード定義である。
