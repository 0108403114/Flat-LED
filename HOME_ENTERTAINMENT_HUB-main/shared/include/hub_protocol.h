#ifndef HUB_PROTOCOL_H
#define HUB_PROTOCOL_H

#include <stdint.h>
#include <string.h>

#define HUB_MAX_NODES 16
#define HUB_MAGIC 0x48484231U
#define HUB_TEXT_MAX_LEN 32U

typedef enum {
    HUB_MODE_MIC = 0,
    HUB_MODE_EXTERNAL = 1,
    HUB_MODE_MANUAL = 2
} hub_mode_t;

typedef enum {
    HUB_SCENE_LIVE = 0,
    HUB_SCENE_HEALING = 1
} hub_scene_t;

typedef enum {
    HUB_CMD_SYNC_PRESET = 0,
    HUB_CMD_TEXT_UPDATE = 1,
    HUB_CMD_FORCE_RESET = 2
} hub_command_type_t;

typedef struct {
    uint32_t magic;
    uint8_t version;
    uint8_t command_type;
    uint8_t scene_id;
    uint8_t target_node_id;
    uint8_t target_flags;
    uint8_t group_id;
    uint8_t mode_id;
    uint16_t animation_preset_id;
    uint16_t effect_preset_id;
    uint16_t palette_preset_id;
    uint8_t energy;
    uint8_t brightness;
    uint8_t hue;
    uint8_t saturation;
    uint16_t hold_ms;
    uint16_t fade_ms;
    uint16_t tempo_bpm;
    uint8_t flags;
    uint8_t reserved;
} hub_effect_packet_t;

typedef struct {
    uint32_t magic;
    uint8_t version;
    uint8_t command_type;
    uint8_t scene_id;
    uint8_t target_node_id;
    uint8_t group_id;
    uint8_t text_length;
    char text[HUB_TEXT_MAX_LEN];
} hub_text_packet_t;

/* ==========================================================
 *  UDP Satellite Protocol (Ver 2.0)
 *  Port: 6454 (Art-Net 準拠)
 *
 *  Byte[ 0]: SAT_SIGNATURE (0x53)
 *  Byte[ 1]: Target Node ID (0=Global, 1=NodeA, 2=NodeB, ...)
 *  Byte[ 2]: CH1  Master Dimmer
 *  Byte[ 3]: CH2  BG Asset ID
 *  Byte[ 4]: CH3  BG In  Effect ID
 *  Byte[ 5]: CH4  BG Out Effect ID
 *  Byte[ 6]: CH5  (reserved)
 *  Byte[ 7]: CH6  (reserved)
 *  Byte[ 8]: CH7  Text Mode ID
 *  Byte[ 9]: CH8  Text In  Effect ID
 *  Byte[10]: CH9  Text Out Effect ID
 *  Byte[11]: CH10 (reserved)
 *  Byte[12]: CH11 (reserved)
 *  Byte[13]: CH12 Transition Time HIGH byte
 *  Byte[14]: CH13 Transition Time LOW byte
 * ========================================================== */

#define SAT_UDP_PORT        6454U
#define SAT_SIGNATURE       0x53U
#define SAT_NODE_ID_GLOBAL  0x00U
#define SAT_PKT_MIN_SIZE    15U

#define SAT_CH_OFFSET       2U   /* Byte[2] が CH1 */

/* CH インデックス (Byte オフセット) */
#define SAT_CH1_DIMMER          2U
#define SAT_CH2_BG_ASSET        3U
#define SAT_CH3_BG_IN_FX        4U
#define SAT_CH4_BG_OUT_FX       5U
#define SAT_CH7_TEXT_MODE       8U
#define SAT_CH8_TEXT_IN_FX      9U
#define SAT_CH9_TEXT_OUT_FX    10U
#define SAT_CH12_TRANS_HIGH    13U
#define SAT_CH13_TRANS_LOW     14U

/* BG Asset ID */
#define SAT_BG_OFF             0U
#define SAT_BG_RAINBOW         1U
#define SAT_BG_PULSE           2U

/* Text Mode ID */
#define SAT_TEXT_OFF           0U
#define SAT_TEXT_LYRICS        1U
#define SAT_TEXT_SEAT_INFO     2U

/* ==========================================================
 *  UART Protocol (MVP 最小仕様)
 *  対象: 中央ノード ↔ LED ノード
 *  Port: UART1 (GPIO17 TX, GPIO18 RX)
 *  
 *  フレーム形式:
 *  [STX 1B] [CMD 1B] [LEN 1B] [PAYLOAD 0〜32B] [CRC8 1B] [ETX 1B]
 * ========================================================== */

/* UART フレーム定義 */
#define HUB_UART_STX              0xAA
#define HUB_UART_ETX              0x55
#define HUB_UART_PAYLOAD_MAX      32
#define HUB_UART_FRAME_MAX_LEN    (1 + 1 + 1 + HUB_UART_PAYLOAD_MAX + 1 + 1)

/* コマンド ID */
typedef enum {
    HUB_UART_CMD_SET_BRIGHTNESS = 0x01,   /**< 全体輝度設定 (1B) */
    HUB_UART_CMD_SET_COLOR      = 0x02,   /**< 単色塗り (3B: R,G,B) */
    HUB_UART_CMD_SET_EFFECT     = 0x03,   /**< エフェクト種別 (1B) */
    HUB_UART_CMD_PLAY_ASSET     = 0x04,   /**< アセット再生 (2B: asset_id LE) */
    HUB_UART_CMD_STOP           = 0x05,   /**< 停止・全消灯 (0B) */
    HUB_UART_CMD_HEARTBEAT      = 0x10,   /**< 生存確認 (0B, 1秒周期) */
    HUB_UART_CMD_ACK            = 0x11,   /**< 受信確認応答 (1B: original_cmd) */
    HUB_UART_CMD_RESET          = 0xFF,   /**< 強制リセット (0B) */
} hub_uart_command_t;

/* UART フレーム構造体 */
typedef struct {
    uint8_t stx;                          /**< 開始バイト (0xAA) */
    uint8_t cmd;                          /**< コマンド ID */
    uint8_t len;                          /**< PAYLOAD 長 (0〜32) */
    uint8_t payload[HUB_UART_PAYLOAD_MAX];/**< ペイロード */
    uint8_t crc8;                         /**< CRC-8/MAXIM */
    uint8_t etx;                          /**< 終了バイト (0x55) */
} hub_uart_frame_t;

/* ========================================================== 
 * CRC-8/MAXIM 計算
 * ========================================================== */

/**
 * CRC-8/MAXIM (ポリノミアル 0x31) を計算
 */
static inline uint8_t hub_uart_crc8_maxim(const uint8_t *data, size_t len) {
    uint8_t crc = 0;
    for (size_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (int j = 0; j < 8; j++) {
            if (crc & 1) {
                crc = (crc >> 1) ^ 0x8C;  // MAXIM ポリノミアル反転
            } else {
                crc >>= 1;
            }
        }
    }
    return crc;
}

/**
 * フレーム内の CRC8 を計算 (STX〜PAYLOAD の範囲)
 */
static inline uint8_t hub_uart_frame_calc_crc8(const hub_uart_frame_t *frame) {
    uint8_t temp[HUB_UART_FRAME_MAX_LEN];
    size_t pos = 0;
    
    temp[pos++] = frame->stx;
    temp[pos++] = frame->cmd;
    temp[pos++] = frame->len;
    
    if (frame->len > 0 && frame->len <= HUB_UART_PAYLOAD_MAX) {
        memcpy(&temp[pos], frame->payload, frame->len);
        pos += frame->len;
    }
    
    return hub_uart_crc8_maxim(temp, pos);
}

/* ========================================================== 
 * エンコード・デコード関数
 * ========================================================== */

/**
 * フレームをバイト列にエンコード (シリアル送信用)
 * @return 書き込みバイト数、エラー時は -1
 */
static inline int hub_uart_frame_encode(const hub_uart_frame_t *frame, 
                                        uint8_t *buffer, size_t size) {
    int frame_len = 1 + 1 + 1 + frame->len + 1 + 1;
    
    if (frame->len > HUB_UART_PAYLOAD_MAX || size < (size_t)frame_len) {
        return -1;
    }
    
    hub_uart_frame_t temp = *frame;
    temp.crc8 = hub_uart_frame_calc_crc8(&temp);
    temp.etx = HUB_UART_ETX;
    
    int pos = 0;
    buffer[pos++] = temp.stx;
    buffer[pos++] = temp.cmd;
    buffer[pos++] = temp.len;
    memcpy(&buffer[pos], temp.payload, temp.len);
    pos += temp.len;
    buffer[pos++] = temp.crc8;
    buffer[pos++] = temp.etx;
    
    return pos;
}

/**
 * バイト列からフレームをデコード (シリアル受信用)
 * @return 成功時 1, CRC エラー時 -1, 不完全時 0
 */
static inline int hub_uart_frame_decode(const uint8_t *buffer, size_t size, 
                                        hub_uart_frame_t *frame) {
    if (size < 5) {
        return 0;  // 不完全
    }
    
    size_t pos = 0;
    
    if (buffer[pos] != HUB_UART_STX) {
        return -1;  // フレーミングエラー
    }
    frame->stx = buffer[pos++];
    
    frame->cmd = buffer[pos++];
    frame->len = buffer[pos++];
    
    if (frame->len > HUB_UART_PAYLOAD_MAX) {
        return -1;  // 不正な LEN
    }
    
    size_t expected_len = 1 + 1 + 1 + frame->len + 1 + 1;
    if (size < expected_len) {
        return 0;  // 不完全
    }
    
    memcpy(frame->payload, &buffer[pos], frame->len);
    pos += frame->len;
    
    frame->crc8 = buffer[pos++];
    frame->etx = buffer[pos++];
    
    if (frame->etx != HUB_UART_ETX) {
        return -1;  // フレーミングエラー
    }
    
    uint8_t expected_crc8 = hub_uart_frame_calc_crc8(frame);
    if (frame->crc8 != expected_crc8) {
        return -1;  // CRC エラー
    }
    
    return 1;  // 成功
}

/* ========================================================== 
 * ヘルパー関数 (フレーム生成)
 * ========================================================== */

static inline void hub_uart_frame_set_brightness(hub_uart_frame_t *frame, uint8_t brightness) {
    frame->stx = HUB_UART_STX;
    frame->cmd = HUB_UART_CMD_SET_BRIGHTNESS;
    frame->len = 1;
    frame->payload[0] = brightness;
}

static inline void hub_uart_frame_set_color(hub_uart_frame_t *frame, 
                                            uint8_t r, uint8_t g, uint8_t b) {
    frame->stx = HUB_UART_STX;
    frame->cmd = HUB_UART_CMD_SET_COLOR;
    frame->len = 3;
    frame->payload[0] = r;
    frame->payload[1] = g;
    frame->payload[2] = b;
}

static inline void hub_uart_frame_set_effect(hub_uart_frame_t *frame, uint8_t effect_id) {
    frame->stx = HUB_UART_STX;
    frame->cmd = HUB_UART_CMD_SET_EFFECT;
    frame->len = 1;
    frame->payload[0] = effect_id;
}

static inline void hub_uart_frame_play_asset(hub_uart_frame_t *frame, uint16_t asset_id) {
    frame->stx = HUB_UART_STX;
    frame->cmd = HUB_UART_CMD_PLAY_ASSET;
    frame->len = 2;
    frame->payload[0] = asset_id & 0xFF;        // LE
    frame->payload[1] = (asset_id >> 8) & 0xFF;
}

static inline void hub_uart_frame_stop(hub_uart_frame_t *frame) {
    frame->stx = HUB_UART_STX;
    frame->cmd = HUB_UART_CMD_STOP;
    frame->len = 0;
}

static inline void hub_uart_frame_heartbeat(hub_uart_frame_t *frame) {
    frame->stx = HUB_UART_STX;
    frame->cmd = HUB_UART_CMD_HEARTBEAT;
    frame->len = 0;
}

static inline void hub_uart_frame_ack(hub_uart_frame_t *frame, uint8_t original_cmd) {
    frame->stx = HUB_UART_STX;
    frame->cmd = HUB_UART_CMD_ACK;
    frame->len = 1;
    frame->payload[0] = original_cmd;
}

static inline void hub_uart_frame_reset(hub_uart_frame_t *frame) {
    frame->stx = HUB_UART_STX;
    frame->cmd = HUB_UART_CMD_RESET;
    frame->len = 0;
}

/* ==========================================================
 *  UDP Satellite Protocol Ver 3.0
 *  ===========================================================
 *  設計目標:
 *    - 家庭用 Wi-Fi での MVP から、国立競技場規模 (100,000 台) まで
 *      同一プロトコルでスケールアップできること。
 *    - 送信側は UDP マルチキャスト 1 パケットのみ。ノード数に依存しない。
 *    - 個別配信（チケット情報・個人メッセージ等）は UDP ユニキャストで同一
 *      フォーマットを使用。切替はネットワーク層で行う。
 *
 *  マルチキャストグループ : 239.255.0.1
 *  ポート                 : 6454  (Art-Net 準拠)
 *  ACK                    : なし  (帯域パンク防止。重要コマンドは 3 回冗長送)
 *
 *  【Ver 2.0 との互換性】
 *    Byte[0] = 0x53 (SAT_SIGNATURE) は共通。
 *    Byte[1] の上位 4 bit が 0x0 の場合は Ver 2.0 パケットとして扱う。
 *    Ver 3.0 パケットは Byte[1] = SAT_V3_PKT_TYPE_* (0x10〜0xFF) で区別。
 *
 *  【パケット種別】
 *    0x10  SAT_V3_PKT_CTRL      シーン・BG・Text 制御 (25 bytes)
 *    0x20  SAT_V3_PKT_CONTENT   動的テキスト配信      (60 bytes)
 *    0x30  SAT_V3_PKT_NAV       席ナビゲーション      (20 bytes)
 *    0x40  SAT_V3_PKT_HEARTBEAT 生存確認              ( 8 bytes)
 *
 *  【ノード ID 体系 (3 bytes = 最大 16,777,215 台)】
 *    0x000000  Global (全ノード一斉)
 *    0x000001〜  個別ノード ID
 *    上位 1 byte をゾーン ID、下位 2 byte をノード ID として運用推奨。
 *      例: 0x010001 = ゾーン1 ノード1
 *
 *  【Flags バイト】
 *    bit 0: PTP_VALID   — execute_at_ms フィールドが有効
 *    bit 1: UNICAST     — ユニキャスト送信フラグ (受信側は無視)
 *    bit 2: ACK_REQ     — HOME少数ノード運用でのみ受信確認を要求 (通常は未使用)
 *    bit 3: REDUNDANT   — 冗長送信パケット (重複処理抑制用)
 *    bit 4〜7: 予約
 * ========================================================== */

/* --- 共通定数 --- */
#define SAT_V3_SIGNATURE        0x53U
#define SAT_V3_UDP_PORT         6454U
#define SAT_V3_MCAST_GROUP      "239.255.0.1"
#define SAT_V3_NODE_GLOBAL      0x000000U   /**< 全ノード一斉 */

/* --- パケット種別 --- */
#define SAT_V3_PKT_CTRL         0x10U       /**< シーン制御 (25 bytes) */
#define SAT_V3_PKT_CONTENT      0x20U       /**< 動的テキスト配信 (60 bytes) */
#define SAT_V3_PKT_NAV          0x30U       /**< 席ナビゲーション (20 bytes) */
#define SAT_V3_PKT_HEARTBEAT    0x40U       /**< 生存確認 (8 bytes) */

/* --- Flags ビット --- */
#define SAT_V3_FLAG_PTP_VALID   (1U << 0)   /**< execute_at_ms が有効 */
#define SAT_V3_FLAG_UNICAST     (1U << 1)   /**< ユニキャスト送信 */
#define SAT_V3_FLAG_ACK_REQ     (1U << 2)   /**< 受信確認要求 (HOME拡張用) */
#define SAT_V3_FLAG_REDUNDANT   (1U << 3)   /**< 冗長送信パケット */
#define SAT_V3_FLAG_FORCE_RESET (1U << 4)   /**< 強制再起動 (esp_restart) */

/* --- BG Asset ID (Ver 2.0 から継続) --- */
#define SAT_V3_BG_OFF           0U
#define SAT_V3_BG_RAINBOW       1U
#define SAT_V3_BG_PULSE         2U
#define SAT_V3_BG_FIRE          3U
#define SAT_V3_BG_OCEAN         4U
#define SAT_V3_BG_STARFIELD     5U

/* --- Effect ID (BG In/Out, Text In/Out 共通) --- */
#define SAT_V3_FX_CUT           0U
#define SAT_V3_FX_FADE          1U
#define SAT_V3_FX_SLIDE_L       2U
#define SAT_V3_FX_SLIDE_R       3U
#define SAT_V3_FX_WIPE          4U
#define SAT_V3_FX_SPARKLE       5U

/* --- Text Mode ID --- */
#define SAT_V3_TEXT_OFF         0U
#define SAT_V3_TEXT_LYRICS      1U
#define SAT_V3_TEXT_SEAT_INFO   2U
#define SAT_V3_TEXT_WELCOME     3U
#define SAT_V3_TEXT_OSHI_MSG    4U          /**< 推しキャラ個別メッセージ */
#define SAT_V3_TEXT_CUSTOM      5U          /**< Content パケットで配信した任意テキスト */

/* --- Content Type (PKT_CONTENT 用) --- */
#define SAT_V3_CONTENT_TICKET   0x01U       /**< チケット・座席情報 */
#define SAT_V3_CONTENT_OSHI_MSG 0x02U       /**< 推しキャラからのメッセージ */
#define SAT_V3_CONTENT_WELCOME  0x03U       /**< ウェルカムメッセージ */
#define SAT_V3_CONTENT_ANNOUNCE 0x04U       /**< 主催者アナウンス */
#define SAT_V3_CONTENT_LYRICS   0x05U       /**< 歌詞チャンク（リアルタイム配信） */

/* --- Scene ID (PKT_CTRL の scene_id フィールド用) --- */
#define SAT_V3_SCENE_NONE       0U          /**< シーン指定なし (各フィールドをそのまま適用) */
#define SAT_V3_SCENE_LIVE       1U          /**< LIVE: FIRE BG + LYRICS + 全灯 */
#define SAT_V3_SCENE_HEALING    2U          /**< HEALING: OCEAN BG + 暗め */
#define SAT_V3_SCENE_ENTRY      3U          /**< ENTRY: STARFIELD + ウェルカム */
#define SAT_V3_SCENE_OFF        4U          /**< 全消灯 */
#define SAT_V3_SCENE_READY      5U          /**< READY: Welcome + 低消費電力 (3分CD) */
#define SAT_V3_SCENE_EVENT_1    6U          /**< EVENT 背景1: OCEAN + CD表示 */
#define SAT_V3_SCENE_EVENT_2    7U          /**< EVENT 背景2: FIRE + 歌詞表示 */
#define SAT_V3_SCENE_EVENT_3    8U          /**< EVENT 背景3: STARFIELD + Thanks */
#define SAT_V3_SCENE_FIREWORKS  9U          /**< 花火: 0秒時演出 */

/* --- Nav Direction (PKT_NAV 用) --- */
#define SAT_V3_NAV_OFF          0x00U
#define SAT_V3_NAV_FORWARD      0x01U
#define SAT_V3_NAV_LEFT         0x02U
#define SAT_V3_NAV_RIGHT        0x03U
#define SAT_V3_NAV_ARRIVED      0x04U       /**< 目的地到着 (点滅演出) */

/* ==========================================================
 *  Ver 3.0 パケット構造体
 * ========================================================== */

/**
 * SAT_V3_PKT_CTRL: シーン制御パケット (25 bytes)
 *
 *  Byte[ 0]    : signature (0x53)
 *  Byte[ 1]    : pkt_type  (0x10)
 *  Byte[ 2]    : version   (0x03)
 *  Byte[ 3- 5] : node_id[3]  上位 1B=ゾーン, 下位 2B=ノード (0x000000=Global)
 *  Byte[ 6]    : dimmer      Master Dimmer (0〜255)
 *  Byte[ 7]    : bg_asset    BG Asset ID
 *  Byte[ 8]    : bg_in_fx    BG In  Effect ID
 *  Byte[ 9]    : bg_out_fx   BG Out Effect ID
 *  Byte[10]    : text_mode   Text Mode ID
 *  Byte[11]    : text_in_fx  Text In  Effect ID
 *  Byte[12]    : text_out_fx Text Out Effect ID
 *  Byte[13-14] : trans_ms    Transition Time (BE, 0〜65535 ms)
 *  Byte[15-18] : execute_at_ms  PTP スケジュール実行時刻 (BE, ms, 0=即時)
 *  Byte[19]    : flags
 *  Byte[20-22] : reserved (0x00)
 *  Byte[23]    : seq_num    冗長送信での重複排除用シーケンス番号
 *  Byte[24]    : crc8       Byte[0〜23] の CRC-8/MAXIM
 */
#define SAT_V3_CTRL_SIZE        25U

typedef struct {
    uint8_t  signature;         /**< 0x53 */
    uint8_t  pkt_type;          /**< SAT_V3_PKT_CTRL (0x10) */
    uint8_t  version;           /**< 0x03 */
    uint8_t  node_id[3];        /**< [0]=ゾーン, [1-2]=ノード ID (BE) */
    uint8_t  dimmer;
    uint8_t  bg_asset;
    uint8_t  bg_in_fx;
    uint8_t  bg_out_fx;
    uint8_t  text_mode;
    uint8_t  text_in_fx;
    uint8_t  text_out_fx;
    uint8_t  trans_ms_hi;       /**< Transition Time 上位バイト */
    uint8_t  trans_ms_lo;       /**< Transition Time 下位バイト */
    uint8_t  execute_at_ms[4];  /**< PTP 実行時刻 (BE, 0=即時) */
    uint8_t  flags;
    uint8_t  scene_id;          /**< SAT_V3_SCENE_* (0=指定なし, 非0=プリセット適用) */
    uint8_t  reserved[2];
    uint8_t  seq_num;
    uint8_t  crc8;
} sat_v3_ctrl_pkt_t;

/**
 * SAT_V3_PKT_CONTENT: 動的テキスト配信パケット (60 bytes)
 *
 *  チケット情報・個人メッセージ等を個別ノードへユニキャストで配信する。
 *  入場スキャン時や QR 読取後にサーバーから当該席ノードへ 1 回送る。
 *  ノードは受信後、content_type と slot に従いローカルで表示する。
 *
 *  Byte[ 0]    : signature     (0x53)
 *  Byte[ 1]    : pkt_type      (0x20)
 *  Byte[ 2]    : version       (0x03)
 *  Byte[ 3- 5] : node_id[3]
 *  Byte[ 6]    : content_type  SAT_V3_CONTENT_* 
 *  Byte[ 7]    : slot          表示スロット番号 (0〜7)
 *  Byte[ 8- 9] : duration_ms   表示継続時間 (BE, ms, 0=常時)
 *  Byte[10]    : text_len      テキスト長 (0〜48)
 *  Byte[11-58] : text[48]      UTF-8 テキスト (ヌル終端不要)
 *  Byte[59]    : crc8          Byte[0〜58] の CRC-8/MAXIM
 */
#define SAT_V3_CONTENT_SIZE         60U
#define SAT_V3_CONTENT_TEXT_MAX     48U

typedef struct {
    uint8_t  signature;
    uint8_t  pkt_type;          /**< SAT_V3_PKT_CONTENT (0x20) */
    uint8_t  version;           /**< 0x03 */
    uint8_t  node_id[3];
    uint8_t  content_type;      /**< SAT_V3_CONTENT_* */
    uint8_t  slot;              /**< 表示スロット (0〜7) */
    uint8_t  duration_ms_hi;
    uint8_t  duration_ms_lo;
    uint8_t  text_len;
    uint8_t  text[SAT_V3_CONTENT_TEXT_MAX];
    uint8_t  crc8;
} sat_v3_content_pkt_t;

/**
 * SAT_V3_PKT_NAV: 席ナビゲーションパケット (20 bytes)
 *
 *  入場時に光で通路を誘導する。全席一斉または個別席に送る。
 *  対象ノードは nav_direction に従い LED 演出を切替える。
 *
 *  Byte[ 0]    : signature     (0x53)
 *  Byte[ 1]    : pkt_type      (0x30)
 *  Byte[ 2]    : version       (0x03)
 *  Byte[ 3- 5] : node_id[3]
 *  Byte[ 6]    : nav_direction SAT_V3_NAV_*
 *  Byte[ 7]    : nav_color_r
 *  Byte[ 8]    : nav_color_g
 *  Byte[ 9]    : nav_color_b
 *  Byte[10]    : blink_rate    点滅速度 (0=常灯, 1=低速, 2=高速)
 *  Byte[11]    : intensity     輝度 (0〜255)
 *  Byte[12-18] : reserved
 *  Byte[19]    : crc8
 */
#define SAT_V3_NAV_SIZE     20U

typedef struct {
    uint8_t  signature;
    uint8_t  pkt_type;          /**< SAT_V3_PKT_NAV (0x30) */
    uint8_t  version;           /**< 0x03 */
    uint8_t  node_id[3];
    uint8_t  nav_direction;     /**< SAT_V3_NAV_* */
    uint8_t  nav_color_r;
    uint8_t  nav_color_g;
    uint8_t  nav_color_b;
    uint8_t  blink_rate;
    uint8_t  intensity;
    uint8_t  reserved[7];
    uint8_t  crc8;
} sat_v3_nav_pkt_t;

/**
 * SAT_V3_PKT_HEARTBEAT: 生存確認パケット (8 bytes)
 *
 *  中央ノードが 1 秒周期でマルチキャスト送信する。
 *  ノードが 3 秒以内に受信できなければセーフティ白 5% に遷移する。
 *
 *  Byte[0]    : signature (0x53)
 *  Byte[1]    : pkt_type  (0x40)
 *  Byte[2]    : version   (0x03)
 *  Byte[3-6]  : uptime_s  中央ノード起動秒数 (BE, 32-bit)
 *  Byte[7]    : crc8
 */
#define SAT_V3_HEARTBEAT_SIZE   8U

typedef struct {
    uint8_t  signature;
    uint8_t  pkt_type;          /**< SAT_V3_PKT_HEARTBEAT (0x40) */
    uint8_t  version;           /**< 0x03 */
    uint8_t  uptime_s[4];       /**< 中央ノード起動秒数 (BE) */
    uint8_t  crc8;
} sat_v3_heartbeat_pkt_t;

/* ==========================================================
 *  Ver 3.0 CRC-8/MAXIM ヘルパー
 * ========================================================== */

static inline uint8_t sat_v3_crc8(const uint8_t *data, size_t len) {
    uint8_t crc = 0;
    for (size_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (int j = 0; j < 8; j++) {
            crc = (crc & 1) ? ((crc >> 1) ^ 0x8C) : (crc >> 1);
        }
    }
    return crc;
}

/* ==========================================================
 *  Ver 3.0 ノード ID ヘルパー
 * ========================================================== */

/** ノード ID を 3 バイト配列に書き込む */
static inline void sat_v3_set_node_id(uint8_t node_id[3], uint8_t zone, uint16_t node) {
    node_id[0] = zone;
    node_id[1] = (node >> 8) & 0xFF;
    node_id[2] = node & 0xFF;
}

/** 3 バイト配列からノード ID を読み出す (32-bit) */
static inline uint32_t sat_v3_get_node_id(const uint8_t node_id[3]) {
    return ((uint32_t)node_id[0] << 16)
         | ((uint32_t)node_id[1] <<  8)
         |  (uint32_t)node_id[2];
}

/** このパケットが自分宛か判定する (Global または自ノード ID と一致) */
static inline int sat_v3_is_my_packet(const uint8_t node_id[3], uint32_t my_node_id) {
    uint32_t target = sat_v3_get_node_id(node_id);
    return (target == SAT_V3_NODE_GLOBAL) || (target == my_node_id);
}

/* ==========================================================
 *  Ver 3.0 エンコードヘルパー
 * ========================================================== */

static inline void sat_v3_ctrl_init(sat_v3_ctrl_pkt_t *pkt) {
    memset(pkt, 0, sizeof(*pkt));
    pkt->signature = SAT_V3_SIGNATURE;
    pkt->pkt_type  = SAT_V3_PKT_CTRL;
    pkt->version   = 0x03;
}

static inline void sat_v3_ctrl_set_trans_ms(sat_v3_ctrl_pkt_t *pkt, uint16_t ms) {
    pkt->trans_ms_hi = (ms >> 8) & 0xFF;
    pkt->trans_ms_lo = ms & 0xFF;
}

static inline void sat_v3_ctrl_set_execute_at(sat_v3_ctrl_pkt_t *pkt, uint32_t ms) {
    pkt->execute_at_ms[0] = (ms >> 24) & 0xFF;
    pkt->execute_at_ms[1] = (ms >> 16) & 0xFF;
    pkt->execute_at_ms[2] = (ms >>  8) & 0xFF;
    pkt->execute_at_ms[3] =  ms        & 0xFF;
    if (ms != 0) {
        pkt->flags |= SAT_V3_FLAG_PTP_VALID;
    }
}

static inline void sat_v3_ctrl_finalize(sat_v3_ctrl_pkt_t *pkt) {
    pkt->crc8 = sat_v3_crc8((const uint8_t *)pkt, SAT_V3_CTRL_SIZE - 1);
}

static inline void sat_v3_content_init(sat_v3_content_pkt_t *pkt) {
    memset(pkt, 0, sizeof(*pkt));
    pkt->signature = SAT_V3_SIGNATURE;
    pkt->pkt_type  = SAT_V3_PKT_CONTENT;
    pkt->version   = 0x03;
}

static inline void sat_v3_content_finalize(sat_v3_content_pkt_t *pkt) {
    pkt->crc8 = sat_v3_crc8((const uint8_t *)pkt, SAT_V3_CONTENT_SIZE - 1);
}

static inline void sat_v3_nav_init(sat_v3_nav_pkt_t *pkt) {
    memset(pkt, 0, sizeof(*pkt));
    pkt->signature = SAT_V3_SIGNATURE;
    pkt->pkt_type  = SAT_V3_PKT_NAV;
    pkt->version   = 0x03;
}

static inline void sat_v3_nav_finalize(sat_v3_nav_pkt_t *pkt) {
    pkt->crc8 = sat_v3_crc8((const uint8_t *)pkt, SAT_V3_NAV_SIZE - 1);
}

static inline void sat_v3_heartbeat_init(sat_v3_heartbeat_pkt_t *pkt, uint32_t uptime_s) {
    memset(pkt, 0, sizeof(*pkt));
    pkt->signature   = SAT_V3_SIGNATURE;
    pkt->pkt_type    = SAT_V3_PKT_HEARTBEAT;
    pkt->version     = 0x03;
    pkt->uptime_s[0] = (uptime_s >> 24) & 0xFF;
    pkt->uptime_s[1] = (uptime_s >> 16) & 0xFF;
    pkt->uptime_s[2] = (uptime_s >>  8) & 0xFF;
    pkt->uptime_s[3] =  uptime_s        & 0xFF;
    pkt->crc8        = sat_v3_crc8((const uint8_t *)pkt, SAT_V3_HEARTBEAT_SIZE - 1);
}

/* ==========================================================
 *  Ver 3.0 デコードヘルパー
 *  戻り値: 1=OK, 0=不完全, -1=エラー(署名/CRC/種別不一致)
 * ========================================================== */

static inline int sat_v3_ctrl_decode(const uint8_t *buf, size_t len,
                                     sat_v3_ctrl_pkt_t *out) {
    if (len < SAT_V3_CTRL_SIZE)             return 0;
    if (buf[0] != SAT_V3_SIGNATURE)         return -1;
    if (buf[1] != SAT_V3_PKT_CTRL)         return -1;
    uint8_t expected = sat_v3_crc8(buf, SAT_V3_CTRL_SIZE - 1);
    if (buf[SAT_V3_CTRL_SIZE - 1] != expected) return -1;
    memcpy(out, buf, SAT_V3_CTRL_SIZE);
    return 1;
}

static inline int sat_v3_content_decode(const uint8_t *buf, size_t len,
                                        sat_v3_content_pkt_t *out) {
    if (len < SAT_V3_CONTENT_SIZE)          return 0;
    if (buf[0] != SAT_V3_SIGNATURE)         return -1;
    if (buf[1] != SAT_V3_PKT_CONTENT)      return -1;
    uint8_t expected = sat_v3_crc8(buf, SAT_V3_CONTENT_SIZE - 1);
    if (buf[SAT_V3_CONTENT_SIZE - 1] != expected) return -1;
    memcpy(out, buf, SAT_V3_CONTENT_SIZE);
    return 1;
}

static inline int sat_v3_nav_decode(const uint8_t *buf, size_t len,
                                    sat_v3_nav_pkt_t *out) {
    if (len < SAT_V3_NAV_SIZE)              return 0;
    if (buf[0] != SAT_V3_SIGNATURE)         return -1;
    if (buf[1] != SAT_V3_PKT_NAV)          return -1;
    uint8_t expected = sat_v3_crc8(buf, SAT_V3_NAV_SIZE - 1);
    if (buf[SAT_V3_NAV_SIZE - 1] != expected) return -1;
    memcpy(out, buf, SAT_V3_NAV_SIZE);
    return 1;
}

#endif
