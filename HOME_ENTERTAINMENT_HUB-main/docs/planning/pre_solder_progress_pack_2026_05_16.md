# はんだ前に進めるパック（2026-05-16）

目的:
- XIAO のはんだ付け完了前に、ソフトと手順を最大限前倒しする。
- はんだ完了後は flash と配線確認だけで Day0 検証に入れる状態を作る。

## 0. 2026-05-17 実行ログ（本日）
- [x] UART フレーム dryrun 実行済み
  - コマンド: `c:/Projects/02_HomeLiveHall_Trial01/.venv/Scripts/python.exe tools/led_uart_test_tool.py dryrun all`
  - 結果: Exit Code 0
- [x] ESP-IDF 環境確認（esp32s3 指定）
  - コマンド: `powershell -ExecutionPolicy Bypass -File tools/esp_idf_controller.ps1 -Action env -ExportScriptPath .\.esp-idf\esp-idf\export.ps1 -Target esp32s3`
  - 結果: idf.py 利用可能
- [x] controller 再現ビルド（esp32s3 指定）
  - コマンド: `powershell -ExecutionPolicy Bypass -File tools/esp_idf_controller.ps1 -Action build -ExportScriptPath .\.esp-idf\esp-idf\export.ps1 -Target esp32s3`
  - 結果: Project build complete
- [x] ACK 方針の最終決定を反映
  - 決定: UART ACKあり / Wi-FiデフォルトACKなし / STADIUM ACK無効固定
  - 反映先: `docs/software/communication_protocol.md`, `docs/planning/ack_architecture_review_2026_05_17.md`

本日時点の残タスク（はんだ前）:
- [ ] flash コマンド最終確認（実機接続後に実行）
- [ ] monitor コマンド最終確認（実機接続後に実行）
- [ ] Day0 チェックシートに実測記録の準備欄を埋める

## A. いま完了済み
- controller の ESP-IDF ローカル環境構築
- esp32s3 ターゲットで build 成功
- UART テストツールの dry-run 対応
- ESP-IDF 実行スクリプトの COM 自動検出対応

## B. はんだ前に実行するチェック（PCのみ）

### 1) UART フレーム整合（ハード不要）
python tools/led_uart_test_tool.py dryrun all

確認ポイント:
- 各コマンドのバイト列が出る
- decode が OK になる
- CRC が一致する

### 2) controller ビルド再現性
powershell -ExecutionPolicy Bypass -File tools/esp_idf_controller.ps1 -Action build -ExportScriptPath .\.esp-idf\esp-idf\export.ps1 -Target esp32s3

確認ポイント:
- Project build complete が出る
- target が esp32s3 になっている

### 3) 書き込みコマンド準備（はんだ後すぐ使う）
powershell -ExecutionPolicy Bypass -File tools/esp_idf_controller.ps1 -Action flash -ExportScriptPath .\.esp-idf\esp-idf\export.ps1 -Target esp32s3

備考:
- Port 未指定時は COM 自動検出
- 複数 COM がある場合はログに候補表示

## C. はんだ完了直後にやる最短3手順
1. USB 接続
2. flash 実行（上記コマンド）
3. monitor 実行

monitor コマンド:
powershell -ExecutionPolicy Bypass -File tools/esp_idf_controller.ps1 -Action monitor -ExportScriptPath .\.esp-idf\esp-idf\export.ps1 -Target esp32s3

## D. Day0 へ接続
- 実測記録は day0 チェックシートに記入:
  - docs/planning/day0_usb_xiao_hw_checklist_2026_05_16.md
- 配線はガイド順に実施:
  - docs/planning/xiao_usb_day0_wiring_guide.md

## E. 次回開始タスク（ESP32準備スタート版）

次回はこの順で開始する（上から順に実施）。

1. はんだ付け準備（5-10分）
- [ ] XIAO ESP32S3 Plus 本体、ピンヘッダ、はんだごて、はんだ、テスターを机上に展開
- [ ] 極性・向き・取り付け面を最終確認

2. XIAO はんだ付け（15-30分）
- [ ] ピンヘッダ仮固定
- [ ] 四隅を先にはんだし、垂直を確認
- [ ] 全ピン本はんだ
- [ ] ブリッジ有無を目視確認

3. 通電前安全確認（5分）
- [ ] 5V と GND の短絡チェック
- [ ] 3V3 と GND の短絡チェック

4. 初回起動（10分）
- [ ] USB 接続
- [ ] `tools/esp_idf_controller.ps1 -Action flash` 実行
- [ ] `tools/esp_idf_controller.ps1 -Action monitor` 実行

5. Day0 記録開始（10分）
- [ ] `docs/planning/day0_usb_xiao_hw_checklist_2026_05_16.md` の 1〜2章を記入

次回の完了条件（最小）:
- [ ] はんだ付け完了
- [ ] flash 成功
- [ ] monitor で起動ログ確認
