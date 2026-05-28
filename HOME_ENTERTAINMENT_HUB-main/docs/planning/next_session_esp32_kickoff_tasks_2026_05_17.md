# 次回開始タスク（ESP32準備から）

日付: 2026-05-17
目的: 次回セッションを「ESP32はんだ付け」から迷わず開始する。

## 0. スタート宣言
- 開始点: XIAO ESP32S3 Plus のはんだ付け
- ゴール: flash と monitor で起動ログ確認まで

## 1. 作業順

1. はんだ付け準備
- [ ] 部材展開: XIAO / ヘッダ / はんだごて / はんだ / テスター
- [ ] ヘッダ向きと取り付け高さを確定

2. はんだ付け
- [ ] 仮固定（四隅）
- [ ] 全ピン本はんだ
- [ ] ブリッジ有無チェック

3. 安全確認
- [ ] 5V-GND 導通確認（短絡なし）
- [ ] 3V3-GND 導通確認（短絡なし）

4. 初回書き込み
- [ ] flash 実行
- [ ] monitor 実行

実行コマンド:
```powershell
powershell -ExecutionPolicy Bypass -File tools/esp_idf_controller.ps1 -Action flash -ExportScriptPath .\.esp-idf\esp-idf\export.ps1 -Target esp32s3
powershell -ExecutionPolicy Bypass -File tools/esp_idf_controller.ps1 -Action monitor -ExportScriptPath .\.esp-idf\esp-idf\export.ps1 -Target esp32s3
```

5. Day0記録
- [ ] docs/planning/day0_usb_xiao_hw_checklist_2026_05_16.md の 1〜2章を記入

## 2. 完了条件（次回）
- [ ] はんだ付け完了
- [ ] flash 成功
- [ ] monitor で起動ログを確認

## 3. 補足（ACK方針）
- UART: ACK あり
- Wi-Fi: デフォルト ACK なし
- STADIUM: ACK 無効固定
