# ESP-IDF 起動固定ガイド（XIAO / controller）

日付: 2026-05-16
対象: Windows PowerShell

## 目的
ESP-IDF 環境起動の手順差をなくし、毎回同じコマンドで build/flash/monitor できるようにする。

## 追加済みスクリプト
- tools/esp_idf_controller.ps1

このスクリプトは次を自動実行する。
- export.ps1 の探索
- ESP-IDF 環境の有効化
- controller プロジェクトで idf.py 実行
- target を esp32s3 に自動整合（XIAO 前提）
- flash/monitor 時の COM ポート自動選択（Port 未指定または auto）

## 基本コマンド

このワークスペースで確定したローカルパス:
- C:\Projects\02_HomeLiveHall_Trial01\.esp-idf\esp-idf\export.ps1

### 1) 環境確認だけ
powershell -ExecutionPolicy Bypass -File tools/esp_idf_controller.ps1 -Action env

### 1.2) この環境の確定コマンド（推奨）
powershell -ExecutionPolicy Bypass -File tools/esp_idf_controller.ps1 -Action env -ExportScriptPath .\.esp-idf\esp-idf\export.ps1 -Target esp32s3

### 1.1) ESP-IDF が標準外パスにある場合
powershell -ExecutionPolicy Bypass -File tools/esp_idf_controller.ps1 -Action env -ExportScriptPath "C:\path\to\esp-idf\export.ps1"

### 2) ビルド
powershell -ExecutionPolicy Bypass -File tools/esp_idf_controller.ps1 -Action build

### 2.1) target を明示したビルド
powershell -ExecutionPolicy Bypass -File tools/esp_idf_controller.ps1 -Action build -Target esp32s3

### 3) 書き込み（COM ポート指定）
powershell -ExecutionPolicy Bypass -File tools/esp_idf_controller.ps1 -Action flash -Port COM5

### 3.1) COM 自動選択で書き込み
powershell -ExecutionPolicy Bypass -File tools/esp_idf_controller.ps1 -Action flash -Port auto -ExportScriptPath .\.esp-idf\esp-idf\export.ps1 -Target esp32s3

### 4) モニタ
powershell -ExecutionPolicy Bypass -File tools/esp_idf_controller.ps1 -Action monitor -Port COM5

### 4.1) COM 自動選択でモニタ
powershell -ExecutionPolicy Bypass -File tools/esp_idf_controller.ps1 -Action monitor -Port auto -ExportScriptPath .\.esp-idf\esp-idf\export.ps1 -Target esp32s3

### 5) 一括（build + flash + monitor）
powershell -ExecutionPolicy Bypass -File tools/esp_idf_controller.ps1 -Action full -Port COM5

### 5.1) この環境の確定コマンド（例: COM5）
powershell -ExecutionPolicy Bypass -File tools/esp_idf_controller.ps1 -Action build -ExportScriptPath .\.esp-idf\esp-idf\export.ps1 -Target esp32s3
powershell -ExecutionPolicy Bypass -File tools/esp_idf_controller.ps1 -Action flash -Port COM5 -ExportScriptPath .\.esp-idf\esp-idf\export.ps1 -Target esp32s3
powershell -ExecutionPolicy Bypass -File tools/esp_idf_controller.ps1 -Action monitor -Port COM5 -ExportScriptPath .\.esp-idf\esp-idf\export.ps1 -Target esp32s3

## つまずき対処
- export.ps1 が見つからない:
  - ESP-IDF をインストールする
  - 既存インストール先が標準外なら ExportScriptPath で明示指定する
- idf.py が見つからない:
  - export が未適用の可能性。Action env を再実行して確認する
- COM ポート不明:
  - デバイスマネージャで確認し、Port 引数へ指定する

## Day0 推奨実行順
1. Action env
2. Action build
3. Action flash -Port COMx
4. Action monitor -Port COMx

補足:
- XIAO ESP32S3 の場合は Target は esp32s3 を使用する。
