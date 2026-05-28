# HOME_ENTERTAINMENT_HUB

リビング空間を音に合わせて演出する分散型ライティングシステムです。

初期版では次の 2 つの使用シーンに対応します。

1. ライブ映像視聴時に、音のピークやエネルギーに合わせてリビング全体をライブ空間化する。
2. 就寝前に音楽に合わせて、低刺激で没入感のあるヒーリング空間を作る。

## システム概要

- 中央ノード: ESP32-S3 ベース。マイク入力の解析、シーン管理、外部制御受信、各照明ノードへの配信を担当。
- ローカル LED ノード: ESP32-S3 ベース。中央ノードと UART で接続し、プリセット情報を受けてローカルの LED マトリックスを描画。
- サテライト LED ノード: ESP32-S3 ベース。中央ノードから Wi-Fi でプリセット情報を受けて各 LED マトリックスを描画。
- PC 再生時: AudioLINKCORE が解析済みの制御信号を USB またはシリアルで中央ノードへ送信。

## まず読むドキュメント

- 全体解説: [docs/PROJECT_OVERVIEW_JA.md](docs/PROJECT_OVERVIEW_JA.md)
- LEDノード書き込み追跡: [docs/planning/led_node_firmware_traceability.md](docs/planning/led_node_firmware_traceability.md)
- チーム導入・引き継ぎガイド: [docs/planning/team_handover_onboarding_guide_2026_05_24.md](docs/planning/team_handover_onboarding_guide_2026_05_24.md)

## 開発方針

- 主開発基盤は ESP-IDF。
- ローカル LED ノードは UART、サテライト LED ノードは家庭内 Wi-Fi ネットワークで接続する。
- 音声そのものは各ノードへ送らず、中央ノードが演出パラメータへ変換して配信する。
- 初期版では HDMI 直接取得と TV Bluetooth 音声取得は対象外。

## 通信で配る主情報

1. メインアニメーション プリセット番号
2. エフェクト プリセット番号
3. カラーパレット プリセット番号
4. テキスト情報
5. 強制リセット指示

## ディレクトリ構成

- docs/specifications: 使用シーンと仕様書
- docs/hardware: 部品、ブロック図、回路設計論点
- docs/software: ソフト構成、モジュール責務、通信設計
- docs/planning: 実装計画と検証計画
- firmware/controller: 中央ノード用 ESP-IDF アプリ
- firmware/lighting_node: 照明ノード用 ESP-IDF アプリ
- shared/include: 中央ノードと照明ノードの共通定義
- tools: 文書生成や補助スクリプト

## 運用切り替えとスマホ送信

- 運用切り替え手順: [docs/planning/operation_switch_guide_wifi_ble.md](docs/planning/operation_switch_guide_wifi_ble.md)
- スマホ BLE 一括シーケンス送信: [tools/mobile_ble_sequence.py](tools/mobile_ble_sequence.py)
- スマホ BLE 今日のS01-S15送信: [tools/mobile_ble_today_sequence.py](tools/mobile_ble_today_sequence.py)
- スマホ BLE 対話型コントローラアプリ: [tools/mobile_ble_controller_app.py](tools/mobile_ble_controller_app.py)

## 今回含めたもの

- JP 仕様書の初版
- ハード設計メモ
- ソフト設計メモ
- 実装計画
- 中央ノードと照明ノードの最小 ESP-IDF アプリ骨組み
- JP/EN Markdown 生成スクリプト

## 現在の進め方

- 最初は中央ノード 1 台と LED ノード 1 台の MVP 試作を行う。
- 目的は完成度よりも、中央ノード性能、LED ノードの SDMMC と WS2812 並列出力、UART 連携の成立性を見極めること。
- 中央ノードの ESP32-S3 が能力不足なら、中央ノードだけ上位 MCU へ切り替える。
- 初回 MVP では多ノード Wi-Fi 同期や AudioLINKCORE 本統合は後段に回す。

## 次の作業候補

1. Wi-Fi 通信プロトコルの具体化
2. 中央ノードの入力切替実装
3. 照明ノードのエフェクト描画実装
4. AudioLINKCORE 受信仕様の確定
