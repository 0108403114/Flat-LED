# LED Node 自動テスト向け「演出コンテンツ制作」共有メモ（下書き）

> 目的：本メモは **自動テスト（動作/通信テスト）** を成立させるために、
> **PC / TouchDesigner（送信側）** と **LED Node（受信側）** の双方で
> 事前に準備すべき事項・コンテンツ設計ルールを、コンテンツデザイナーへ共有するための下書きです。
>
> 前提：LED Node は ESP32-S3 + FastLED、Wi‑Fi STA + UDPマルチキャスト（239.255.0.1:6454）で受信し、
> WS2812B を 2ブロック（GPIO12/13）合計 880px（88×10）で表示します。\
> ※本コードは最小動作版であり、今後完成度を上げていく前提です。citeturn1search1

---

## 1. システム全体像（誰が何を作るか）

### 1.1 送信側（PC / TouchDesigner）の役割
- テスト用の **演出シーケンス（コンテンツ）** をタイムライン/状態遷移として定義する。citeturn1search1
- UDPマルチキャストで以下のパケット種別を送信する（想定）：
  - `CTRL`：背景/テキスト/輝度/シーン/トランジション等の制御
  - `CONTENT`：カスタムテキスト、歌詞チャンク等の配信
  - `NAV`：誘導（点滅色/速度）
  - `HEARTBEAT`：生存監視（途絶でセーフティ表示へ）citeturn1search1
- 自動テストで重要な「再現性」を担保するため、
  - 送信周期（fps / Hz）
  - シーン遷移のタイミング
  - シーケンス番号（重複排除）
  - 予約実行（execute_at_ms 等）の扱い
  を設計する。citeturn1search1

### 1.2 受信側（LED Node）の役割
- UDP（＋必要に応じて BLE）受信 → パケットをデコード → 表示状態へ反映する。citeturn1search1
- 88×10 マトリクス（サーペンタイン）へ描画する座標系を提供する。citeturn1search1
- ハートビート途絶時は **安全表示（白 8% + 4隅ステータスRGBW）** を表示する。citeturn1search1
- 背景（BG）アニメ、テキストレイヤ、NAV点滅、フェード遷移などを実装していく。citeturn1search1

---

## 2. 表示仕様（コンテンツ側が知っておくべきこと）

### 2.1 LED マトリクス仕様
- 画面：**88列 × 10行（計 880px）** citeturn1search1
- ブロック分割：
  - 上 5行（y=0..4）→ Block1（GPIO12, 440px）
  - 下 5行（y=5..9）→ Block2（GPIO13, 440px）citeturn1search1
- 配線：サーペンタイン（偶数行/奇数行で x 方向が反転）citeturn1search1
- LED：WS2812B / GRB オーダー citeturn1search1

### 2.2 レイヤ構成（想定）
- **背景（BG）**：アニメーション（例：FIRE / OCEAN / STARFIELD / OFF / ローカル花火）citeturn1search1
- **テキスト（TEXT）**：5×8 ASCII フォントで描画（歌詞/カスタム）citeturn1search1
- **NAV（誘導）**：点滅色・点滅速度（0=常灯, 1=低速, 2=高速）citeturn1search1
- **ステータス（4隅RGBW）**：通信断などの識別表示に使用citeturn1search1

> NOTE：現段階の最小動作版では、各レイヤの描画/合成は未完成・順次実装予定。

---

## 3. 通信（プロトコル前提）— コンテンツ制作に必要な観点

### 3.1 ネットワーク
- Wi‑Fi：STA モードで AP に接続 citeturn1search1
- UDP：マルチキャスト **239.255.0.1:6454** に参加して受信 citeturn1search1

### 3.2 パケット種別（コンテンツが触れる領域）
> 実際のフィールド定義は `hub_protocol.h`（Ver 3.0）に準拠する。citeturn1search1

- **CTRL（制御）**：
  - 目的：背景/テキスト/輝度/遷移/シーンプリセット等を一括制御
  - 重要：
    - `dimmer`（輝度）→ FastLED brightness に反映 citeturn1search1
    - `scene_id` 指定時は、ノード側で BG/TEXT/輝度/遷移時間を上書きする（プリセット）citeturn1search1
    - `trans_ms`（遷移時間）>0 の場合、BG切替でフェード遷移を行う想定（safe mode 外）citeturn1search1
    - `seq_num`：冗長送信の重複排除用（ノード側で保持）citeturn1search1
    - `FLAG_FORCE_RESET`：受信したら即再起動（テストでは扱い注意）citeturn1search1

- **CONTENT（内容配信）**：
  - 目的：カスタムテキストや歌詞（lyrics）など、表示コンテンツ本体を配信
  - 歌詞：チャンク分割で再構成し、全チャンク揃ったら1行として表示開始時刻を更新する想定citeturn1search1

- **NAV（誘導）**：
  - 目的：出口誘導等のための点滅表示（色/速度）citeturn1search1

- **HEARTBEAT（生存監視）**：
  - 目的：通信断を検出し、一定時間でセーフティ表示へ移行する。citeturn1search1

---

## 4. シーン（プリセット）一覧 — コンテンツ制作者向け

`scene_id` を使うと、ノード側で以下のように BG/TEXT/輝度/遷移が自動設定される想定。citeturn1search1

- `LIVE`：BG=FIRE, TEXT=LYRICS, dimmer=255, trans=255ms citeturn1search1
- `HEALING`：BG=OCEAN, TEXT=OFF, dimmer=140, trans=1000ms citeturn1search1
- `ENTRY`：BG=STARFIELD, TEXT=OFF, dimmer=180, trans=800ms citeturn1search1
- `OFF`：BG=OFF, TEXT=OFF, dimmer=0, trans=500ms citeturn1search1
- `READY`：BG=OCEAN, TEXT=CUSTOM（"Welcome <nickname>"）, dimmer=120, trans=500ms citeturn1search1
- `EVENT_1`：BG=OCEAN, TEXT=CUSTOM（カウントダウン用想定）, dimmer=180, trans=500ms citeturn1search1
- `EVENT_2`：BG=FIRE, TEXT=LYRICS, dimmer=255, trans=1000ms citeturn1search1
- `EVENT_3`：BG=STARFIELD, TEXT=CUSTOM（Thanks用想定）, dimmer=200, trans=1000ms citeturn1search1
- `FIREWORKS`：BG=ローカル花火ID, TEXT=OFF, dimmer=255（輝度だけ強制適用も想定）citeturn1search1

> コンテンツ設計方針：
> - **自動テスト**では、まず `scene_id` ベースで「決まった見え」を作ると再現性が高い。
> - BG/TEXT を個別にいじる詳細制御は、ノード側実装が揃ってから段階的に増やす。

---

## 5. 自動テスト用コンテンツ：最低限揃えるべき「演出セット」

### 5.1 テスト観点（例）
1. **ネットワーク疎通**：Wi‑Fi接続→マルチキャスト参加→受信確認 citeturn1search1
2. **ハートビート監視**：heartbeat停止→セーフティ表示へ遷移 citeturn1search1
3. **CTRL反映**：dimmer / scene切替 / trans_ms による遷移確認 citeturn1search1
4. **CONTENT反映**：カスタムテキスト表示、歌詞チャンク再構成 citeturn1search1
5. **NAV反映**：色・点滅速度・ON/OFF citeturn1search1
6. **重複排除**：同一 `seq_num` の多重送信時に安定動作 citeturn1search1
7. **予約実行（将来）**：execute_at_ms による同期（複数ノード同時切替）

### 5.2 推奨「演出シーケンス」（例）
- **SEQ-A：起動・接続確認（30秒）**
  - HEARTBEAT 送信開始
  - CTRL: scene=READY（Welcome表示）
  - 期待：ノードが READY 表示

- **SEQ-B：シーン遷移（60秒）**
  - CTRL: scene=ENTRY → HEALING → LIVE（各10〜20秒）
  - 期待：BG/TEXT/輝度/遷移時間がシーン通りに変わる

- **SEQ-C：歌詞（60秒）**
  - CTRL: scene=LIVE
  - CONTENT: lyrics をチャンクで送信（1行を複数チャンク）
  - 期待：全チャンク揃った時点で1行として表示更新

- **SEQ-D：NAV（30秒）**
  - NAV: 色=青、blink=低速 → 高速 → 常灯
  - 期待：点滅速度が変化

- **SEQ-E：安全系（30秒）**
  - HEARTBEAT 停止（3秒以上）
  - 期待：セーフティ白 8% + 4隅RGBW（識別表示）

---

## 6. 送信側（PC / TouchDesigner）で準備するもの

### 6.1 実装物
- UDPマルチキャスト送信（239.255.0.1:6454）citeturn1search1
- hub_protocol.h Ver3.0 に準拠したパケット生成（CRC/サイズ含む）citeturn1search1
- 自動テスト用タイムライン（例：SEQ-A〜E）
- ログ出力：
  - 送信時刻
  - pkt種別
  - seq_num
  - ノード宛先（ゾーン/ノードID）

### 6.2 運用ルール（推奨）
- HEARTBEAT は一定周期で必ず送る（途絶テスト時のみ止める）citeturn1search1
- CTRL は「冗長送信」してもノードが重複排除できるよう seq_num を設計するciteturn1search1
- シーン遷移は trans_ms を明示し、視認で差分が分かる値を使うciteturn1search1

---

## 7. 受信側（LED Node）で準備するもの

### 7.1 実装（最小動作 → 段階的に強化）
- Wi‑Fi接続（STA）＋マルチキャスト参加 citeturn1search1
- UDP受信ループ → dispatch → handle_xxx の骨格整備 citeturn1search1
- HEARTBEAT 監視 → セーフティ表示 citeturn1search1
- CTRL（dimmer/scene/bg/text/trans/flags/seq）適用 citeturn1search1
- BG（FIRE/OCEAN/STARFIELD/OFF/花火）の最低限描画（まずは静止画でもOK）citeturn1search1
- TEXT（CUSTOM/LYRICS）の最低限描画（5×8 ASCII）citeturn1search1
- NAV 点滅（色/速度）citeturn1search1

### 7.2 テスト観点での「見える化」
- 4隅RGBWを状態表示に活用（通信断やモード識別）citeturn1search1
- シリアルログを標準化
  - 受信 src（UDP/BLE）
  - pkt種別
  - decode成功/失敗（CRC/size）
  - seq重複drop
  - scene適用内容

---

## 8. コンテンツデザイナー向け：制作ガイドライン

### 8.1 画面特性
- 高さ10pxしかないため、
  - 情報は **短い単語/アイコン的表現**
  - カウントダウンや矢印、点滅など **動きで伝える**
  が有効。

### 8.2 テキスト
- 5×8 ASCII フォント前提（現状はUTF-8は '?' 代替想定）citeturn1search1
- 表示文字数は横幅88pxに依存（例：1文字=5px+間隔で概ね6px換算）
  - 目安：**約14文字**で1画面に収めやすい（スクロール併用は別）

### 8.3 カラーパレット
- WS2812B（GRB）前提なので、
  - 赤/緑/青/白の判別が容易な配色
  - 低輝度でも視認できる配色
  を基本とする。citeturn1search1

---

## 9. 未確定事項（資料化の前に埋めたい項目）

> ここは赤阪さん側で仕様を確定したら、デザイナー資料に反映

- hub_protocol.h の確定版フィールド一覧（CTRL/CONTENT/NAV/HEARTBEAT）
- 宛先指定の仕様（全体/ゾーン/ノード/グループ等）
- HEARTBEAT 周期（推奨値）とタイムアウト判定
- seq_num の運用（増分ルール、wrap時の扱い）
- lyrics の文字コード方針（ASCIIのみ/UTF-8対応/日本語対応）
- BGアセットのID割り当て（FIRE/OCEAN/STARFIELD/…）
- テキストのスクロール仕様（速度、方向、ループ/一回）

---

## 10. 付録：この下書きが参照している実装メモ

- ESP32-S3-Zero / WS2812B 2ブロック（GPIO12/13）/ 88×10マトリクス / UDPマルチキャスト 239.255.0.1:6454 / ハートビート断でセーフティ表示 / sceneプリセット / 歌詞チャンク再構成、など。citeturn1search1
