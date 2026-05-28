# チーム導入・引き継ぎガイド（職場環境向け）

最終更新: 2026-05-24
対象: 職場PCで複数人開発を開始するメンバー

## 1. このガイドの目的

このリポジトリを新しいPCに導入し、複数人で安全に継続開発するための最短手順をまとめる。

## 2. 最初に読む順番

1. `README.md`
2. `docs/PROJECT_OVERVIEW_JA.md`
3. `docs/software/communication_protocol.md`
4. `docs/planning/led_node_firmware_traceability.md`

## 3. 必要ツール（職場PC）

- Git
- VS Code
- Python 3.11+ (推奨)
- ESP-IDF 5.2 系
- PlatformIO (サテライトノードを扱う場合)

## 4. 初期セットアップ

1. リポジトリ取得
```powershell
git clone https://github.com/shinra71223-eng/HOME_ENTERTAINMENT_HUB.git
cd HOME_ENTERTAINMENT_HUB
```

2. Python 仮想環境
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. ESP-IDF ローカル環境（各PCローカル）
- `.esp-idf/` はローカル専用。Git管理しない。
- セットアップ後、controller は次で実行:
```powershell
powershell -ExecutionPolicy Bypass -File tools/esp_idf_controller.ps1 -Action env -ExportScriptPath .\.esp-idf\esp-idf\export.ps1 -Target esp32s3
powershell -ExecutionPolicy Bypass -File tools/esp_idf_controller.ps1 -Action build -ExportScriptPath .\.esp-idf\esp-idf\export.ps1 -Target esp32s3
```

## 5. ノード別の主な実装入口

- Controller: `firmware/controller/main/app_main.c`
- Lighting Node (UART): `firmware/lighting_node/main/app_main.c`
- Satellite Node (Wi-Fi): `firmware/satellite_node/src/main.cpp`
- 共通プロトコル: `shared/include/hub_protocol.h`

## 6. 通信方針（固定決定）

- UART: ACKあり
- Wi-Fi: デフォルトACKなし
- STADIUM想定: ACK無効固定
- HOME想定: 条件付きで動的ACKを将来拡張として導入

詳細は `docs/software/communication_protocol.md` を正とする。

## 7. チーム開発ルール（最小）

1. `main` へ直接コミットしない（緊急時を除く）
2. 作業は `feature/<topic>` ブランチで実施
3. PR でレビュー後にマージ
4. コミットは「1テーマ1コミット」を基本にする
5. 生成物・ローカル環境はコミットしない（`.esp-idf/`, `build/`, `.pio/` 等）

## 8. LEDノード書き込み追跡ルール（重要）

LEDノードへ書き込みを実施したら、必ず以下を記録する。

- 日時
- 対象ノード種別
- 書き込み元ソースパス
- GitコミットID
- 実行コマンド
- 結果

記録先: `docs/planning/led_node_firmware_traceability.md`

## 9. 引き継ぎ時チェックリスト

- [ ] 仕様変更が `docs/software/communication_protocol.md` に反映されている
- [ ] 実行手順が `docs/planning` に反映されている
- [ ] LED書き込み実績が追跡台帳に記録されている
- [ ] 未コミット差分を整理済み（`git status --short`）
- [ ] PR本文に「目的・変更点・未対応」を明記した

## 10. 次回開始時の推奨入口

次回の物理作業再開は以下から開始:
- `docs/planning/next_session_esp32_kickoff_tasks_2026_05_17.md`
