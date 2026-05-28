# ソフトウェア設計

> **最終更新**: 2026-05-10（運用ルール更新）｜**参照時点**: 2026-05-10  
> GPIO 割り当て・UARTパケット仕様の詳細は [実装計画](../planning/implementation_plan.md) を優先参照してください。

## 中央ノードの責務

- Input Manager: マイク入力と外部制御入力の切替
- Audio Analyzer: 音特徴量抽出
- External Control Receiver: AudioLINKCORE からの入力受信
- Scene Engine: シーンごとの演出パラメータ生成
- Local UART Dispatcher: ローカル LED ノードへ UART でコマンド配信
- Wi-Fi Dispatcher: サテライト LED ノードへ Wi-Fi でコマンド配信
- Node Registry: ノード管理
- Config Store: 設定保存
- Asset Catalog: 利用可能なアセット ID と再生条件の管理
- Local UI: 表示とボタン処理

## LED ノードの責務

- UART Receiver または Network Receiver: 中央ノードからのコマンド受信
- Command Parser: 受信データ解釈
- Asset Loader: microSD 上のローカル演出データ読み込み
- Frame Composer: アセットと受信コマンドを合成して最終フレームを生成
- Effect Renderer: 色と明るさの更新
- LED Driver: FastLED 等を用いた実 LED 制御
- Safety Monitor: 通信断や異常時の安全動作
- Status Reporter: 状態通知

## コマンド種別

- Sync Preset: アニメーション、エフェクト、パレット、明るさ、テンポを同期する。
- Text Update: テキスト情報を更新する。
- Force Reset: LED ノード側の再生状態をリセットし、必要なら再起動またはブラックアウトへ遷移する。

## 配信対象

- ローカル LED ノード: 中央ノードから UART 接続
- サテライト LED ノード: 中央ノードから Wi-Fi 接続
- 論理コマンドは同じで、物理トランスポートだけを分ける。

## Communication Protocol (Ver 3.0)

- Port: UDP 6454 (Art-Net 準拠)
- Signature: [0] 0x53 (Shin's Signature)
- Packet Type: [1]
	- 0x10: CTRL (Scene / BG / Text / Dimmer / Transition / Schedule)
	- 0x20: CONTENT (Lyrics / Ticket / Announce などの動的テキスト)
	- 0x30: NAV (誘導表示)
	- 0x40: HEARTBEAT (生存確認)
- Version: [2] 0x03
- Targeting: [3-5] Node ID 3 bytes (Zone 1 byte + Node 2 bytes)
	- 0x000000 = Global

- CTRL Packet Map (25 bytes):
	- [6] Dimmer
	- [7] BG Asset ID
	- [8-9] BG In/Out Effect ID
	- [10] Text Mode ID
	- [11-12] Text In/Out Effect ID
	- [13-14] Transition Time (16-bit ms)
	- [15-18] execute_at_ms (32-bit, ms, 0=即時)
	- [19] Flags (PTP_VALID / REDUNDANT / FORCE_RESET など)
	- [20] Scene ID
	- [23] seq_num
	- [24] crc8 (CRC-8/MAXIM)

- CONTENT Packet Map (60 bytes):
	- [6] content_type (lyrics など)
	- [7] slot
	- [8-9] duration_ms
	- [10] text_len
	- [11-58] text[48]
	- [59] crc8

- HEARTBEAT Packet Map (8 bytes):
	- [0] signature
	- [1] 0x40
	- [2] version
	- [7] crc8

### MVP 運用ルール (追加フィールドなし)

- LYRICS 横スクロール方向:
	- `version` が奇数のとき左スクロール
	- `version` が偶数のとき右スクロール
	- 短文（例 5文字以下）でもスクロール対象になる場合あり（演出要件による）
- LYRICS フェードイン:
	- CTRL の `text_in_fx=FADE` を受けたノードは、歌詞文字の輝度を時間でランプアップする
	- フェード立ち上がり時間は実装側で固定（現行 1500ms 程度）
- 背景減光 (テキスト強調):
	- CTRL の `bg_out_fx=FADE` を受けたノードは、背景レイヤーのみ減光する
	- テキスト輝度とは独立して制御する
	- LYRICS フォーカス時に `bg_out_fx=FADE` が指定された場合、背景遷移フェードは停止し輝度を安定させる
- CUSTOM フェード表示:
	- CTRL の `text_mode=CUSTOM` かつ `text_in_fx=FADE` / `text_out_fx=FADE` を受けたノードは、CUSTOM テキストに対してフェードイン/アウトを適用する
	- フェード時間（イン/ホールド/アウト）は実装側で固定（現行 900/1200/900ms 程度）
- Node別 CUSTOM 表示の運用注意:
	- Node 別メッセージを送る直前に、対象 Node へ `text_mode=CUSTOM` の CTRL を先行送信する
	- その後に CONTENT(CUSTOM) を送信して表示欠落を防止する

### テキストスクロール制御（LYRICS）

- スクロール方向:
	- CONTENT パケットの `version` フィールドで指定（プロトコル側では区別しない）
	- `version` 奇数 = 左スクロール、偶数 = 右スクロール
- スクロール速度:
	- 実装側で固定（現行約 18px/frame 相当）
	- プロトコルに速度パラメータはなし（将来拡張で追加予定）
- 1 回スクロール vs ループ:
	- 現行実装では CONTENT 受信時にスクロール開始、ショー演出上は 1 回スクロールを前提
	- ループ再生は背景が切り替わるまでの間、自動的に繰り返される
- 短文強制スクロール:
	- 5文字以下の短文であっても、演出上必要な場合はスクロール表示させることがある
	- 仕様側では区別せず、実装で対応（画面幅フィルタなし）

### 背景交互表示・エフェクト制御

- エフェクト指定方法:
	- CTRL の `bg_in_fx` / `bg_out_fx` で背景の遷移エフェクトを指定
	- `CUT` (0x00) = 即座に切り替え、`FADE` (0x01) = フェード遷移
- 背景交互表示の実装パターン:
	- PC/TD から短時間間隔（推奨 120ms）で複数の CTRL をノードに送信
	- 例: `bg=ASSET_A` → `bg=ASSET_B` → `bg=ASSET_A` ...
	- `trans_ms` が小さい（≤200ms）場合はビジュアル上高速に切り替わる
- 遷移時間の効果:
	- `trans_ms` (16bit ms) が大きい場合、フェード期間中は背景が徐々に変わる
	- LYRICS フォーカス中（`bg_out_fx=FADE`）の場合、フェード遷移が停止する
- ノード同期性:
	- 複数ノードに同一背景コマンドを送る場合、全ノードが近い時刻に遷移する
	- 厳密な同期は保証されないため、視覚的に見える "ズレ" は許容する設計

## 役割分担と保持データ整理 (Node / PC・TouchDesigner)

この章は、Node 側と PC・TouchDesigner 側で何を保持し、どこで計算するかを固定するための運用基準である。

### 1. Node1/Node2 が保持すべき情報

- 固定プロフィール
	- zone, node, nickname, seat, pair_id, partner_node など
	- 目的: 起動時表示、個別演出、ペア演出のベース情報
- 通信状態
	- last_heartbeat_ms, safe_mode, last_seq_num
	- 目的: 通信断時の安全遷移、重複パケット排除
- 現在表示状態
	- current_bg_asset, current_text_mode, current_brightness, current_scene
	- 目的: 最新状態を単純に再現可能にする
- 演出内部状態 (ローカル計算用)
	- 背景アニメ状態 (例: 花火バースト配列、炎熱バッファ、星の瞬き状態)
	- テキスト演出状態 (例: 5秒カウントのローカル自走タイマ)
	- 目的: フレームごとの連続性をネットワーク遅延に依存させない
- 歌詞再構成バッファ
	- song_id, version, total_chunks, chunk受信状態、current_line
	- 目的: 分割配信の欠落耐性と差分更新

### 2. Node1/Node2 で行う計算処理

- パケット検証と適用判定
	- CRC 検証
	- 宛先判定 (Global または自身)
	- seq_num による重複排除
	- execute_at_ms の予約適用
- フレーム合成
	- 背景アニメ更新
	- フェード等の遷移補間
	- テキストオーバーレイ
	- 最終的に FastLED 出力
- セーフティ制御
	- HEARTBEAT タイムアウト監視
	- タイムアウト時は safe 表示へ遷移
- ローカル自走演出
	- 5→0 カウントダウンの秒進行をノード内タイマで進める
	- 目的: Node 間の 1 秒ズレ低減

### 3. PC / TouchDesigner 側が保持すべき情報

- ショー制御データ
	- シーンタイムライン
	- 各時点で送る CTRL / CONTENT / HEARTBEAT のイベント列
- ノード管理データ
	- 論理ターゲット (Global / Zone / Node)
	- 必要に応じてノード別オーバーライド文言
- 歌詞マスター
	- song_id, version, 行テキスト
	- チャンク分割前の原本
- 送信運用状態
	- heartbeat 送信周期
	- 最終送信時刻、送信ログ、再送方針

### 4. PC / TouchDesigner 側で行う計算処理

- タイムライン計算
	- 現在時刻に対応するイベント抽出
	- 送信順序決定 (CTRL と CONTENT を分離)
- プロトコルエンコード
	- Node ID 3 byte 生成
	- 各パケット生成 (CTRL 25 bytes, CONTENT 60 bytes, HEARTBEAT 8 bytes)
	- CRC-8/MAXIM 付与
- 歌詞チャンク化
	- Sxxxx|Vyy|Cii/tt|text フォーマット化
	- 48 byte 制限内へ分割
- 可観測性
	- 送信ログ出力
	- 重要コマンド再送 (必要時)

### 5. 通信プロトコル境界 (責務の切り分け)

- PC / TouchDesigner が責任を持つ領域
	- いつ、誰に、何を送るか (イベントスケジューリング)
	- パケットの正しい構築と送信
- Node が責任を持つ領域
	- 受信後の妥当性判定
	- 状態適用とフレーム生成
	- 通信断時の安全動作
- 共通契約
	- 送信は CTRL と CONTENT を混在させない
	- HEARTBEAT は 3 秒以内に再送されること
	- 重要イベントは短間隔で複数回送信して取りこぼしを低減

### 6. 実装マッピング (現行コード)

- Node 側
	- [firmware/satellite_node/src/main.cpp](firmware/satellite_node/src/main.cpp)
	- 受信、適用、背景描画、テキスト合成、セーフティ監視を担当
	- テキストスクロール実装: `draw_text_layer()` 関数（方向、速度、1 回制御）
	- 背景エフェクト実装: フェード制御（`gFadeActive` フラグ）、LYRICS フォーカス時フェード抑止
- PC / TouchDesigner 側
	- [tools/td_sat_sender.py](tools/td_sat_sender.py)
	- パケット生成、送信 API、歌詞分割、送信ログを担当
	- CTRL 送信時に bg_in_fx / bg_out_fx / text_in_fx / text_out_fx を指定可能
	- 背景交互表示用の複数 CTRL 送信（120ms 間隔推奨）を実装
- テスト送信シナリオ
	- [tools/test_start_sequence.py](tools/test_start_sequence.py)
	- S08/S09: ノード別交互表示 + 片側歌詞
	- S11: 歌詞フェードイン（text_in_fx=FADE）+ 背景フェード抑止
	- S14: Node 別 CUSTOM メッセージのフェードイン/アウト
- プロトコル定義
	- [shared/include/hub_protocol.h](shared/include/hub_protocol.h)
	- 定数、サイズ、CRC 方式、UART/UDP 仕様を定義

### 実装状況 (2026-05-10)

- 実装済み (送受信): CTRL / CONTENT / HEARTBEAT
- 実装済み (受信側): NAV
- 実装済み (テキスト制御):
	- LYRICS 横スクロール（方向は version で自動選択）
	- 短文強制スクロール、1 回スクロール
	- LYRICS フェードイン（text_in_fx=FADE）
	- CUSTOM フェード表示（text_in_fx/text_out_fx で in/out）
- 実装済み (背景エフェクト):
	- 背景交互表示（短時間間隔の複数 CTRL 送信）
	- 背景フェード遷移（bg_in_fx/bg_out_fx）
	- LYRICS フォーカス時に背景遷移フェード抑止（gFadeActive 制御）
- 送信側の現状:
	- TD 側 (td_sat_sender) は CTRL / CONTENT / HEARTBEAT を生成・送信
	- テキストモード（LYRICS/CUSTOM）と FX フィールドを指定可能
	- NAV の TD 送信 API は未実装

### MVP スコープ再定義 (2026-05-09)

- MVP では READY と LIVE に専念する。
- NAV モードは位置情報把握、QR 読取、会場導線制御など別機能との結合が必要なため、MVP 対象外とする。
- HOME モードは Home ENTERTAINMENT Hub 本体側の機能として別スコープで扱う。

#### READY モード

- チェックイン完了後の待機状態
- 省電力寄りの表示
- Welcome メッセージや案内テキストの表示
- 主に CONTENT + CTRL + HEARTBEAT を使用

#### LIVE モード

- カウントダウン表示
- 背景アセット切替
- シーン / 輝度 / 遷移 / エフェクト制御
- 歌詞やテキストのリアルタイム表示
- ノード側で背景とテキストを合成して最終表示
- 主に CTRL + CONTENT + HEARTBEAT を併用

#### MVP 対象外

- NAV-IN / NAV-OUT
- QR コード読取連携
- 位置情報・導線制御
- HOME モード (LIVE / HEALING / LIGHTING の家庭利用)

### パケット利用方針 (MVP)

- READY:
	- CTRL: 背景、輝度、省電力向けシーン指定
	- CONTENT: Welcome や案内テキスト
	- HEARTBEAT: 生存維持
- LIVE:
	- CTRL: 背景、シーン、輝度、遷移、予約実行
	- CONTENT: 歌詞、カウントダウン、メッセージ
	- HEARTBEAT: 生存維持
- CTRL と CONTENT は同一パケットに混在させず、用途ごとに個別送信する。
- 実運用では HEARTBEAT を定期送信しつつ、必要な時点で CTRL / CONTENT を追加送信する。

### プロトコル拡張予約 (将来版向け)

現在の CTRL パケット (25 bytes) は満杯に近い設計となっています。将来のテキストスクロール速度指定、背景交互表示パターン指定などに対応する場合は、以下の選択肢を検討してください：

- **案 1**: CTRL パケットを 32 bytes に拡張（下位互換性を維持しつつ追加フィールド確保）
- **案 2**: 新しいパケットタイプ（0x50: ADVANCED_CTRL など）を追加して拡張機能を分離
- **案 3**: 既存の `reserved` フィールドを使い切り、その後の案を適用

現段階では、実装側で固定値を使うことで対応し、運用ルール明記で柔軟性を確保しています。

## ノード識別と優先順位

- サテライト LED ノードは短い数値 ID を持つ。
- 初期版の目安は 1 から 16。
- ノードの表示名は中央ノード側の別名テーブルで管理する。
- 全体一斉コマンドと個別ノード指定コマンドを扱う。
- 個別ノード指定コマンドは、保持時間中は全体一斉コマンドより優先する。
- 保持時間終了後は全体同期状態へ戻る。
- 初期版の標準保持時間は 3 秒とする。
- 将来のグループ制御に備えて group_id 領域を予約する。
- group_id の 0 は全体扱いとして使う。

## モード

- Microphone Mode: 中央ノードが音を解析して演出を生成
- AudioLINKCORE Mode: 外部制御信号をそのまま演出入力として利用
- Manual Preset Mode: 手動プリセット再生

## ストレージ方針

- 大容量のイルミネーションデータは照明ノード側の microSD に保存する。
- 中央ノードは再生するアニメーションプリセット番号、エフェクトプリセット番号、カラーパレット番号、テキスト情報、再生位置、テンポ、色変調パラメータを配信する。
- 初期版ではアニメーションプリセット番号を asset ID と 1 対 1 で対応させる。
- 照明ノードは受信したアセット ID を基に、ローカル microSD から必要データを読み込んで再生する。
- Wi-Fi では大容量のフレームデータ本体を常時配信せず、トリガ、同期情報、可変パラメータだけを送る。
- Wi-Fi は重要コマンドのみ短時間の複数回送信で取りこぼしを下げる。
- サテライトノードは ESP32 と microSD を基本セットにした共通構成を目指す。
- ただし SDMMC を使う場合は XIAO ESP32S3 Plus の GPIO 余裕を必ず検証し、必要ならノード専用にピン数の多い ESP32-S3 へ切り替える。
- テキスト表示可否はノードごとの設定値で制御する。
- 初期状態ではローカル LED ノードだけテキスト表示を有効にする。
- カラーパレットはアニメーション全体の色替えとして適用する。
- エフェクトは加算や乗算などの簡易ブレンドでアニメーションへ重ねる。
- 各 LED ノードは ESP32-S3 上で最終フレームを合成してから WS2812 へ出力する。
- FastLED は出力層に限定して採用する。
- Force Reset 完了通知は初期版では UART ローカル LED ノードだけ返す。
- Wi-Fi の重要コマンドは 50 ms 間隔で 3 回送信する。
