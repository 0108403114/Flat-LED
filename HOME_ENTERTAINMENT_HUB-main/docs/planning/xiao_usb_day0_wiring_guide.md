# XIAO USB Day0 配線ガイド（メインノード MVP）

日付: 2026-05-16
方針: USB給電で先に機能成立、PD/DC-DC は後段で統合

## 1. 先に決めること
- MCU は XIAO ESP32S3 Plus 固定
- 給電は USB のみ
- まずは I2C と UART を成立させる

## 2. 配線順序（この順で実施）
1. GND 共通線を最初に敷く
2. XIAO を USB 接続して起動確認
3. I2C（BH1750 と INA228）を配線
4. UART（LEDノード連携）を配線
5. 最後に LED データ線を接続

## 3. 配線表（Day0 最小）

### 3.1 XIAO と I2C
- XIAO D0 (GPIO1) -> BH1750 SDA, INA228 SDA
- XIAO D1 (GPIO2) -> BH1750 SCL, INA228 SCL
- XIAO 3V3 -> BH1750 VCC, INA228 VCC
- XIAO GND -> BH1750 GND, INA228 GND

### 3.2 XIAO と LEDノード UART
- XIAO D6 (GPIO43, TX) -> LEDノード RX
- XIAO D7 (GPIO44, RX) -> LEDノード TX
- XIAO GND -> LEDノード GND

## 4. 通電時の安全ルール
- USB接続前に、5V と GND が短絡していないか導通確認
- 配線を抜き差しするときは USB を一度抜く
- まずは LED 輝度を上げない（最小テストのみ）
- 異常発熱があれば即 USB を抜く

## 5. 合格ライン（Day0）
- シリアルログで起動が見える
- I2C スキャンで BH1750 と INA228 が見える
- INA228 レジスタ読み取りログが出る
- UART で SET_COLOR が送れて LED が追従する
- 10分連続で再起動しない

## 6. つまずいた時の最短復旧
- I2C が見えない: SDA/SCL 配線を再確認、GND共通を再確認
- UART が無反応: TX/RX の交差接続を確認、GND共通を再確認
- 起動しない: USBケーブルをデータ対応品に変更
