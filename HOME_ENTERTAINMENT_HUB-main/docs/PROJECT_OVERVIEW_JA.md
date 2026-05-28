# HOME_ENTERTAINMENT_HUB 解説書

最終更新: 2026-05-24

## 1. このプロジェクトは何を作るか

HOME_ENTERTAINMENT_HUB は、中央ノードと複数のLEDノードで構成する分散ライティングシステムです。

- 家庭向けモード: 少数ノードで高い可観測性を重視
- 大規模向けモード: 10万台規模を想定し、帯域保護を重視

## 2. ノード構成

1. 中央ノード (Controller)
- 役割: センサ入力、演出制御、UART/Wi-Fi配信
- 実装: `firmware/controller/main/app_main.c`

2. ローカルLEDノード (Lighting Node)
- 役割: UARTコマンド受信、LED描画
- 実装: `firmware/lighting_node/main/app_main.c`

3. サテライトLEDノード (Satellite Node)
- 役割: Wi-Fi/UDP受信、LED描画
- 実装: `firmware/satellite_node/src/main.cpp`

## 3. 通信方針の要点

- UART: ACKあり
- Wi-Fi: デフォルトACKなし
- STADIUM想定: ACK無効固定
- HOME想定: 条件付きで動的ACKを将来拡張として許可

詳細: `docs/software/communication_protocol.md`

## 4. 主要ディレクトリ

- `docs/` 設計・計画・手順ドキュメント
- `firmware/controller/` 中央ノード (ESP-IDF)
- `firmware/lighting_node/` ローカルLEDノード (ESP-IDF)
- `firmware/satellite_node/` サテライトLEDノード (PlatformIO/Arduino)
- `shared/include/` 共通プロトコル定義
- `tools/` テストツール、補助スクリプト

## 5. 直近の開発状況

- 中央ノードのESP-IDFビルド手順を固定化済み
- ACK方針を文書として確定済み
- 次回はESP32はんだ付け開始タスクから再開できる状態

## 6. 再開時の最短ルート

1. `docs/planning/next_session_esp32_kickoff_tasks_2026_05_17.md` を開く
2. はんだ付けと安全確認を完了
3. flash/monitor を実行
4. `docs/planning/day0_usb_xiao_hw_checklist_2026_05_16.md` に記録
