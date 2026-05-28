/**
 * @file main.cpp
 * @brief LED ノード Wi-Fi + UDP Ver 3.0 受信実装
 *
 * Waveshare ESP32-S3-Zero
 *   Block1 (GPIO12): 440 個の WS2812B LED (GRB)
 *   Block2 (GPIO13): 440 個の WS2812B LED (GRB)
 *
 * 通信:
 *   Wi-Fi STA モード → UDP マルチキャスト 239.255.0.1:6454
 *   プロトコル: hub_protocol.h Ver 3.0
 *
 * 動作フロー:
 *   起動 → Wi-Fi 接続 → マルチキャスト参加 → UDP 受信ループ
 *   ハートビート途絶 3秒 → セーフティ白 5% に遷移
 */

#include <Arduino.h>
#include <FastLED.h>
#include <WiFi.h>
#include <WiFiUDP.h>
#include <esp_task_wdt.h>
#include "hub_protocol.h"

/* ====================================================================
 * ★ デバイスごとに書き換えるパラメータ
 * ==================================================================== */
// Wi-Fi 認証情報
#define WIFI_SSID        "JCOM_CFAA"
#define WIFI_PASSWORD    "558550064158"

// このノードの識別子 (書き込み前に変更する)
// Zone: 物理位置 (1〜255),  Node: 座席番号等 (1〜65535)
#ifndef MY_ZONE
#define MY_ZONE   1
#endif
#ifndef MY_NODE
#define MY_NODE   1
#endif

/* ====================================================================
 * 定数
 * ==================================================================== */
#define WIFI_TIMEOUT_MS     10000U
#define WIFI_RETRY_DELAY_MS  5000U
#define UDP_RX_BUF_SIZE       128U

#define LED_PIN_BLOCK1        12
#define LED_PIN_BLOCK2        13
#define NUM_LEDS_BLOCK1      440
#define NUM_LEDS_BLOCK2      440
#define LED_TYPE              WS2812B
#define COLOR_ORDER           GRB

#define HEARTBEAT_TIMEOUT_MS 3000U   // 3秒応答なし → セーフ白

// 電源保護: FastLED のソフトウェア電流制限 (5V系)
#define LED_POWER_LIMIT_MA    2500U

// LED マトリクスレイアウト (88列 × 10行, Block1=上5行, Block2=下5行)
#define MATRIX_COLS   88
#define MATRIX_ROWS   10
#define MATRIX_ROWS_PER_BLOCK  5   // Block1 / Block2 それぞれ 5行

// 5×8 ビットマップフォント
#define FONT_W  5
#define FONT_H  8

// 暴走対策: メインループが停止した場合に自動リセット
#define LOOP_WDT_TIMEOUT_S       8

/* ====================================================================
 * グローバル変数
 * ==================================================================== */

// ---- LED ----
CRGB gBlock1[NUM_LEDS_BLOCK1];
CRGB gBlock2[NUM_LEDS_BLOCK2];

// ---- Wi-Fi / UDP ----
static WiFiUDP   gUdp;
static uint8_t   gUdpRxBuf[UDP_RX_BUF_SIZE];
static bool      gNetReady = false;

// ---- ノード状態 ----
static uint32_t  gMyNodeId;              // (MY_ZONE<<16)|MY_NODE
static uint8_t   gGlobalBrightness  = 10;
static uint8_t   gBgAsset           = SAT_V3_BG_OFF;
static uint8_t   gTextMode          = SAT_V3_TEXT_OFF;
static uint8_t   gLastSeqNum        = 0;  // 冗長送信重複排除
static bool      gHeartbeatActive   = false;
static uint32_t  gLastHeartbeatMs   = 0;
static bool      gSafeMode          = true;

// ---- 予約実行 (execute_at_ms) ----
static bool              gCtrlPending      = false;
static uint32_t          gCtrlPendingAtMs  = 0;
static sat_v3_ctrl_pkt_t gCtrlPendingPkt;

// ---- BG アニメーション ----
static uint8_t   gRainbowHue        = 0;
static uint32_t  gAnimLastMs        = 0;

// FIRE: 熱拡散バッファ (Block1/Block2 共用)
static uint8_t   gFireHeat[NUM_LEDS_BLOCK1];  // Block1 と同サイズで十分

// STARFIELD: 各 LED の輝度と瞬きタイミング
struct StarCell { uint8_t bri; uint8_t speed; };
static StarCell  gStars1[NUM_LEDS_BLOCK1];
static StarCell  gStars2[NUM_LEDS_BLOCK2];
static bool      gStarsInited = false;

// ---- フェードトランジション ----
static CRGB      gFadeSnap1[NUM_LEDS_BLOCK1];  // BG 切替前フレームのスナップショット
static CRGB      gFadeSnap2[NUM_LEDS_BLOCK2];
static bool      gFadeActive   = false;
static uint32_t  gFadeStartMs  = 0;
static uint16_t  gFadeDurMs    = 0;

// ---- NAV 点滅状態 ----
static bool      gNavActive         = false;
static uint8_t   gNavR, gNavG, gNavB;
static uint8_t   gNavBlinkRate      = 0;  // 0=常灯, 1=低速, 2=高速
static uint32_t  gNavBlinkLastMs    = 0;
static bool      gNavBlinkOn        = true;

// ---- 歌詞チャンク再構成 ----
#define LYRICS_MAX_CHUNKS     8    // 1行あたりの最大チャンク数
#define LYRICS_CHUNK_TEXT_MAX 32   // チャンクテキスト最大長 (ヘッダ除去後)
#define LYRICS_LINE_MAX       256  // 結合後の最大文字数

typedef struct {
    bool    received;
    char    text[LYRICS_CHUNK_TEXT_MAX + 1];
} lyrics_chunk_t;

static struct {
    uint16_t      song_id;
    uint8_t       version;
    uint8_t       total_chunks;
    uint8_t       received_count;
    lyrics_chunk_t chunks[LYRICS_MAX_CHUNKS];
    char          current_line[LYRICS_LINE_MAX];  // 直前有効行
} gLyrics;

// 前方宣言: apply_ctrl_packet() から使用
void led_all_off();

/* ====================================================================
 * 5×8 ASCIIビットマップフォント (0x20〜0x7E, 95文字)
 * 各エントリ: 5列分のバイト列, bit0=上端 bit7=下端
 * ==================================================================== */
static const uint8_t FONT5X8[95][FONT_W] PROGMEM = {
    {0x00,0x00,0x00,0x00,0x00}, // 0x20 ' '
    {0x00,0x00,0x5F,0x00,0x00}, // 0x21 '!'
    {0x00,0x07,0x00,0x07,0x00}, // 0x22 '"'
    {0x14,0x7F,0x14,0x7F,0x14}, // 0x23 '#'
    {0x24,0x2A,0x7F,0x2A,0x12}, // 0x24 '$'
    {0x23,0x13,0x08,0x64,0x62}, // 0x25 '%'
    {0x36,0x49,0x55,0x22,0x50}, // 0x26 '&'
    {0x00,0x05,0x03,0x00,0x00}, // 0x27 '\''
    {0x00,0x1C,0x22,0x41,0x00}, // 0x28 '('
    {0x00,0x41,0x22,0x1C,0x00}, // 0x29 ')'
    {0x14,0x08,0x3E,0x08,0x14}, // 0x2A '*'
    {0x08,0x08,0x3E,0x08,0x08}, // 0x2B '+'
    {0x00,0x50,0x30,0x00,0x00}, // 0x2C ','
    {0x08,0x08,0x08,0x08,0x08}, // 0x2D '-'
    {0x00,0x60,0x60,0x00,0x00}, // 0x2E '.'
    {0x20,0x10,0x08,0x04,0x02}, // 0x2F '/'
    {0x3E,0x51,0x49,0x45,0x3E}, // 0x30 '0'
    {0x00,0x42,0x7F,0x40,0x00}, // 0x31 '1'
    {0x42,0x61,0x51,0x49,0x46}, // 0x32 '2'
    {0x21,0x41,0x45,0x4B,0x31}, // 0x33 '3'
    {0x18,0x14,0x12,0x7F,0x10}, // 0x34 '4'
    {0x27,0x45,0x45,0x45,0x39}, // 0x35 '5'
    {0x3C,0x4A,0x49,0x49,0x30}, // 0x36 '6'
    {0x01,0x71,0x09,0x05,0x03}, // 0x37 '7'
    {0x36,0x49,0x49,0x49,0x36}, // 0x38 '8'
    {0x06,0x49,0x49,0x52,0x3C}, // 0x39 '9'
    {0x00,0x36,0x36,0x00,0x00}, // 0x3A ':'
    {0x00,0x56,0x36,0x00,0x00}, // 0x3B ';'
    {0x08,0x14,0x22,0x41,0x00}, // 0x3C '<'
    {0x14,0x14,0x14,0x14,0x14}, // 0x3D '='
    {0x00,0x41,0x22,0x14,0x08}, // 0x3E '>'
    {0x02,0x01,0x51,0x09,0x06}, // 0x3F '?'
    {0x32,0x49,0x79,0x41,0x3E}, // 0x40 '@'
    {0x7E,0x11,0x11,0x11,0x7E}, // 0x41 'A'
    {0x7F,0x49,0x49,0x49,0x36}, // 0x42 'B'
    {0x3E,0x41,0x41,0x41,0x22}, // 0x43 'C'
    {0x7F,0x41,0x41,0x22,0x1C}, // 0x44 'D'
    {0x7F,0x49,0x49,0x49,0x41}, // 0x45 'E'
    {0x7F,0x09,0x09,0x09,0x01}, // 0x46 'F'
    {0x3E,0x41,0x49,0x49,0x7A}, // 0x47 'G'
    {0x7F,0x08,0x08,0x08,0x7F}, // 0x48 'H'
    {0x00,0x41,0x7F,0x41,0x00}, // 0x49 'I'
    {0x20,0x40,0x41,0x3F,0x01}, // 0x4A 'J'
    {0x7F,0x08,0x14,0x22,0x41}, // 0x4B 'K'
    {0x7F,0x40,0x40,0x40,0x40}, // 0x4C 'L'
    {0x7F,0x02,0x04,0x02,0x7F}, // 0x4D 'M'
    {0x7F,0x04,0x08,0x10,0x7F}, // 0x4E 'N'
    {0x3E,0x41,0x41,0x41,0x3E}, // 0x4F 'O'
    {0x7F,0x09,0x09,0x09,0x06}, // 0x50 'P'
    {0x3E,0x41,0x51,0x21,0x5E}, // 0x51 'Q'
    {0x7F,0x09,0x19,0x29,0x46}, // 0x52 'R'
    {0x46,0x49,0x49,0x49,0x31}, // 0x53 'S'
    {0x01,0x01,0x7F,0x01,0x01}, // 0x54 'T'
    {0x3F,0x40,0x40,0x40,0x3F}, // 0x55 'U'
    {0x1F,0x20,0x40,0x20,0x1F}, // 0x56 'V'
    {0x3F,0x40,0x38,0x40,0x3F}, // 0x57 'W'
    {0x63,0x14,0x08,0x14,0x63}, // 0x58 'X'
    {0x07,0x08,0x70,0x08,0x07}, // 0x59 'Y'
    {0x61,0x51,0x49,0x45,0x43}, // 0x5A 'Z'
    {0x00,0x7F,0x41,0x41,0x00}, // 0x5B '['
    {0x02,0x04,0x08,0x10,0x20}, // 0x5C '\\'
    {0x00,0x41,0x41,0x7F,0x00}, // 0x5D ']'
    {0x04,0x02,0x01,0x02,0x04}, // 0x5E '^'
    {0x40,0x40,0x40,0x40,0x40}, // 0x5F '_'
    {0x00,0x01,0x02,0x04,0x00}, // 0x60 '`'
    {0x20,0x54,0x54,0x54,0x78}, // 0x61 'a'
    {0x7F,0x48,0x44,0x44,0x38}, // 0x62 'b'
    {0x38,0x44,0x44,0x44,0x20}, // 0x63 'c'
    {0x38,0x44,0x44,0x48,0x7F}, // 0x64 'd'
    {0x38,0x54,0x54,0x54,0x18}, // 0x65 'e'
    {0x08,0x7E,0x09,0x01,0x02}, // 0x66 'f'
    {0x0C,0x52,0x52,0x52,0x3E}, // 0x67 'g'
    {0x7F,0x08,0x04,0x04,0x78}, // 0x68 'h'
    {0x00,0x44,0x7D,0x40,0x00}, // 0x69 'i'
    {0x20,0x40,0x44,0x3D,0x00}, // 0x6A 'j'
    {0x7F,0x10,0x28,0x44,0x00}, // 0x6B 'k'
    {0x00,0x41,0x7F,0x40,0x00}, // 0x6C 'l'
    {0x7C,0x04,0x18,0x04,0x78}, // 0x6D 'm'
    {0x7C,0x08,0x04,0x04,0x78}, // 0x6E 'n'
    {0x38,0x44,0x44,0x44,0x38}, // 0x6F 'o'
    {0x7C,0x14,0x14,0x14,0x08}, // 0x70 'p'
    {0x08,0x14,0x14,0x18,0x7C}, // 0x71 'q'
    {0x7C,0x08,0x04,0x04,0x08}, // 0x72 'r'
    {0x48,0x54,0x54,0x54,0x20}, // 0x73 's'
    {0x04,0x3F,0x44,0x40,0x20}, // 0x74 't'
    {0x3C,0x40,0x40,0x40,0x7C}, // 0x75 'u'
    {0x1C,0x20,0x40,0x20,0x1C}, // 0x76 'v'
    {0x3C,0x40,0x30,0x40,0x3C}, // 0x77 'w'
    {0x44,0x28,0x10,0x28,0x44}, // 0x78 'x'
    {0x0C,0x50,0x50,0x50,0x3C}, // 0x79 'y'
    {0x44,0x64,0x54,0x4C,0x44}, // 0x7A 'z'
    {0x00,0x08,0x36,0x41,0x00}, // 0x7B '{'
    {0x00,0x00,0x7F,0x00,0x00}, // 0x7C '|'
    {0x00,0x41,0x36,0x08,0x00}, // 0x7D '}'
    {0x08,0x08,0x2A,0x1C,0x08}, // 0x7E '~'
};

/* ====================================================================
 * マトリクス座標 → LED インデックス変換 (サーペンタイン)
 *   x: 0〜87 (列), y: 0〜9 (行, 0=最上段)
 *   y 0〜4 → Block1,  y 5〜9 → Block2
 * ==================================================================== */
static CRGB& matrix_pixel(int x, int y) {
    if (x < 0 || x >= MATRIX_COLS) x = 0;
    if (y < 0 || y >= MATRIX_ROWS) y = 0;
    if (y < MATRIX_ROWS_PER_BLOCK) {
        uint16_t idx = (y % 2 == 0)
            ? (uint16_t)(y * MATRIX_COLS + x)
            : (uint16_t)(y * MATRIX_COLS + (MATRIX_COLS - 1 - x));
        return gBlock1[idx];
    } else {
        int ly = y - MATRIX_ROWS_PER_BLOCK;
        uint16_t idx = (ly % 2 == 0)
            ? (uint16_t)(ly * MATRIX_COLS + x)
            : (uint16_t)(ly * MATRIX_COLS + (MATRIX_COLS - 1 - x));
        return gBlock2[idx];
    }
}

/* ====================================================================
 * テキストレイヤー描画
 *   text:  ASCII 文字列 (UTF-8マルチバイトは '?' で代替)
 *   color: 文字色
 *   row_offset: 縦方向の描画開始行 (デフォルト 1 = 上1px余白)
 * ==================================================================== */
void draw_text_layer(const char* text, CRGB color, int row_offset = 1) {
    if (!text || text[0] == '\0') return;
    int cx = 0;
    for (int ci = 0; text[ci] != '\0'; ci++) {
        uint8_t ch = (uint8_t)text[ci];
        // UTF-8 マルチバイト: リードバイト (0xC0-) → 続くバイト数を計算してスキップ
        if (ch >= 0x80) {
            if (ch >= 0xC0) {
                // リードバイト: 0b110x=1続き, 0b1110=2続き, 0b11110=3続き
                int extra = (ch >= 0xF0) ? 3 : (ch >= 0xE0) ? 2 : 1;
                ci += extra;
            }
            // continuation byte または上で先頭を飛ばした → スキップ
            ch = '?';
        }
        // 制御文字はスペース扱い
        if (ch < 0x20) ch = ' ';
        if (ch > 0x7E) ch = '?';

        // 右端超えたら停止 (1行描画)
        if (cx + FONT_W > MATRIX_COLS) break;

        // 1文字を FONT_W 列 × FONT_H 行で描画
        for (int col = 0; col < FONT_W; col++) {
            uint8_t colbits = pgm_read_byte(&FONT5X8[ch - 0x20][col]);
            for (int row = 0; row < FONT_H; row++) {
                if (colbits & (1 << row)) {
                    int py = row_offset + row;
                    if (py < MATRIX_ROWS) {
                        matrix_pixel(cx + col, py) = color;
                    }
                }
            }
        }
        cx += FONT_W + 1;  // 1px 文字間スペース
    }
}

/* ====================================================================
 * シーンプリセット適用
 *   pkt の bg_asset / text_mode / dimmer / trans_ms をシーン定義で上書きする
 * ==================================================================== */
static void apply_scene(sat_v3_ctrl_pkt_t *pkt) {
    switch (pkt->scene_id) {
        case SAT_V3_SCENE_LIVE:
            pkt->bg_asset   = SAT_V3_BG_FIRE;
            pkt->text_mode  = SAT_V3_TEXT_LYRICS;
            pkt->dimmer     = 255;
            pkt->trans_ms_hi = 0;  pkt->trans_ms_lo = 255;  // 255ms
            Serial.println("[SCENE] LIVE");
            break;
        case SAT_V3_SCENE_HEALING:
            pkt->bg_asset   = SAT_V3_BG_OCEAN;
            pkt->text_mode  = SAT_V3_TEXT_OFF;
            pkt->dimmer     = 140;
            pkt->trans_ms_hi = 3;  pkt->trans_ms_lo = 232;  // 1000ms
            Serial.println("[SCENE] HEALING");
            break;
        case SAT_V3_SCENE_ENTRY:
            pkt->bg_asset   = SAT_V3_BG_STARFIELD;
            pkt->text_mode  = SAT_V3_TEXT_OFF;
            pkt->dimmer     = 180;
            pkt->trans_ms_hi = 3;  pkt->trans_ms_lo = 32;   // 800ms
            Serial.println("[SCENE] ENTRY");
            break;
        case SAT_V3_SCENE_OFF:
            pkt->bg_asset   = SAT_V3_BG_OFF;
            pkt->text_mode  = SAT_V3_TEXT_OFF;
            pkt->dimmer     = 0;
            pkt->trans_ms_hi = 1;  pkt->trans_ms_lo = 244;  // 500ms
            Serial.println("[SCENE] OFF");
            break;
        default:
            break;
    }
}

/* ====================================================================
 * CTRL 適用本体
 *   decode/宛先/重複判定/予約判定は呼び出し側で実施済みとする
 * ==================================================================== */
static void apply_ctrl_packet(sat_v3_ctrl_pkt_t *pkt) {
    // Dimmer 適用
    if (pkt->dimmer != gGlobalBrightness) {
        gGlobalBrightness = pkt->dimmer;
        FastLED.setBrightness(pkt->dimmer);
    }

    // scene_id が指定されている場合はプリセットで各フィールドを上書き
    if (pkt->scene_id != SAT_V3_SCENE_NONE) {
        apply_scene(pkt);
    }

    // trans_ms を先に取り出す (BG 切替処理で参照するため)
    uint16_t trans_ms = ((uint16_t)pkt->trans_ms_hi << 8) | pkt->trans_ms_lo;

    // BG Asset 切り替え
    if (pkt->bg_asset != gBgAsset) {
        // フェードトランジション: trans_ms > 0 かつ safe mode 外のときスナップショット取得
        if (trans_ms > 0 && !gSafeMode) {
            memcpy(gFadeSnap1, gBlock1, sizeof(gFadeSnap1));
            memcpy(gFadeSnap2, gBlock2, sizeof(gFadeSnap2));
            gFadeActive  = true;
            gFadeStartMs = millis();
            gFadeDurMs   = trans_ms;
        } else {
            gFadeActive = false;
        }
        gBgAsset     = pkt->bg_asset;
        gStarsInited = false;  // STARFIELD 再初期化
        if (pkt->bg_asset == SAT_V3_BG_OFF && !gFadeActive) {
            led_all_off();
        }
    }

    // Text Mode 切り替え
    gTextMode = pkt->text_mode;

    // Force Reset フラグ検出: 即座に再起動
    if (pkt->flags & SAT_V3_FLAG_FORCE_RESET) {
        Serial.println("[CTRL] FORCE_RESET received — restarting");
        delay(100);
        esp_restart();
    }

    Serial.printf("[CTRL] bg=%d txt=%d dim=%d trans=%dms seq=%d\n",
                  pkt->bg_asset, pkt->text_mode, pkt->dimmer, trans_ms, pkt->seq_num);
}

/* ====================================================================
 * LED 基本制御
 * ==================================================================== */

void led_safe_white() {
    uint8_t bri = (255 * 5) / 100;  // 5%
    FastLED.setBrightness(bri);
    fill_solid(gBlock1, NUM_LEDS_BLOCK1, CRGB::White);
    fill_solid(gBlock2, NUM_LEDS_BLOCK2, CRGB::White);
    FastLED.show();
}

void led_all_off() {
    fill_solid(gBlock1, NUM_LEDS_BLOCK1, CRGB::Black);
    fill_solid(gBlock2, NUM_LEDS_BLOCK2, CRGB::Black);
    FastLED.show();
}

void led_fill(uint8_t r, uint8_t g, uint8_t b) {
    CRGB c(r, g, b);
    fill_solid(gBlock1, NUM_LEDS_BLOCK1, c);
    fill_solid(gBlock2, NUM_LEDS_BLOCK2, c);
    FastLED.show();
}

/* ====================================================================
 * BG アニメーション更新 (50fps)
 * ==================================================================== */

// update_bg_anim: gBlock1/gBlock2 のピクセルのみ更新 (show()呼び出しなし)
// タイミング制御・show()呼び出しは loop() 側で管理
void update_bg_anim() {
    switch (gBgAsset) {
        case SAT_V3_BG_OFF:
            // OFF時はバッファクリアを呼び出し元に委ねる
            break;

        case SAT_V3_BG_RAINBOW:
            fill_rainbow(gBlock1, NUM_LEDS_BLOCK1, gRainbowHue, 3);
            fill_rainbow(gBlock2, NUM_LEDS_BLOCK2, gRainbowHue + 128, 3);
            gRainbowHue++;
            break;

        case SAT_V3_BG_PULSE: {
            uint8_t bri = beatsin8(30, 20, 255);
            fill_solid(gBlock1, NUM_LEDS_BLOCK1, CHSV(0, 255, bri));
            fill_solid(gBlock2, NUM_LEDS_BLOCK2, CHSV(0, 255, bri));
            break;
        }

        case SAT_V3_BG_FIRE: {
            // 熱拡散モデル: 底部(index 0)から発火、先端へ熱が伝わり冷却される
            const uint8_t COOLING  = 55;  // 冷却速度 (大きいほど短い炎)
            const uint8_t SPARKING = 120; // 発火確率 (大きいほど激しい)
            uint16_t n = NUM_LEDS_BLOCK1;

            // 1. 冷却
            for (uint16_t i = 0; i < n; i++) {
                uint8_t cool = random8(0, ((COOLING * 10) / n) + 2);
                gFireHeat[i] = qsub8(gFireHeat[i], cool);
            }
            // 2. 熱拡散 (上方向へ)
            for (uint16_t i = n - 1; i >= 2; i--) {
                gFireHeat[i] = (gFireHeat[i - 1] + gFireHeat[i - 2] + gFireHeat[i - 2]) / 3;
            }
            // 3. 底部でランダム発火
            if (random8() < SPARKING) {
                uint8_t y = random8(7);
                gFireHeat[y] = qadd8(gFireHeat[y], random8(160, 255));
            }
            // 4. 熱値を炎パレットで色に変換
            for (uint16_t i = 0; i < n; i++) {
                CRGB c = HeatColor(gFireHeat[i]);
                gBlock1[i] = c;
                // Block2 は Block1 の逆順（対称炎）
                gBlock2[n - 1 - i] = c;
            }
            break;
        }

        case SAT_V3_BG_OCEAN: {
            // 青緑グラデーション + sin 波で波打ち
            uint32_t t = millis();
            for (uint16_t i = 0; i < NUM_LEDS_BLOCK1; i++) {
                // 各 LED に位相差を付けた sin 波で明度変動
                uint8_t wave1 = sin8((uint8_t)(t / 20 + i * 3));
                uint8_t wave2 = sin8((uint8_t)(t / 13 + i * 5 + 80));
                uint8_t bri   = scale8(qadd8(wave1 / 2, wave2 / 2), 220) + 30;
                // 青 (hue=145〜165) の範囲でゆらぐ
                uint8_t hue   = 145 + scale8(sin8((uint8_t)(i * 4 + t / 40)), 20);
                gBlock1[i] = CHSV(hue, 220, bri);
            }
            for (uint16_t i = 0; i < NUM_LEDS_BLOCK2; i++) {
                uint8_t wave1 = sin8((uint8_t)(t / 20 + i * 3 + 60));
                uint8_t wave2 = sin8((uint8_t)(t / 13 + i * 5 + 140));
                uint8_t bri   = scale8(qadd8(wave1 / 2, wave2 / 2), 220) + 30;
                uint8_t hue   = 145 + scale8(sin8((uint8_t)(i * 4 + t / 40 + 60)), 20);
                gBlock2[i] = CHSV(hue, 220, bri);
            }
            break;
        }

        case SAT_V3_BG_STARFIELD: {
            // 初回: 星をランダム初期化
            if (!gStarsInited) {
                for (uint16_t i = 0; i < NUM_LEDS_BLOCK1; i++) {
                    gStars1[i].bri   = random8();
                    gStars1[i].speed = random8(1, 6);
                }
                for (uint16_t i = 0; i < NUM_LEDS_BLOCK2; i++) {
                    gStars2[i].bri   = random8();
                    gStars2[i].speed = random8(1, 6);
                }
                gStarsInited = true;
            }
            // 各 LED の輝度を独立した速度で増減 (三角波)
            for (uint16_t i = 0; i < NUM_LEDS_BLOCK1; i++) {
                gStars1[i].bri = sin8(gStars1[i].bri + gStars1[i].speed);
                // 暗い星: 白 (hue=0 sat=0)、明るい星: わずかに青白
                uint8_t sat = (gStars1[i].bri > 180) ? 30 : 0;
                gBlock1[i]  = CHSV(160, sat, gStars1[i].bri);
            }
            for (uint16_t i = 0; i < NUM_LEDS_BLOCK2; i++) {
                gStars2[i].bri = sin8(gStars2[i].bri + gStars2[i].speed);
                uint8_t sat = (gStars2[i].bri > 180) ? 30 : 0;
                gBlock2[i]  = CHSV(160, sat, gStars2[i].bri);
            }
            break;
        }

        default:
            break;
    }
}

/* ====================================================================
 * NAV 点滅更新
 * ==================================================================== */

void update_nav_blink() {
    if (!gNavActive) return;

    uint32_t now      = millis();
    uint32_t interval = (gNavBlinkRate == 0) ? 0u
                      : (gNavBlinkRate == 1) ? 800u
                      : 300u;  // rate=2 → 高速

    if (interval == 0) {
        led_fill(gNavR, gNavG, gNavB);
        return;
    }

    if (now - gNavBlinkLastMs >= interval) {
        gNavBlinkLastMs = now;
        gNavBlinkOn     = !gNavBlinkOn;
        if (gNavBlinkOn) {
            led_fill(gNavR, gNavG, gNavB);
        } else {
            led_all_off();
        }
    }
}

/* ====================================================================
 * Wi-Fi / UDP 初期化
 * ==================================================================== */

bool wifi_connect() {
    Serial.printf("[WiFi] Connecting to '%s'", WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    uint32_t start = millis();
    while (WiFi.status() != WL_CONNECTED) {
        if (millis() - start > WIFI_TIMEOUT_MS) {
            Serial.println("\n[WiFi] Timeout");
            return false;
        }
        delay(250);
        Serial.print(".");
        // 接続中インジケータ: 暗い青点滅
        static bool tog = false;
        tog = !tog;
        led_fill(0, 0, tog ? 30 : 0);
    }
    Serial.printf("\n[WiFi] Connected  IP=%s  RSSI=%ddBm\n",
                  WiFi.localIP().toString().c_str(), WiFi.RSSI());
    return true;
}

bool udp_begin() {
    IPAddress mcastIP;
    mcastIP.fromString(SAT_V3_MCAST_GROUP);
    if (!gUdp.beginMulticast(mcastIP, SAT_V3_UDP_PORT)) {
        Serial.println("[UDP] beginMulticast FAILED");
        return false;
    }
    Serial.printf("[UDP] Joined  group=%s  port=%d\n",
                  SAT_V3_MCAST_GROUP, SAT_V3_UDP_PORT);
    return true;
}

/* ====================================================================
 * UDP パケットハンドラ
 * ==================================================================== */

// ---- PKT_CTRL (0x10) ----
void handle_ctrl(const uint8_t *buf, int len) {
    sat_v3_ctrl_pkt_t pkt;
    if (sat_v3_ctrl_decode(buf, (size_t)len, &pkt) != 1) {
        Serial.println("[CTRL] CRC/size error — dropped");
        return;
    }

    // 宛先確認 (Global or 自ノード)
    if (!sat_v3_is_my_packet(pkt.node_id, gMyNodeId)) return;

    // 冗長送信重複排除
    if ((pkt.flags & SAT_V3_FLAG_REDUNDANT) && pkt.seq_num == gLastSeqNum) {
        return;
    }
    gLastSeqNum = pkt.seq_num;

    // ハートビートタイマーをリセット
    gLastHeartbeatMs = millis();
    gHeartbeatActive = true;
    gSafeMode        = false;

    // execute_at_ms が未来時刻なら予約し、到達時に適用する
    uint32_t execute_at_ms = ((uint32_t)pkt.execute_at_ms[0] << 24)
                           | ((uint32_t)pkt.execute_at_ms[1] << 16)
                           | ((uint32_t)pkt.execute_at_ms[2] << 8)
                           | (uint32_t)pkt.execute_at_ms[3];
    bool has_schedule = ((pkt.flags & SAT_V3_FLAG_PTP_VALID) != 0u) && (execute_at_ms != 0u);
    if (has_schedule) {
        uint32_t now = millis();
        uint32_t target_ms = execute_at_ms;
        // 実運用では PTP 未導入のため、60秒以下の値は「受信時点からの相対遅延」として扱う
        if (execute_at_ms <= 60000u) {
            target_ms = now + execute_at_ms;
        }
        int32_t diff = (int32_t)(target_ms - now);
        if (diff > 0) {
            gCtrlPendingPkt  = pkt;
            gCtrlPendingAtMs = target_ms;
            gCtrlPending     = true;
            Serial.printf("[CTRL] scheduled t=%u (in %ldms) raw=%u seq=%d\n",
                          (unsigned)target_ms, (long)diff, (unsigned)execute_at_ms, pkt.seq_num);
            return;
        }
    }

    // 即時適用コマンドを受けた場合は保留中コマンドを破棄
    gCtrlPending = false;

    apply_ctrl_packet(&pkt);
}

/* ====================================================================
 * 歌詞チャンク再構成
 * ==================================================================== */

// 全チャンクのテキストが準備できたら結合して current_line を更新
// received フラグではなくテキスト非空チェックを使う・ディフ導入で持ち越しテキストも利用できる
static void lyrics_assemble() {
    char assembled[LYRICS_LINE_MAX];
    size_t pos = 0;
    for (int i = 0; i < gLyrics.total_chunks && i < LYRICS_MAX_CHUNKS; i++) {
        if (gLyrics.chunks[i].text[0] == '\0') {
            Serial.printf("[LYRICS] chunk %d/%d empty — keeping prev line\n",
                          i + 1, gLyrics.total_chunks);
            return;  // テキストなし: 直前有効行を維持
        }
        size_t tlen = strlen(gLyrics.chunks[i].text);
        if (pos + tlen < (size_t)(LYRICS_LINE_MAX - 1)) {
            memcpy(assembled + pos, gLyrics.chunks[i].text, tlen);
            pos += tlen;
        }
    }
    assembled[pos] = '\0';
    memcpy(gLyrics.current_line, assembled, pos + 1);
    Serial.printf("[LYRICS] line='%s'\n", gLyrics.current_line);
}

// PKT_CONTENT type=LYRICS の payload テキストを処理
// フォーマット: S{4hex}|V{2dec}|C{2dec}/{2dec}|{text}  (プレフィックス 17 bytes 固定)
static void handle_lyrics(const char *text, uint8_t tlen) {
    // 最低 17 bytes (プレフィックス) + 本文 1 byte 以上
    if (tlen < 18 || text[0] != 'S' || text[5] != '|' || text[6] != 'V'
        || text[9] != '|' || text[10] != 'C' || text[13] != '/'
        || text[16] != '|') {
        Serial.printf("[LYRICS] bad format tlen=%d\n", tlen);
        return;
    }

    // song_id (hex4)
    char hex4[5];  memcpy(hex4, text + 1, 4);  hex4[4] = '\0';
    uint16_t song_id = (uint16_t)strtol(hex4, nullptr, 16);

    // version (dec2)
    char dec2[3];  memcpy(dec2, text + 7, 2);  dec2[2] = '\0';
    uint8_t version = (uint8_t)atoi(dec2);

    // chunk index (dec2, 1-based)
    char cidx[3];  memcpy(cidx, text + 11, 2);  cidx[2] = '\0';
    uint8_t chunk_idx = (uint8_t)atoi(cidx);

    // total chunks (dec2)
    char ctot[3];  memcpy(ctot, text + 14, 2);  ctot[2] = '\0';
    uint8_t total = (uint8_t)atoi(ctot);

    if (chunk_idx == 0 || chunk_idx > LYRICS_MAX_CHUNKS
        || total == 0 || total > LYRICS_MAX_CHUNKS) {
        Serial.printf("[LYRICS] out of range chunk=%d total=%d\n", chunk_idx, total);
        return;
    }

    // song+version に応じて状態を切り替え
    if (song_id != gLyrics.song_id) {
        // 新曲: 全状態リセット
        memset(&gLyrics.chunks, 0, sizeof(gLyrics.chunks));
        gLyrics.song_id        = song_id;
        gLyrics.version        = version;
        gLyrics.total_chunks   = total;
        gLyrics.received_count = 0;
        Serial.printf("[LYRICS] new song=0x%04X ver=%d total=%d\n",
                      song_id, version, total);
    } else if (version != gLyrics.version) {
        // 差分更新: テキストを保持し、received フラグだけリセット
        for (int i = 0; i < LYRICS_MAX_CHUNKS; i++) {
            gLyrics.chunks[i].received = false;
        }
        Serial.printf("[LYRICS] diff update song=0x%04X ver %d->%d total=%d\n",
                      song_id, gLyrics.version, version, total);
        gLyrics.version        = version;
        gLyrics.total_chunks   = total;
        gLyrics.received_count = 0;
    }

    uint8_t idx = chunk_idx - 1;  // 0-based
    if (gLyrics.chunks[idx].received) {
        Serial.printf("[LYRICS] dup chunk=%d — ignored\n", chunk_idx);
        return;
    }

    // チャンクテキスト保存 (プレフィックス 17 bytes 後)
    uint8_t chunk_text_len = tlen - 17;
    if (chunk_text_len > LYRICS_CHUNK_TEXT_MAX) chunk_text_len = LYRICS_CHUNK_TEXT_MAX;
    memcpy(gLyrics.chunks[idx].text, text + 17, chunk_text_len);
    gLyrics.chunks[idx].text[chunk_text_len] = '\0';
    gLyrics.chunks[idx].received = true;
    gLyrics.received_count++;

    Serial.printf("[LYRICS] chunk %d/%d ok: '%s' (%d/%d)\n",
                  chunk_idx, total, gLyrics.chunks[idx].text,
                  gLyrics.received_count, total);

    // 全チャンク受信済 OR 差分モードでテキストが準備できた場合に列坂を試みる
    lyrics_assemble();
}

// ---- PKT_CONTENT (0x20) ----
void handle_content(const uint8_t *buf, int len) {
    sat_v3_content_pkt_t pkt;
    if (sat_v3_content_decode(buf, (size_t)len, &pkt) != 1) {
        Serial.println("[CONTENT] CRC/size error — dropped");
        return;
    }

    if (!sat_v3_is_my_packet(pkt.node_id, gMyNodeId)) return;

    // テキストを安全に取り出す (ヌル終端保証)
    uint8_t tlen = pkt.text_len;
    if (tlen > SAT_V3_CONTENT_TEXT_MAX) tlen = SAT_V3_CONTENT_TEXT_MAX;
    char text[SAT_V3_CONTENT_TEXT_MAX + 1];
    memcpy(text, pkt.text, tlen);
    text[tlen] = '\0';

    Serial.printf("[CONTENT] type=0x%02X slot=%d text='%s'\n",
                  pkt.content_type, pkt.slot, text);

    if (pkt.content_type == SAT_V3_CONTENT_LYRICS) {
        // 歌詞チャンク再構成ハンドラへ委譲
        handle_lyrics(text, tlen);
    } else {
        // MVP: テキストモードを CUSTOM に切り替え、白点灯 (表示実装は F-2)
        gTextMode = SAT_V3_TEXT_CUSTOM;
        if (gBgAsset == SAT_V3_BG_OFF) {
            FastLED.setBrightness(gGlobalBrightness);
            led_fill(255, 255, 255);
        }
    }
}

// ---- PKT_NAV (0x30) ----
void handle_nav(const uint8_t *buf, int len) {
    sat_v3_nav_pkt_t pkt;
    if (sat_v3_nav_decode(buf, (size_t)len, &pkt) != 1) {
        Serial.println("[NAV] CRC/size error — dropped");
        return;
    }

    if (!sat_v3_is_my_packet(pkt.node_id, gMyNodeId)) return;

    FastLED.setBrightness(pkt.intensity > 0 ? pkt.intensity : gGlobalBrightness);

    if (pkt.nav_direction == SAT_V3_NAV_OFF) {
        gNavActive = false;
        led_all_off();
        Serial.println("[NAV] OFF");
    } else {
        gNavR           = pkt.nav_color_r;
        gNavG           = pkt.nav_color_g;
        gNavB           = pkt.nav_color_b;
        gNavBlinkRate   = pkt.blink_rate;
        gNavBlinkLastMs = millis();
        gNavBlinkOn     = true;
        gNavActive      = true;
        Serial.printf("[NAV] dir=%d rgb=(%d,%d,%d) blink=%d intensity=%d\n",
                      pkt.nav_direction,
                      pkt.nav_color_r, pkt.nav_color_g, pkt.nav_color_b,
                      pkt.blink_rate, pkt.intensity);
    }
}

// ---- PKT_HEARTBEAT (0x40) ----
void handle_heartbeat(const uint8_t *buf, int len) {
    if (len < (int)SAT_V3_HEARTBEAT_SIZE) return;

    // HEARTBEAT は node_id を持たないので CRC のみ確認
    uint8_t expected = sat_v3_crc8(buf, SAT_V3_HEARTBEAT_SIZE - 1);
    if (buf[SAT_V3_HEARTBEAT_SIZE - 1] != expected) {
        Serial.println("[HB] CRC error — dropped");
        return;
    }

    gLastHeartbeatMs = millis();
    gHeartbeatActive = true;
    gSafeMode        = false;
}

// ---- メイン受信ディスパッチャ ----
void udp_receive() {
    int pkt_size = gUdp.parsePacket();
    if (pkt_size <= 0) return;

    // デバッグ: パケット受信を記録
    Serial.printf("[UDP] recv %d bytes from %s\n",
                  pkt_size, gUdp.remoteIP().toString().c_str());

    int len = gUdp.read(gUdpRxBuf, UDP_RX_BUF_SIZE);
    if (len < 2) return;

    // [1] 署名チェック — 0x53 以外は即破棄
    if (gUdpRxBuf[0] != SAT_V3_SIGNATURE) {
        Serial.printf("[UDP] bad sig=0x%02X — dropped\n", gUdpRxBuf[0]);
        return;
    }

    // [2] パケット種別で分岐
    switch (gUdpRxBuf[1]) {
        case SAT_V3_PKT_CTRL:
            handle_ctrl(gUdpRxBuf, len);
            break;
        case SAT_V3_PKT_CONTENT:
            handle_content(gUdpRxBuf, len);
            break;
        case SAT_V3_PKT_NAV:
            handle_nav(gUdpRxBuf, len);
            break;
        case SAT_V3_PKT_HEARTBEAT:
            handle_heartbeat(gUdpRxBuf, len);
            break;
        default:
            break;
    }
}

/* ====================================================================
 * ハートビートタイムアウト監視
 * ==================================================================== */

void check_heartbeat_timeout() {
    if (!gHeartbeatActive) return;

    if ((millis() - gLastHeartbeatMs) > HEARTBEAT_TIMEOUT_MS) {
        Serial.println("[LED Node] HEARTBEAT TIMEOUT — safe mode");
        gHeartbeatActive = false;
        gSafeMode        = true;
        gNavActive       = false;
        gBgAsset         = SAT_V3_BG_OFF;
        gTextMode        = SAT_V3_TEXT_OFF;
        led_safe_white();
    }
}

/* ====================================================================
 * setup() / loop()
 * ==================================================================== */

void setup() {
    Serial.begin(115200);
    Serial.setTimeout(0);
    // USB CDC が接続されるまで最大 3 秒待つ
    // (接続なしでも 3 秒後に自動で抜けるのでブロックしない)
    uint32_t ws = millis();
    while (!Serial && (millis() - ws) < 3000) { delay(10); }
    delay(100);  // バッファ安定待ち

    Serial.printf("\n[LED Node] Boot  Zone=%d Node=%d\n", MY_ZONE, MY_NODE);

    // ノード ID を事前計算
    gMyNodeId = ((uint32_t)MY_ZONE << 16) | (uint32_t)MY_NODE;

    // FastLED 初期化
    FastLED.addLeds<LED_TYPE, LED_PIN_BLOCK1, COLOR_ORDER>(
        gBlock1, NUM_LEDS_BLOCK1).setCorrection(TypicalLEDStrip);
    FastLED.addLeds<LED_TYPE, LED_PIN_BLOCK2, COLOR_ORDER>(
        gBlock2, NUM_LEDS_BLOCK2).setCorrection(TypicalLEDStrip);
    FastLED.setMaxPowerInVoltsAndMilliamps(5, LED_POWER_LIMIT_MA);
    FastLED.setBrightness(gGlobalBrightness);

    // ループ停止時の自動復帰用ウォッチドッグ
    esp_task_wdt_init(LOOP_WDT_TIMEOUT_S, true);
    esp_task_wdt_add(NULL);

    // 起動ビジュアル: 緑×3回点滅
    for (int i = 0; i < 3; i++) {
        led_fill(0, 255, 0); delay(120);
        led_all_off();       delay(120);
    }

    // 初期状態: セーフティ白 5%
    led_safe_white();
    gSafeMode = true;

    // Wi-Fi 接続 → UDP マルチキャスト参加
    bool wifiOk = wifi_connect();
    if (wifiOk) {
        led_fill(0, 60, 0);  // 接続成功: 暗い緑
        delay(1000);
        gNetReady = udp_begin();
    }

    if (!gNetReady) {
        // 失敗: オレンジ×5点滅 → セーフ白で待機
        Serial.println("[LED Node] Network FAILED — safe mode");
        for (int i = 0; i < 5; i++) {
            led_fill(255, 80, 0); delay(200);
            led_all_off();        delay(200);
        }
    }

    led_safe_white();
    gLastHeartbeatMs = millis();
    Serial.printf("[LED Node] Ready  ID=0x%06X  waiting for UDP...\n",
                  (unsigned)gMyNodeId);
}

void loop() {
    // ループが回っている限りWDTをキック
    esp_task_wdt_reset();

    uint32_t now = millis();

    // ---- Wi-Fi 切断時の再接続 ----
    if (WiFi.status() != WL_CONNECTED) {
        if (gNetReady) {
            Serial.println("[WiFi] Lost — reconnecting");
            gNetReady        = false;
            gHeartbeatActive = false;
            gSafeMode        = true;
            gCtrlPending     = false;
            led_safe_white();
        }
        delay(WIFI_RETRY_DELAY_MS);
        if (wifi_connect()) {
            gNetReady = udp_begin();
            if (gNetReady) {
                gLastHeartbeatMs = millis();
                led_safe_white();
            }
        }
        return;
    }

    // ---- UDP 受信 ----
    if (gNetReady) {
        udp_receive();
    }

    // ---- 予約 CTRL 適用 ----
    if (gCtrlPending && ((int32_t)(now - gCtrlPendingAtMs) >= 0)) {
        gCtrlPending = false;
        apply_ctrl_packet(&gCtrlPendingPkt);
    }

    // ---- ハートビートタイムアウト監視 ----
    check_heartbeat_timeout();

    // ---- BG + テキスト レンダリング (50fps スロットル) ----
    if (!gSafeMode && !gNavActive) {
        if (now - gAnimLastMs >= 20) {
            gAnimLastMs = now;
            // BG OFF 時はバッファを黒でクリア
            if (gBgAsset == SAT_V3_BG_OFF) {
                fill_solid(gBlock1, NUM_LEDS_BLOCK1, CRGB::Black);
                fill_solid(gBlock2, NUM_LEDS_BLOCK2, CRGB::Black);
            } else {
                update_bg_anim();
            }
            // フェードブレンド: スナップショット → 新 BG へ alpha 0→255 で補間
            if (gFadeActive) {
                uint32_t elapsed = now - gFadeStartMs;
                if (elapsed >= gFadeDurMs) {
                    gFadeActive = false;
                } else {
                    uint8_t alpha = (uint8_t)((uint32_t)elapsed * 255 / gFadeDurMs);
                    for (uint16_t i = 0; i < NUM_LEDS_BLOCK1; i++) {
                        gBlock1[i] = blend(gFadeSnap1[i], gBlock1[i], alpha);
                    }
                    for (uint16_t i = 0; i < NUM_LEDS_BLOCK2; i++) {
                        gBlock2[i] = blend(gFadeSnap2[i], gBlock2[i], alpha);
                    }
                }
            }

            // テキストオーバーレイ (SAT_V3_TEXT_LYRICS + current_line 有効時)
            if (gTextMode == SAT_V3_TEXT_LYRICS && gLyrics.current_line[0] != '\0') {
                draw_text_layer(gLyrics.current_line, CRGB::White);
            }
            FastLED.show();
        }
    }

    // ---- NAV 点滅更新 ----
    update_nav_blink();

    // ---- 定期ログ (5秒毎) ----
    static uint32_t sLogMs = 0;
    if (now - sLogMs >= 2000) {
        sLogMs = now;
        Serial.printf("[alive] t=%ums RSSI=%ddBm bg=%d txt=%d bri=%d safe=%d\n",
                      now, WiFi.RSSI(), gBgAsset, gTextMode,
                      gGlobalBrightness, gSafeMode ? 1 : 0);
    }
}

