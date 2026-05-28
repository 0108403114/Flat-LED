# ACKアーキテクチャ評価メモ（2026-05-17）

対象資料:
- docs/Information/HEH_ACK_Architecture_Pack/docs/05_ack_architecture_spec_ja.md
- docs/Information/HEH_ACK_Architecture_Pack/include/hub_protocol.h
- docs/Information/HEH_ACK_Architecture_Pack/src/main_sample.cpp

## 総評

提案の方向性は妥当。
特に「HOME（少数）と STADIUM（大規模）で ACK を動的制御する」思想は、現行の設計思想と整合し、採用価値が高い。

## 最終決定（本日確定）

1. 現行リリース方針
- UART: ACK あり（維持）
- Wi-Fi: ACK なし（デフォルト維持）

2. HOME拡張方針
- HOME 少数ノード運用に限り、`SAT_V3_FLAG_ACK_REQ`（bit2）による動的ACKを許可する。
- ただし「検証用プロファイル」扱いで段階導入し、標準運用には即時適用しない。

3. STADIUM方針（固定）
- ACK は無効固定。
- 冗長送信 + HEARTBEAT + セーフモードで信頼性を担保する。

4. 互換性方針（固定）
- flags の割当は現行を維持する（bit0=PTP_VALID, bit1=UNICAST, bit2=ACK_REQ, bit3=REDUNDANT）。
- ACK_REQ を bit0 に再配置する案は採用しない。

5. ACK応答パケット（0x50）
- 将来拡張として保留。
- 導入時は既存 CRC-8/MAXIM と固定長仕様に合わせる。

## 良い点（採用）

1. 運用モードで ACK 方針を分ける設計
- HOME: 可観測性重視
- STADIUM: 帯域保護重視

2. ACK 依存を避ける大規模運用思想
- STADIUM で ACK なし
- 冗長送信 + HEARTBEAT + セーフモードで信頼性担保

3. プロトコルフォークを避ける意図
- 共通フレーム構造を保ち、運用フラグで切り替える思想は保守性が高い

## 注意点（修正または保留）

1. フラグビット割当の衝突
- 提案書: bit0=ACK_REQ, bit1=REDUNDANT
- 現行実装: bit0=PTP_VALID, bit1=UNICAST, bit2=ACK_REQ, bit3=REDUNDANT
- 判断: 既存互換性維持のため、現行割当を維持する

2. ACKパケット仕様の整合不足
- 提案サンプルの ACK CRC と既存 CRC 実装（MAXIM系）の整合が未確定
- 判断: ACK pkt_type 0x50 は将来拡張として段階導入

3. サンプル実装の移植前提
- `main_sample.cpp` は配置オフセットやネットワーク初期化が参考実装レベル
- 判断: そのまま本番採用せず、既存受信ループに差分移植する

## 本プロジェクトへの反映方針

1. UART
- ACK 使用を維持（Day0/Day1 の実機検証含む）

2. Wi-Fi
- デフォルト: ACK なし（現行）
- 将来: HOME運用に限定した ACK_REQ 有効化を追加
- STADIUM: ACK 無効固定

3. 文書反映
- docs/software/communication_protocol.md に ACKアーキテクチャ方針を追記済み

## 次アクション

1. ACK返信パケット（0x50）を暫定仕様化する場合は、既存 CRC ルールに合わせて定義
2. HOMEプロファイル用に ACK 集計のタイムアウト閾値を設計
3. STADIUMプロファイルで ACK 経路をビルド時または設定で強制無効化
