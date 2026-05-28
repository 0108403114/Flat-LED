# NotebookLM投入用ドキュメントセット

最終更新: 2026-05-09

このフォルダは、NotebookLM に投入しやすいように、現時点の構想・実装状況・計画を整理した資料セットです。
既存の設計メモや途中経過資料をそのまま渡すのではなく、2026-05-09 時点の最新判断を反映した要約版を格納しています。

## 推奨投入順

1. 01_project_overview.md
2. 02_tasklist_and_implementation_plan.md
3. 03_hardware_spec_concept.md
4. 04_communication_protocol_spec.md

## 参照用コード原本

- 05_satellite_node_main.cpp: 現在の実機で動作しているサテライトノードの主ファームウェア
- 06_hub_protocol.h: 現行の共通プロトコル定義ヘッダ

## 各資料の役割

- 01_project_overview.md: プロジェクト全体像、目的、現状、実機検証済み範囲
- 02_tasklist_and_implementation_plan.md: フェーズ別タスク、完了状況、次フェーズ
- 03_hardware_spec_concept.md: ハード構成、採用部品方針、電源・LED・配線前提
- 04_communication_protocol_spec.md: 通信の設計思想、現行実装、未実装領域
- 05_satellite_node_main.cpp: 現行ファームウェアの実装本体
- 06_hub_protocol.h: ファームウェアとツールが共有するプロトコル定義

## 取り扱い方針

- NotebookLM にはこのフォルダ内の 4 資料を優先投入してください。
- より詳細な原本が必要な場合のみ、docs 配下の既存資料を追加参照してください。
- このセットは構想と実装済み範囲を混在させていますが、各資料内で「実装済み」と「構想」を分けて記載しています。