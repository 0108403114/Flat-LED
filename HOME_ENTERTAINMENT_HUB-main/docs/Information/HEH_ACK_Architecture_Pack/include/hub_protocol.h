/**
 * @file hub_protocol.h
 * @brief HOME_ENTERTAINMENT_HUB 通信プロトコル仕様 Ver 3.1 (ACK動的制御対応版)
 */

#ifndef HUB_PROTOCOL_H
#define HUB_PROTOCOL_H

#include <stdint.h>
#include <string.h>

#define SAT_V3_SIGNATURE       0x53

// パケット種別 (pkt_type)
#define SAT_V3_PKT_CTRL        0x10
#define SAT_V3_PKT_CONTENT     0x20
#define SAT_V3_PKT_NAV         0x30
#define SAT_V3_PKT_HEARTBEAT   0x40
#define SAT_V3_PKT_ACK         0x50  // 新設: 到達確認応答パケット

// フラグビットマスク (flags)
#define SAT_V3_FLAG_REQ_ACK    (1 << 0)  // ビット0: 1=ACK要求, 0=ACK不要
#define SAT_V3_FLAG_REDUNDANT  (1 << 1)  // ビット1: 1=冗長重複パケット, 0=通常

#pragma pack(push, 1)

/**
 * @brief 中央から送出される制御構造体の共通ヘッダー（参考用）
 */
typedef struct {
    uint8_t signature;       // 0x53 固定
    uint8_t pkt_type;        // パケット種別
    uint8_t zone_id;         // 対象ゾーンID
    uint16_t node_id;        // 対象個別ノードID (0=Global一斉)
    uint8_t flags;           // ビット0: ACK要求フラグ等
    uint32_t sequence;       // シーケンス番号/タイムスタンプ
    // -- 以降、各種制御パラメータ(省略) --
} sat_v3_header_t;

/**
 * @brief 新設: サテライトノードから中央ノードへ返すACKパケット構造体 (サイズ固定)
 */
typedef struct {
    uint8_t signature;       // 0x53 固定
    uint8_t pkt_type;        // 0x50 (SAT_V3_PKT_ACK)
    uint8_t zone_id;         // 返信元ノードのゾーンID
    uint16_t node_id;        // 返信元ノードの個別ID
    uint32_t echo_seq;       // 受信パケットからオウム返しするシリアル/タイムスタンプ
    uint8_t status_code;     // 状態コード: 0x00=正常終了, 0x01=CRCエラー, 0x02=アセット欠損
    uint8_t crc8;            // 最終チェックサム
} sat_v3_ack_pkt_t;

#pragma pack(pop)

// CRC8 チェックサム簡易計算ヘルパー (実装はmain.cpp側を参照)
inline uint8_t sat_v3_crc8(const uint8_t *data, size_t len) {
    uint8_t crc = 0x00;
    for (size_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (int j = 0; j < 8; j++) {
            if (crc & 0x80) {
                crc = (crc << 1) ^ 0x07;
            } else {
                crc <<= 1;
            }
        }
    }
    return crc;
}

#endif // HUB_PROTOCOL_H
