/**
 * @file main_sample.cpp
 * @brief サテライトノード側における ACK 動的条件分岐処理の実装サンプル
 * @note PlatformIO / Arduino環境想定 (Waveshare ESP32-S3-Zero)
 */

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUDP.h>
#include "hub_protocol.h"

// デバイス固有定義パラメータ（書き込み環境に応じて変更）
#define MY_ZONE_ID   1
#define MY_NODE_ID   101

WiFiUDP gUdp;
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
const unsigned int localPort = 6454; // HEH 標準ポート

/**
 * @brief 中央ノード宛てにユニキャストで確認応答パケット(ACK)を送信
 */
void send_unicast_ack(IPAddress remoteIP, uint16_t remotePort, uint32_t echoSeq, uint8_t statusCode) {
    sat_v3_ack_pkt_t ackPkt;
    
    ackPkt.signature = SAT_V3_SIGNATURE;
    ackPkt.pkt_type = SAT_V3_PKT_ACK;
    ackPkt.zone_id = MY_ZONE_ID;
    ackPkt.node_id = htons(MY_NODE_ID); // ネットワークバイトオーダーに変換
    ackPkt.echo_seq = htonl(echoSeq);
    ackPkt.status_code = statusCode;
    
    // 自自身の手前までのデータでCRC8を計算
    ackPkt.crc8 = sat_v3_crc8((const uint8_t*)&ackPkt, sizeof(sat_v3_ack_pkt_t) - 1);
    
    // 送信元のIPおよびポートに対してダイレクトに1対1送信(ユニキャスト)
    gUdp.beginPacket(remoteIP, remotePort);
    gUdp.write((const uint8_t*)&ackPkt, sizeof(sat_v3_ack_pkt_t));
    gUdp.endPacket();
    
    Serial.printf("[ACK] Sent back to %s:%d (Seq: %d, Status: 0x%02X)\n", 
                  remoteIP.toString().c_str(), remotePort, echoSeq, statusCode);
}

/**
 * @brief パケット解析・ディスパッチャの拡張
 */
void parse_incoming_packet(const uint8_t *buf, int len) {
    if (len < 8) return; // 最小ヘッダーサイズ未満は破棄
    
    // 1. 署名の検証
    if (buf[0] != SAT_V3_SIGNATURE) return;
    
    uint8_t pktType = buf[1];
    uint8_t flags = buf[5]; // 仕様に基づいたフラグバイトの位置(拡張案配置)
    
    // 仮でヘッダーからシーケンス番号を抽出 (オフセット6〜9バイトと仮定)
    uint32_t receivedSeq = 0;
    memcpy(&receivedSeq, &buf[6], sizeof(uint32_t));
    receivedSeq = ntohl(receivedSeq);

    // 2. パケット種別ごとの描画・制御メイン処理
    switch (pktType) {
        case SAT_V3_PKT_CTRL:
            // 演出切り替え・自律描画処理の実行...
            // process_control_logic(buf, len);
            break;
            
        case SAT_V3_PKT_CONTENT:
            // 歌詞チャンクテキストのレイヤー重畳...
            break;
            
        default:
            return; // 未定義パケットはスキップ
    }

    // 3. 【プランA中核】ACK要求フラグが立っているかどうかの動的判定
    if (flags & SAT_V3_FLAG_REQ_ACK) {
        // HOMEモード判定：マルチキャストパケットの送信元IP/Portを取得し、ACKをユニキャスト返信
        IPAddress centralIP = gUdp.remoteIP();
        uint16_t centralPort = gUdp.remotePort();
        
        // 正常終了(0x00)としてACK返送
        send_unicast_ack(centralIP, centralPort, receivedSeq, 0x00);
    } else {
        // STADIUMモード判定：フラグがゼロなら一切応答せず沈黙(ネットワークパンクを防止)
        // 何もしない
    }
}

void setup() {
    Serial.begin(115200);
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) { delay(500); }
    
    gUdp.begin(localPort);
    // マルチキャストグループに参加 (例: 239.255.0.1)
    WiFi.hostByName("239.255.0.1", IPAddress()); // 必要に応じた初期化
}

void loop() {
    int packetSize = gUdp.parsePacket();
    if (packetSize > 0) {
        uint8_t packetBuffer[512];
        int len = gUdp.read(packetBuffer, 512);
        if (len > 0) {
            parse_incoming_packet(packetBuffer, len);
        }
    }
}
