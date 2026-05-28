# 今日のGoal（2026-05-17 / はんだ前）

## 今日の最重要Goal
XIAO はんだ付け前に、ソフト側を「書き込み直前状態」まで進める。

## 成功条件（DoD）
- [x] UART dryrun でフレーム整合確認
- [x] controller を esp32s3 で再現ビルド
- [x] ESP-IDF 起動手順を固定化（export.ps1 明示指定）
- [x] ACK 方針を確定（UART ACKあり / Wi-FiデフォルトACKなし / STADIUM ACK無効固定）
- [ ] 実機接続後に使う flash / monitor コマンドを即実行できる状態

## 今日ここまでの実績
1. dryrun all 成功（Exit Code 0）
2. `-Action env` で IDF 環境有効化確認
3. `-Action build` で Project build complete 確認
4. ACK 最終決定を仕様へ反映（HOME動的ACKは検証プロファイルで段階導入）

## 次にやる順番（はんだ後すぐ）
1. USB 接続
2. flash 実行
3. monitor 実行
4. Day0 チェックシートへ実測を記入

## 実行コマンド（コピペ用）
```powershell
powershell -ExecutionPolicy Bypass -File tools/esp_idf_controller.ps1 -Action flash -ExportScriptPath .\.esp-idf\esp-idf\export.ps1 -Target esp32s3
powershell -ExecutionPolicy Bypass -File tools/esp_idf_controller.ps1 -Action monitor -ExportScriptPath .\.esp-idf\esp-idf\export.ps1 -Target esp32s3
```
