# 作業申し送りメモ

## 最終更新: 2026-05-06

---

## Phase E 完了宣言

### 完了項目（実機確認済み）

#### E-1: ノード側基礎実装
| 項目 | 状態 |
|---|---|
| Wi-Fi STA 接続 | ✅ |
| UDP マルチキャスト受信ループ | ✅ |
| 署名 0x53 チェック | ✅ |
| Target ID / Global 振り分け | ✅ |
| BG Asset 再生（OFF / RAINBOW / PULSE / FIRE / OCEAN / STARFIELD） | ✅ |
| HEARTBEAT タイムアウトで safe mode 遷移 | ✅ |
| PKT_CONTENT 受信 | ✅ |
| PKT_NAV 受信（単色点灯 / 点滅 MVP） | ✅ |
| 歌詞チャンク受信仕様（song/chunk/version） | ✅ |
| 歌詞チャンク再構成・欠損検出 | ✅ |
| 歌詞チャンク差分更新（同 song_id / 新 version でテキスト持ち越し） | ✅ |
| Force Reset（PKT_CTRL bit4 → esp_restart） | ✅ |
| FastLED 電流制限（5V/2500mA） | ✅ |
| ループ WDT（8秒ハング時自動再起動） | ✅ |

#### E-2: 2台同時動作 MVP
| 項目 | 状態 |
|---|---|
| 2台同時発光 MVP | ✅ |
| TD Python から UDP 送出確認 | ✅ |
| .toe 保存 | ✅ |

---

## Phase E 残件（意図的に後送り）

| 残件 | 後送り理由 | 再着手タイミング |
|---|---|---|
| **Group ID 配信** | 2台では検証不可。設計コストに見合わない | ノード 10台以上になった時点 |
| **NAV 方向別 LED 演出** | LED の空間レイアウト（どの番号が「左」か）が未定義。送信側（TD）が色指定で代用可能 | Phase F で LED レイアウト設計時 |
| **テキスト描画（current_line の表示）** | F-2 スコープで明示済み | Phase F-2 |

---

## 実機情報（変更なし）

| ポート | MAC | Zone | Node |
|---|---|---|---|
| COM3 | a0:f2:62:f0:84:90 | 1 | 1 |
| COM4 | 3c:0f:02:e1:a8:20 | 1 | 2 |

---

## 主要ファイル（変更済み）

| ファイル | 変更内容 |
|---|---|
| `firmware/satellite_node/src/main.cpp` | 歌詞再構成・差分更新・Force Reset 実装 |
| `shared/include/hub_protocol.h` | `SAT_V3_FLAG_FORCE_RESET (1U << 4)` 追加 |
| `firmware/satellite_node/platformio.ini` | Node1/Node2 環境定義済み |
| `tools/led_udp_test_tool.py` | pair-scene / pair-content / pair-nav / keep-live / lyrics-chunk / lyrics-line / force-reset コマンド追加済み |

---

## 運用注意事項

- Global 送信は `--zone 0 --node 0`（`0x000000`）。`--zone 1 --node 0` は `0x010000` になりドロップされる。
- テストツールの作業ディレクトリが `firmware/satellite_node` のとき、`.venv` と `tools` の相対パスがズレる。プロジェクトルート (`C:\Projects\02_HomeLiveHall_Trial01`) で実行すること。

---

## Phase F: 完了報告

### F の目標

「演出として見えるレベル」まで BG アニメと LED 演出を強化する。
Wi-Fi 多ノード同期・AudioLINKCORE 統合は Phase G 以降。

### Phase F 完了項目（実機確認済み）

| # | タスク | 結果 |
|---|---|---|
| F-1 | **BG アニメ本実装** | FIRE / OCEAN / STARFIELD の実装と 2 台同時表示を確認 |
| F-2 | **歌詞テキスト描画** | 5x8 ASCII フォントによる `current_line` 表示を確認 |
| F-3 | **フェード遷移** | BG 切替時のクロスフェードを実機確認 |
| F-4 | **シーン定義** | LIVE / HEALING / ENTRY / OFF のシーン切替と相対遅延実行を確認 |
| F-5 | **長時間安定化** | 30 分連続動作試験を完走。safe mode 遷移なし、歌詞更新 30 回完了 |

### F-5 試験結果サマリ

- 実行コマンド: `.\.venv\Scripts\python.exe .\tools\endurance_lyrics_test.py --duration-min 30 --zone 1 --node-a 1 --node-b 2 --interval-ms 400`
- 結果: exit code 0
- 進捗ログ: `M01/30 STAB` から `M30/30 STAB` まで 1 分ごとの更新を欠落なく確認
- 終了処理: `[DONE] endurance test completed` / `[CLEANUP] sent OFF to both nodes`
- 判定: F-5 合格

### 次のフェーズ

- Phase G で AudioLINKCORE 統合と外部制御入力を進める
- Wi-Fi 再接続や RAM 推移の内部観測が必要な場合は別途シリアルログ試験を追加する

---

## Phase G: 進捗報告（2026-05-06 夜）

### G の目標

TouchDesigner から LED ノードをリアルタイム制御できるパイプラインを確立する。

### G 完了項目（本日）

| # | タスク | 結果 |
|---|---|---|
| G-1 | **UDP 送信モジュール** | `tools/td_sat_sender.py` 作成。TD 内で直接インポートし LIVE/HEALING/OFF を実機送信確認 |
| G-2 | **MCP 経由 LED 制御** | `tools/td_led_mcp_client.py` で init/scene/bg/dimmer/lyrics/hb-start コマンドを実装 |
| G-3 | **HB 自動送信スレッド** | `tools/td_hb_setup.py`。TD 内バックグラウンドスレッドで 1.5 秒周期 HEARTBEAT 送信。`op()` をスレッド内で使わないことでTDクラッシュを回避。 |
| G-4 | **TD パッチ UI 構築** | `tools/td_ui_builder.py` で `/project1/td_led_ui` を MCP API 経由で自動構築。LIVE/HEALING/ENTRY/OFF ボタン、DIMMER スライダー、歌詞入力フィールド、SEND/HB トグルボタン |
| G-5 | **TD Save Warning 修正** | Storage に pickle 不可オブジェクト（socket, Thread）を格納しないよう全スクリプトを修正。`td_sat_sender._global_ctrl` モジュールグローバルのみ使用 |
| G-6 | **不要ノード削除** | `tmp_nullCHOP`, `tmp_scriptDAT` を削除（診断用一時ノードによる赤エラーを解消） |
| G-7 | **TD ノードレイアウト整列** | `/project1`（4 ノード）、`/project1/mcp_webserver_base` 内（4 ノード）、`/project1/td_led_ui` 内（9 ノード）を論理グループ別に配置 |
| G-8 | **TD 再起動後の自動初期化** | `tools/td_ui_builder.py` の Execute DAT テンプレートに lazy bootstrap を追加。controller 未初期化時に `td_sat_sender.TdLedController()` を自動生成 |

### 重要な技術的知見

| 事象 | 原因 | 対策 |
|---|---|---|
| TD Save Warning | `op().store()` に socket/Thread を保存 → pickle 失敗 | Storage 使用禁止。`td_sat_sender._global_ctrl` のみ使用 |
| TD スレッド内 `op()` クラッシュ | TD の Operator API はメインスレッド専用 | スレッド内から `op()` を一切呼ばない |
| TD 再起動後の状態消失 | モジュールグローバルはTD再起動でリセットされる | Execute DAT の lazy bootstrap で自動初期化。失敗時のみ手動 init にフォールバック |

### Phase G 現在進捗

```
Phase G ███████░░░  70%
```

### Phase G 残タスク

| タスク | 優先度 |
|---|---|
| AudioLINKCORE 受信プロトコルの具体化 | 中 |
| 中央ノード実装の最小スケルトン着手（controller 側） | 中 |

### 次回作業時の復元手順

TD 再起動後は以下で状態確認してから制御開始すること：

```bash
# プロジェクトルートで実行
python tools/td_hb_setup.py               # HB スレッド起動
python tools/td_led_mcp_client.py status  # 確認（hb_thread: running）

# もし controller が NOT initialized の場合のみ
python tools/td_led_mcp_client.py init
```

### 主要ファイル（Phase G で追加）

| ファイル | 役割 |
|---|---|
| `tools/td_sat_sender.py` | TD 内 Python から UDP でノード制御するモジュール |
| `tools/td_led_mcp_client.py` | MCP 経由 LED 制御 CLI |
| `tools/td_hb_setup.py` | TD 内 HB バックグラウンドスレッド管理 |
| `tools/td_ui_builder.py` | TD パッチ UI 再構築スクリプト |
| `touchdesigner-mcp-td/my_project.toe` | TD プロジェクトファイル（保存済み）|
