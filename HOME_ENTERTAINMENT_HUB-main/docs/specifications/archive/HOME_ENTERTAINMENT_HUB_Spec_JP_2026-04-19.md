# HOME_ENTERTAINMENT_HUB 仕様書 初版

このファイルは 2026-04-19 時点の初期版スナップショットです。

参照元: docs/specifications/HOME_ENTERTAINMENT_HUB_Spec_JP.md

- 使用シーンはライブ空間化とヒーリング空間化の 2 本。
- 初期版の主音声入力はマイク。
- PC 再生時は AudioLINKCORE が解析済み制御信号を中央ノードへ送る。
- 照明側は分散した ESP32-S3 ノード構成。
- ノード間通信は通常の家庭内 Wi-Fi ネットワーク。
