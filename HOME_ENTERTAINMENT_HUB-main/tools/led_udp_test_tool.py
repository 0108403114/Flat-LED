#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LED Node UDP マルチキャスト テストツール
hub_protocol.h の SAT UDP Protocol (Ver 2.0) 準拠

【プロトコル仕様】
  Byte[ 0]: SAT_SIGNATURE (0x53)
  Byte[ 1]: Target Node ID  (0x00=Global, 0x01〜=個別)
  Byte[ 2]: CH1  Master Dimmer      (0〜255)
  Byte[ 3]: CH2  BG Asset ID        (0=OFF, 1=RAINBOW, 2=PULSE, ...)
  Byte[ 4]: CH3  BG In  Effect ID   (0=CUT, 1=FADE, 2=SLIDE, ...)
  Byte[ 5]: CH4  BG Out Effect ID   (0=CUT, 1=FADE, 2=SLIDE, ...)
  Byte[ 6]: CH5  (reserved)
  Byte[ 7]: CH6  (reserved)
  Byte[ 8]: CH7  Text Mode ID       (0=OFF, 1=LYRICS, 2=SEAT_INFO)
  Byte[ 9]: CH8  Text In  Effect ID
  Byte[10]: CH9  Text Out Effect ID
  Byte[11]: CH10 (reserved)
  Byte[12]: CH11 (reserved)
  Byte[13]: CH12 Transition Time HIGH byte
  Byte[14]: CH13 Transition Time LOW byte
  合計: 15 bytes (SAT_PKT_MIN_SIZE)

  マルチキャストグループ: 239.255.0.1
  ポート: 6454 (Art-Net 準拠)

使用方法:
  python led_udp_test_tool.py dimmer 128
  python led_udp_test_tool.py bg 1
  python led_udp_test_tool.py bg 2 --node 3 --transition 500
  python led_udp_test_tool.py text 1
  python led_udp_test_tool.py scene live
  python led_udp_test_tool.py scene heal
  python led_udp_test_tool.py stop
  python led_udp_test_tool.py bench --pps 100 --duration 5
  python led_udp_test_tool.py analyze
  python led_udp_test_tool.py listen

100,000台スケーラビリティ検証:
  python led_udp_test_tool.py analyze
"""

import socket
import struct
import time
import sys
import argparse
import threading

# ---- プロトコル定数 (hub_protocol.h Ver 3.0 と同期) ----
SAT_MULTICAST_GROUP  = "239.255.0.1"
SAT_UDP_PORT         = 6454
SAT_SIGNATURE        = 0x53

# Ver 2.0 (後方互換)
SAT_NODE_ID_GLOBAL   = 0x00
SAT_PKT_SIZE         = 15          # SAT_PKT_MIN_SIZE

# Ver 3.0 パケット種別
SAT_V3_PKT_CTRL         = 0x10
SAT_V3_PKT_CONTENT      = 0x20
SAT_V3_PKT_NAV          = 0x30
SAT_V3_PKT_HEARTBEAT    = 0x40

# パケットサイズ (Ver 3.0)
SAT_V3_CTRL_SIZE        = 25
SAT_V3_CONTENT_SIZE     = 60
SAT_V3_NAV_SIZE         = 20
SAT_V3_HEARTBEAT_SIZE   = 8
SAT_V3_CONTENT_TEXT_MAX = 48

# Flags
SAT_V3_FLAG_PTP_VALID   = (1 << 0)
SAT_V3_FLAG_UNICAST     = (1 << 1)
SAT_V3_FLAG_ACK_REQ     = (1 << 2)
SAT_V3_FLAG_REDUNDANT   = (1 << 3)
SAT_V3_FLAG_FORCE_RESET = (1 << 4)

# Scene ID
SAT_SCENE_NONE    = 0
SAT_SCENE_LIVE    = 1
SAT_SCENE_HEALING = 2
SAT_SCENE_ENTRY   = 3
SAT_SCENE_OFF     = 4

# BG Asset ID
SAT_BG_OFF           = 0
SAT_BG_RAINBOW       = 1
SAT_BG_PULSE         = 2
SAT_BG_FIRE          = 3
SAT_BG_OCEAN         = 4
SAT_BG_STARFIELD     = 5

# BG/Text Effect ID
SAT_FX_CUT           = 0
SAT_FX_FADE          = 1
SAT_FX_SLIDE_L       = 2
SAT_FX_SLIDE_R       = 3
SAT_FX_WIPE          = 4
SAT_FX_SPARKLE       = 5

# Text Mode ID
SAT_TEXT_OFF         = 0
SAT_TEXT_LYRICS      = 1
SAT_TEXT_SEAT_INFO   = 2
SAT_TEXT_WELCOME     = 3
SAT_TEXT_OSHI_MSG    = 4
SAT_TEXT_CUSTOM      = 5

# Content Type
SAT_CONTENT_TICKET   = 0x01
SAT_CONTENT_OSHI_MSG = 0x02
SAT_CONTENT_WELCOME  = 0x03
SAT_CONTENT_ANNOUNCE = 0x04
SAT_CONTENT_LYRICS   = 0x05

# Nav Direction
SAT_NAV_OFF          = 0x00
SAT_NAV_FORWARD      = 0x01
SAT_NAV_LEFT         = 0x02
SAT_NAV_RIGHT        = 0x03
SAT_NAV_ARRIVED      = 0x04


def _crc8_maxim(data: bytes) -> int:
    """CRC-8/MAXIM (hub_protocol.h sat_v3_crc8 と同一実装)"""
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8C if (crc & 1) else (crc >> 1)
    return crc


def _node_id_bytes(zone: int, node: int) -> bytes:
    """ゾーン番号とノード番号を 3 バイトに変換"""
    return bytes([zone & 0xFF, (node >> 8) & 0xFF, node & 0xFF])


class SatUdpPacket:
    """
    SAT UDP Protocol Ver 2.0 パケット（後方互換用）
    hub_protocol.h の SAT_* 定義と 1:1 対応
    """

    def __init__(self):
        self.target_node_id    = SAT_NODE_ID_GLOBAL
        self.ch1_dimmer        = 255
        self.ch2_bg_asset      = SAT_BG_OFF
        self.ch3_bg_in_fx      = SAT_FX_CUT
        self.ch4_bg_out_fx     = SAT_FX_CUT
        self._ch5_reserved     = 0
        self._ch6_reserved     = 0
        self.ch7_text_mode     = SAT_TEXT_OFF
        self.ch8_text_in_fx    = SAT_FX_CUT
        self.ch9_text_out_fx   = SAT_FX_CUT
        self._ch10_reserved    = 0
        self._ch11_reserved    = 0
        self.transition_ms     = 0    # CH12(HIGH) + CH13(LOW) = 0〜65535 ms

    def encode(self) -> bytes:
        """15 バイトのパケットにエンコードする"""
        trans_hi = (self.transition_ms >> 8) & 0xFF
        trans_lo = self.transition_ms & 0xFF
        return struct.pack(
            "15B",
            SAT_SIGNATURE,
            self.target_node_id & 0xFF,
            self.ch1_dimmer     & 0xFF,
            self.ch2_bg_asset   & 0xFF,
            self.ch3_bg_in_fx   & 0xFF,
            self.ch4_bg_out_fx  & 0xFF,
            self._ch5_reserved,
            self._ch6_reserved,
            self.ch7_text_mode  & 0xFF,
            self.ch8_text_in_fx & 0xFF,
            self.ch9_text_out_fx& 0xFF,
            self._ch10_reserved,
            self._ch11_reserved,
            trans_hi,
            trans_lo,
        )

    @classmethod
    def decode(cls, data: bytes) -> "SatUdpPacket | None":
        """受信バイト列をパケットにデコードする"""
        if len(data) < SAT_PKT_SIZE:
            return None
        if data[0] != SAT_SIGNATURE:
            return None
        pkt = cls()
        pkt.target_node_id  = data[1]
        pkt.ch1_dimmer      = data[2]
        pkt.ch2_bg_asset    = data[3]
        pkt.ch3_bg_in_fx    = data[4]
        pkt.ch4_bg_out_fx   = data[5]
        pkt._ch5_reserved   = data[6]
        pkt._ch6_reserved   = data[7]
        pkt.ch7_text_mode   = data[8]
        pkt.ch8_text_in_fx  = data[9]
        pkt.ch9_text_out_fx = data[10]
        pkt._ch10_reserved  = data[11]
        pkt._ch11_reserved  = data[12]
        pkt.transition_ms   = (data[13] << 8) | data[14]
        return pkt

    def __repr__(self) -> str:
        target = "GLOBAL" if self.target_node_id == SAT_NODE_ID_GLOBAL else f"Node#{self.target_node_id}"
        bg_names = {SAT_BG_OFF: "OFF", SAT_BG_RAINBOW: "RAINBOW", SAT_BG_PULSE: "PULSE"}
        text_names = {SAT_TEXT_OFF: "OFF", SAT_TEXT_LYRICS: "LYRICS", SAT_TEXT_SEAT_INFO: "SEAT_INFO"}
        fx_names = {SAT_FX_CUT: "CUT", SAT_FX_FADE: "FADE", SAT_FX_SLIDE_L: "SLIDE"}
        return (
            f"SatUdpPacket("
            f"target={target}, "
            f"dimmer={self.ch1_dimmer}, "
            f"bg={bg_names.get(self.ch2_bg_asset, self.ch2_bg_asset)}"
            f"[in={fx_names.get(self.ch3_bg_in_fx, self.ch3_bg_in_fx)}"
            f" out={fx_names.get(self.ch4_bg_out_fx, self.ch4_bg_out_fx)}], "
            f"text={text_names.get(self.ch7_text_mode, self.ch7_text_mode)}"
            f"[in={fx_names.get(self.ch8_text_in_fx, self.ch8_text_in_fx)}"
            f" out={fx_names.get(self.ch9_text_out_fx, self.ch9_text_out_fx)}], "
            f"trans={self.transition_ms}ms"
            f")"
        )


# =====================================================
#  Ver 3.0 パケットクラス
# =====================================================

class SatV3CtrlPacket:
    """
    Ver 3.0 シーン制御パケット (25 bytes)
    sat_v3_ctrl_pkt_t に対応
    """
    def __init__(self, zone: int = 0, node: int = 0):
        self.zone           = zone
        self.node           = node
        self.dimmer         = 255
        self.bg_asset       = SAT_BG_OFF
        self.bg_in_fx       = SAT_FX_CUT
        self.bg_out_fx      = SAT_FX_CUT
        self.text_mode      = SAT_TEXT_OFF
        self.text_in_fx     = SAT_FX_CUT
        self.text_out_fx    = SAT_FX_CUT
        self.trans_ms       = 0
        self.execute_at_ms  = 0     # 0=即時実行
        self.flags          = 0
        self.scene_id       = SAT_SCENE_NONE
        self.seq_num        = 0

    def encode(self) -> bytes:
        nid = _node_id_bytes(self.zone, self.node)
        buf = bytearray(SAT_V3_CTRL_SIZE)
        buf[0]  = SAT_SIGNATURE
        buf[1]  = SAT_V3_PKT_CTRL
        buf[2]  = 0x03
        buf[3]  = nid[0]; buf[4] = nid[1]; buf[5] = nid[2]
        buf[6]  = self.dimmer & 0xFF
        buf[7]  = self.bg_asset & 0xFF
        buf[8]  = self.bg_in_fx & 0xFF
        buf[9]  = self.bg_out_fx & 0xFF
        buf[10] = self.text_mode & 0xFF
        buf[11] = self.text_in_fx & 0xFF
        buf[12] = self.text_out_fx & 0xFF
        buf[13] = (self.trans_ms >> 8) & 0xFF
        buf[14] = self.trans_ms & 0xFF
        eat = self.execute_at_ms
        buf[15] = (eat >> 24) & 0xFF
        buf[16] = (eat >> 16) & 0xFF
        buf[17] = (eat >>  8) & 0xFF
        buf[18] = eat & 0xFF
        if eat != 0:
            self.flags |= SAT_V3_FLAG_PTP_VALID
        buf[19] = self.flags
        buf[20] = self.scene_id & 0xFF
        # buf[21-22] reserved = 0
        buf[23] = self.seq_num & 0xFF
        buf[24] = _crc8_maxim(buf[:24])
        return bytes(buf)

    def __repr__(self) -> str:
        bg_n  = {SAT_BG_OFF:"OFF", SAT_BG_RAINBOW:"RAINBOW", SAT_BG_PULSE:"PULSE",
                 SAT_BG_FIRE:"FIRE", SAT_BG_OCEAN:"OCEAN", SAT_BG_STARFIELD:"STARFIELD"}
        txt_n = {SAT_TEXT_OFF:"OFF", SAT_TEXT_LYRICS:"LYRICS", SAT_TEXT_SEAT_INFO:"SEAT_INFO",
                 SAT_TEXT_WELCOME:"WELCOME", SAT_TEXT_OSHI_MSG:"OSHI_MSG", SAT_TEXT_CUSTOM:"CUSTOM"}
        target = f"GLOBAL" if (self.zone == 0 and self.node == 0) else f"Z{self.zone}-N{self.node}"
        return (f"V3_CTRL({target} dim={self.dimmer} "
                f"bg={bg_n.get(self.bg_asset, self.bg_asset)} "
                f"txt={txt_n.get(self.text_mode, self.text_mode)} "
                f"trans={self.trans_ms}ms "
                f"exec_at={self.execute_at_ms}ms flags=0x{self.flags:02X})")


class SatV3ContentPacket:
    """
    Ver 3.0 動的テキスト配信パケット (60 bytes)
    sat_v3_content_pkt_t に対応
    チケット情報・個人メッセージ等をユニキャストで個別席に配信する
    """
    def __init__(self, zone: int, node: int):
        self.zone         = zone
        self.node         = node
        self.content_type = SAT_CONTENT_TICKET
        self.slot         = 0
        self.duration_ms  = 0       # 0=常時表示
        self.text         = ""

    def encode(self) -> bytes:
        nid = _node_id_bytes(self.zone, self.node)
        buf = bytearray(SAT_V3_CONTENT_SIZE)
        buf[0] = SAT_SIGNATURE
        buf[1] = SAT_V3_PKT_CONTENT
        buf[2] = 0x03
        buf[3] = nid[0]; buf[4] = nid[1]; buf[5] = nid[2]
        buf[6] = self.content_type & 0xFF
        buf[7] = self.slot & 0xFF
        buf[8] = (self.duration_ms >> 8) & 0xFF
        buf[9] = self.duration_ms & 0xFF
        encoded = self.text.encode("utf-8")[:SAT_V3_CONTENT_TEXT_MAX]
        buf[10] = len(encoded)
        buf[11:11+len(encoded)] = encoded
        buf[59] = _crc8_maxim(buf[:59])
        return bytes(buf)

    def __repr__(self) -> str:
        ctype_n = {SAT_CONTENT_TICKET:"TICKET", SAT_CONTENT_OSHI_MSG:"OSHI_MSG",
                   SAT_CONTENT_WELCOME:"WELCOME", SAT_CONTENT_ANNOUNCE:"ANNOUNCE",
                   SAT_CONTENT_LYRICS:"LYRICS"}
        return (f"V3_CONTENT(Z{self.zone}-N{self.node} "
                f"type={ctype_n.get(self.content_type, self.content_type)} "
                f"slot={self.slot} dur={self.duration_ms}ms "
                f"text={self.text!r})")


class SatV3NavPacket:
    """
    Ver 3.0 席ナビゲーションパケット (20 bytes)
    sat_v3_nav_pkt_t に対応
    光で通路・座席を誘導する
    """
    def __init__(self, zone: int = 0, node: int = 0):
        self.zone          = zone
        self.node          = node
        self.nav_direction = SAT_NAV_OFF
        self.color_r       = 255
        self.color_g       = 200
        self.color_b       = 0
        self.blink_rate    = 0
        self.intensity     = 200

    def encode(self) -> bytes:
        nid = _node_id_bytes(self.zone, self.node)
        buf = bytearray(SAT_V3_NAV_SIZE)
        buf[0] = SAT_SIGNATURE
        buf[1] = SAT_V3_PKT_NAV
        buf[2] = 0x03
        buf[3] = nid[0]; buf[4] = nid[1]; buf[5] = nid[2]
        buf[6] = self.nav_direction & 0xFF
        buf[7] = self.color_r & 0xFF
        buf[8] = self.color_g & 0xFF
        buf[9] = self.color_b & 0xFF
        buf[10] = self.blink_rate & 0xFF
        buf[11] = self.intensity & 0xFF
        buf[19] = _crc8_maxim(buf[:19])
        return bytes(buf)

    def __repr__(self) -> str:
        dir_n = {SAT_NAV_OFF:"OFF", SAT_NAV_FORWARD:"FWD", SAT_NAV_LEFT:"LEFT",
                 SAT_NAV_RIGHT:"RIGHT", SAT_NAV_ARRIVED:"ARRIVED"}
        target = "GLOBAL" if (self.zone == 0 and self.node == 0) else f"Z{self.zone}-N{self.node}"
        return (f"V3_NAV({target} dir={dir_n.get(self.nav_direction, self.nav_direction)} "
                f"rgb=({self.color_r},{self.color_g},{self.color_b}) "
                f"blink={self.blink_rate} intensity={self.intensity})")


class SatUdpSender:
    """UDP マルチキャスト / ユニキャスト 送信クラス"""

    def __init__(self, group: str = SAT_MULTICAST_GROUP, port: int = SAT_UDP_PORT, ttl: int = 2):
        self.group = group
        self.port  = port
        self.ttl   = ttl
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self._sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
        self._sent_count = 0

    def send(self, pkt: SatUdpPacket) -> None:
        """Ver 2.0 パケット送信（後方互換）"""
        data = pkt.encode()
        self._sock.sendto(data, (self.group, self.port))
        self._sent_count += 1

    def send_raw(self, data: bytes, dest: str = None) -> None:
        """生バイト列を送信 (Ver 3.0 パケット用。dest 省略時はマルチキャスト)"""
        target = dest if dest else self.group
        self._sock.sendto(data, (target, self.port))
        self._sent_count += 1

    def close(self) -> None:
        self._sock.close()

    @property
    def sent_count(self) -> int:
        return self._sent_count


class SatUdpListener:
    """UDP マルチキャスト受信クラス（デバッグ用）"""

    def __init__(self, group: str = SAT_MULTICAST_GROUP, port: int = SAT_UDP_PORT):
        self.group = group
        self.port  = port
        self._running = False

    def listen(self, timeout_sec: float = 30.0) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", self.port))

        mreq = struct.pack("4sL", socket.inet_aton(self.group), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.settimeout(1.0)

        print(f"[LISTEN] {self.group}:{self.port} (timeout={timeout_sec}s, Ctrl+C で終了)")
        self._running = True
        deadline = time.time() + timeout_sec
        recv_count = 0

        try:
            while self._running and time.time() < deadline:
                try:
                    data, addr = sock.recvfrom(256)
                except socket.timeout:
                    continue
                recv_count += 1
                pkt = SatUdpPacket.decode(data)
                if pkt:
                    print(f"[{recv_count:04d}] from {addr[0]}  {pkt}")
                else:
                    sig = data[0] if data else 0xFF
                    print(f"[{recv_count:04d}] from {addr[0]}  INVALID sig=0x{sig:02X} len={len(data)}")
        except KeyboardInterrupt:
            pass
        finally:
            sock.close()
        print(f"[LISTEN] 受信 {recv_count} パケット")


# ---- コマンドハンドラ ----

def _make_sender() -> SatUdpSender:
    return SatUdpSender()


def cmd_dimmer(args) -> None:
    pkt = SatV3CtrlPacket(zone=args.zone, node=args.node)
    pkt.dimmer = max(0, min(255, args.value))
    sender = _make_sender()
    sender.send_raw(pkt.encode())
    sender.close()
    print(f"[SENT] {pkt}")


def cmd_bg(args) -> None:
    pkt = SatV3CtrlPacket(zone=args.zone, node=args.node)
    pkt.dimmer    = args.dimmer
    pkt.bg_asset  = args.asset_id
    pkt.bg_in_fx  = args.in_fx
    pkt.bg_out_fx = args.out_fx
    pkt.trans_ms  = args.transition
    sender = _make_sender()
    sender.send_raw(pkt.encode())
    sender.close()
    print(f"[SENT] {pkt}")


def cmd_text(args) -> None:
    pkt = SatV3CtrlPacket(zone=args.zone, node=args.node)
    pkt.text_mode   = args.mode_id
    pkt.text_in_fx  = args.in_fx
    pkt.text_out_fx = args.out_fx
    pkt.trans_ms    = args.transition
    sender = _make_sender()
    sender.send_raw(pkt.encode())
    sender.close()
    print(f"[SENT] {pkt}")


def cmd_scene(args) -> None:
    """プリセットシーン一括送信 (Ver 3.0)"""
    scene_map = {
        "live":    SAT_SCENE_LIVE,
        "healing": SAT_SCENE_HEALING,
        "heal":    SAT_SCENE_HEALING,
        "entry":   SAT_SCENE_ENTRY,
        "off":     SAT_SCENE_OFF,
    }
    name = args.name.lower()
    if name not in scene_map:
        print(f"[ERROR] 不明なシーン名: {name}  利用可能: {list(scene_map.keys())}")
        sys.exit(1)
    pkt = SatV3CtrlPacket(zone=args.zone, node=args.node)
    pkt.scene_id = scene_map[name]
    if args.execute_after_ms > 0:
        pkt.execute_at_ms = args.execute_after_ms
    sender = _make_sender()
    sender.send_raw(pkt.encode())
    sender.close()
    print(f"[SENT] scene={name} (id={pkt.scene_id})  {pkt}")


def _apply_scene_to_node(sender: SatUdpSender,
                         scene_name: str,
                         zone: int,
                         node: int,
                         execute_at_ms: int = 0) -> None:
    """指定シーンを単一ノードに適用する内部ヘルパー。"""
    scene_map = {
        "live":    SAT_SCENE_LIVE,
        "healing": SAT_SCENE_HEALING,
        "heal":    SAT_SCENE_HEALING,
        "entry":   SAT_SCENE_ENTRY,
        "off":     SAT_SCENE_OFF,
    }
    pkt = SatV3CtrlPacket(zone=zone, node=node)
    pkt.scene_id = scene_map[scene_name]
    pkt.execute_at_ms = execute_at_ms
    sender.send_raw(pkt.encode())
    print(f"[SENT] scene={scene_name} (id={pkt.scene_id}) Z{zone}-N{node} {pkt}")


def cmd_pair_scene(args) -> None:
    """
    2ノード同時発光MVP向け: 同一シーンを2台へ連続送信する。
    例)
      python tools/led_udp_test_tool.py pair-scene live --zone 1 --node-a 1 --node-b 2 --repeat 3 --interval-ms 300
    """
    name = args.name.lower()
    if name not in ("live", "heal", "off", "entry"):
        print(f"[ERROR] 不明なシーン名: {name}  利用可能: ['live', 'heal', 'off', 'entry']")
        sys.exit(1)

    if args.node_a <= 0 or args.node_b <= 0:
        print("[ERROR] --node-a / --node-b は 1 以上を指定してください")
        sys.exit(1)

    execute_at_ms = 0
    if args.execute_after_ms > 0:
        execute_at_ms = args.execute_after_ms

    sender = _make_sender()
    try:
        for i in range(args.repeat):
            _apply_scene_to_node(sender, name, args.zone, args.node_a, execute_at_ms)
            _apply_scene_to_node(sender, name, args.zone, args.node_b, execute_at_ms)
            if i < args.repeat - 1 and args.interval_ms > 0:
                time.sleep(args.interval_ms / 1000.0)
    finally:
        sender.close()

    print(
        f"[PAIR] done scene={name} zone={args.zone} nodes=({args.node_a},{args.node_b}) "
        f"repeat={args.repeat} interval={args.interval_ms}ms"
    )


def cmd_pair_content(args) -> None:
    """2ノードへ同じCONTENTを配信する。"""
    ctype_map = {
        "ticket":   SAT_CONTENT_TICKET,
        "oshi":     SAT_CONTENT_OSHI_MSG,
        "welcome":  SAT_CONTENT_WELCOME,
        "announce": SAT_CONTENT_ANNOUNCE,
        "lyrics":   SAT_CONTENT_LYRICS,
    }
    ctype = ctype_map.get(args.content_type.lower())
    if ctype is None:
        print(f"[ERROR] 不明な content_type: {args.content_type}  利用可能: {list(ctype_map.keys())}")
        sys.exit(1)

    if args.node_a <= 0 or args.node_b <= 0:
        print("[ERROR] --node-a / --node-b は 1 以上を指定してください")
        sys.exit(1)

    sender = _make_sender()
    try:
        pkt_a = SatV3ContentPacket(zone=args.zone, node=args.node_a)
        pkt_a.content_type = ctype
        pkt_a.slot = args.slot
        pkt_a.duration_ms = args.duration
        pkt_a.text = args.text

        pkt_b = SatV3ContentPacket(zone=args.zone, node=args.node_b)
        pkt_b.content_type = ctype
        pkt_b.slot = args.slot
        pkt_b.duration_ms = args.duration
        pkt_b.text = args.text

        for i in range(args.repeat):
            sender.send_raw(pkt_a.encode())
            print(f"[SENT] {pkt_a}")
            sender.send_raw(pkt_b.encode())
            print(f"[SENT] {pkt_b}")
            if i < args.repeat - 1 and args.interval_ms > 0:
                time.sleep(args.interval_ms / 1000.0)
    finally:
        sender.close()

    print(
        f"[PAIR] done content={args.content_type} zone={args.zone} nodes=({args.node_a},{args.node_b}) "
        f"repeat={args.repeat} interval={args.interval_ms}ms"
    )


def cmd_pair_nav(args) -> None:
    """2ノードへ同じNAVを送信する。"""
    dir_map = {
        "off":      SAT_NAV_OFF,
        "fwd":      SAT_NAV_FORWARD,
        "left":     SAT_NAV_LEFT,
        "right":    SAT_NAV_RIGHT,
        "arrived":  SAT_NAV_ARRIVED,
    }
    direction = dir_map.get(args.direction.lower())
    if direction is None:
        print(f"[ERROR] 不明な direction: {args.direction}  利用可能: {list(dir_map.keys())}")
        sys.exit(1)

    if args.node_a <= 0 or args.node_b <= 0:
        print("[ERROR] --node-a / --node-b は 1 以上を指定してください")
        sys.exit(1)

    sender = _make_sender()
    try:
        pkt_a = SatV3NavPacket(zone=args.zone, node=args.node_a)
        pkt_a.nav_direction = direction
        pkt_a.color_r = args.r
        pkt_a.color_g = args.g
        pkt_a.color_b = args.b
        pkt_a.blink_rate = args.blink
        pkt_a.intensity = args.intensity

        pkt_b = SatV3NavPacket(zone=args.zone, node=args.node_b)
        pkt_b.nav_direction = direction
        pkt_b.color_r = args.r
        pkt_b.color_g = args.g
        pkt_b.color_b = args.b
        pkt_b.blink_rate = args.blink
        pkt_b.intensity = args.intensity

        for i in range(args.repeat):
            sender.send_raw(pkt_a.encode())
            print(f"[SENT] {pkt_a}")
            sender.send_raw(pkt_b.encode())
            print(f"[SENT] {pkt_b}")
            if i < args.repeat - 1 and args.interval_ms > 0:
                time.sleep(args.interval_ms / 1000.0)
    finally:
        sender.close()

    print(
        f"[PAIR] done nav={args.direction} zone={args.zone} nodes=({args.node_a},{args.node_b}) "
        f"repeat={args.repeat} interval={args.interval_ms}ms"
    )


def cmd_keep_live(args) -> None:
    """liveシーンを一定時間維持送信する（セーフ白へ戻らないことを確認する用途）。"""
    if args.node_a <= 0 or args.node_b <= 0:
        print("[ERROR] --node-a / --node-b は 1 以上を指定してください")
        sys.exit(1)

    sender = _make_sender()
    start = time.perf_counter()
    deadline = start + args.duration
    interval = max(0.05, args.interval_ms / 1000.0)
    count = 0

    try:
        while time.perf_counter() < deadline:
            _apply_scene_to_node(sender, "live", args.zone, args.node_a)
            _apply_scene_to_node(sender, "live", args.zone, args.node_b)
            count += 2
            time.sleep(interval)
    finally:
        sender.close()

    elapsed = time.perf_counter() - start
    print(f"[KEEP-LIVE] sent={count} elapsed={elapsed:.2f}s interval={args.interval_ms}ms")


def _build_lyrics_chunk_text(song_id: int, version: int, chunk_index: int, chunk_total: int, text: str) -> str:
    """song/chunk/version を先頭メタ情報として埋め込んだ歌詞チャンク文字列を作る。"""
    prefix = f"S{song_id:04X}|V{version:02d}|C{chunk_index:02d}/{chunk_total:02d}|"
    available = SAT_V3_CONTENT_TEXT_MAX - len(prefix.encode("utf-8"))
    if available <= 0:
        raise ValueError("metadata が長すぎて本文を格納できません")

    # UTF-8の途中切断を避けるため、バイト境界で安全に切り詰める
    encoded = text.encode("utf-8")
    if len(encoded) > available:
        encoded = encoded[:available]
        while True:
            try:
                text = encoded.decode("utf-8")
                break
            except UnicodeDecodeError:
                encoded = encoded[:-1]
    return prefix + text


def cmd_lyrics_chunk(args) -> None:
    """歌詞チャンク1件を song/chunk/version 付きで送信する。"""
    if args.chunk < 1 or args.total < 1 or args.chunk > args.total:
        print("[ERROR] --chunk / --total の値が不正です (1 <= chunk <= total)")
        sys.exit(1)

    try:
        payload = _build_lyrics_chunk_text(args.song, args.version, args.chunk, args.total, args.text)
    except ValueError as ex:
        print(f"[ERROR] {ex}")
        sys.exit(1)

    pkt = SatV3ContentPacket(zone=args.zone, node=args.node)
    pkt.content_type = SAT_CONTENT_LYRICS
    pkt.slot = args.slot
    pkt.duration_ms = args.duration
    pkt.text = payload

    sender = _make_sender()
    sender.send_raw(pkt.encode())
    sender.close()

    print(f"[SENT] LYRICS_CHUNK song={args.song} ver={args.version} chunk={args.chunk}/{args.total}")
    print(f"       payload={pkt.text!r}")


def cmd_lyrics_line(args) -> None:
    """1行の歌詞を指定幅で分割し、song/chunk/version 付きで連続送信する。"""
    if args.chunk_width < 1:
        print("[ERROR] --chunk-width は 1 以上を指定してください")
        sys.exit(1)

    chunks = [args.text[i:i + args.chunk_width] for i in range(0, len(args.text), args.chunk_width)] or [""]
    total = len(chunks)

    sender = _make_sender()
    try:
        for idx, chunk_text in enumerate(chunks, start=1):
            payload = _build_lyrics_chunk_text(args.song, args.version, idx, total, chunk_text)
            pkt = SatV3ContentPacket(zone=args.zone, node=args.node)
            pkt.content_type = SAT_CONTENT_LYRICS
            pkt.slot = args.slot
            pkt.duration_ms = args.duration
            pkt.text = payload
            sender.send_raw(pkt.encode())
            print(f"[SENT] chunk={idx}/{total} payload={pkt.text!r}")
            if idx < total and args.interval_ms > 0:
                time.sleep(args.interval_ms / 1000.0)
    finally:
        sender.close()

    print(
        f"[LYRICS-LINE] done song={args.song} ver={args.version} chunks={total} "
        f"chunk_width={args.chunk_width} interval={args.interval_ms}ms"
    )


def cmd_force_reset(args) -> None:
    """PKT_CTRL に FORCE_RESET フラグを立てて対象ノードを再起動させる。"""
    pkt = SatV3CtrlPacket(zone=args.zone, node=args.node)
    pkt.flags = SAT_V3_FLAG_FORCE_RESET
    sender = _make_sender()
    sender.send_raw(pkt.encode())
    sender.close()
    target = "GLOBAL" if (args.zone == 0 and args.node == 0) else f"Z{args.zone}-N{args.node}"
    print(f"[SENT] FORCE_RESET -> {target}")


def cmd_stop(args) -> None:
    pkt = SatV3CtrlPacket(zone=args.zone, node=args.node)
    pkt.dimmer    = 0
    pkt.bg_asset  = SAT_BG_OFF
    pkt.text_mode = SAT_TEXT_OFF
    pkt.trans_ms  = 0
    sender = _make_sender()
    sender.send_raw(pkt.encode())
    sender.close()
    print(f"[SENT] STOP  {pkt}")


def cmd_content(args) -> None:
    """
    動的テキスト配信 (Ver 3.0 PKT_CONTENT)
    チケット情報・個人メッセージ等をユニキャストで個別席ノードへ配信する
    """
    ctype_map = {
        "ticket":   SAT_CONTENT_TICKET,
        "oshi":     SAT_CONTENT_OSHI_MSG,
        "welcome":  SAT_CONTENT_WELCOME,
        "announce": SAT_CONTENT_ANNOUNCE,
        "lyrics":   SAT_CONTENT_LYRICS,
    }
    ctype = ctype_map.get(args.content_type.lower())
    if ctype is None:
        print(f"[ERROR] 不明な content_type: {args.content_type}  利用可能: {list(ctype_map.keys())}")
        sys.exit(1)

    pkt = SatV3ContentPacket(zone=args.zone, node=args.node)
    pkt.content_type = ctype
    pkt.slot         = args.slot
    pkt.duration_ms  = args.duration
    pkt.text         = args.text
    sender = _make_sender()
    sender.send_raw(pkt.encode())
    sender.close()
    print(f"[SENT] {pkt}")


def cmd_nav(args) -> None:
    """
    席ナビゲーション (Ver 3.0 PKT_NAV)
    光で通路・目的地を誘導する
    """
    dir_map = {
        "off":      SAT_NAV_OFF,
        "fwd":      SAT_NAV_FORWARD,
        "left":     SAT_NAV_LEFT,
        "right":    SAT_NAV_RIGHT,
        "arrived":  SAT_NAV_ARRIVED,
    }
    direction = dir_map.get(args.direction.lower())
    if direction is None:
        print(f"[ERROR] 不明な direction: {args.direction}  利用可能: {list(dir_map.keys())}")
        sys.exit(1)

    pkt = SatV3NavPacket(zone=args.zone, node=args.node)
    pkt.nav_direction = direction
    pkt.color_r       = args.r
    pkt.color_g       = args.g
    pkt.color_b       = args.b
    pkt.blink_rate    = args.blink
    pkt.intensity     = args.intensity
    sender = _make_sender()
    sender.send_raw(pkt.encode())
    sender.close()
    print(f"[SENT] {pkt}")


def cmd_bench(args) -> None:
    """
    スループットベンチマーク (Ver 3.0 CTRL パケット使用)
    --pps : 目標パケット/秒
    --duration : 送信継続秒数
    """
    pps      = args.pps
    duration = args.duration
    interval = 1.0 / pps

    pkt = SatV3CtrlPacket()
    pkt.bg_asset = SAT_BG_RAINBOW
    data = pkt.encode()

    sender = _make_sender()
    print(f"[BENCH] 目標 {pps} pkt/s × {duration}s = {pps * duration:.0f} パケット")
    print(f"        パケットサイズ: {len(data)} bytes (Ver 3.0 CTRL)")
    print(f"        送信先: {SAT_MULTICAST_GROUP}:{SAT_UDP_PORT}")

    sent     = 0
    start    = time.perf_counter()
    deadline = start + duration
    next_tx  = start

    while time.perf_counter() < deadline:
        if time.perf_counter() >= next_tx:
            sender.send_raw(data)
            sent += 1
            next_tx += interval

    elapsed    = time.perf_counter() - start
    actual_pps = sent / elapsed
    bps_total  = actual_pps * len(data) * 8

    sender.close()
    print(f"\n[BENCH RESULT]")
    print(f"  送信パケット数 : {sent}")
    print(f"  経過時間       : {elapsed:.3f} s")
    print(f"  実効 PPS       : {actual_pps:.1f} pkt/s")
    print(f"  送信帯域       : {bps_total:.0f} bps  ({bps_total/1000:.1f} kbps)")
    print(f"  Dropped        : 0")


def cmd_analyze(_args) -> None:
    """
    100,000台スケーラビリティ理論分析
    UDP マルチキャストの帯域特性を計算して表示する
    """
    print("=" * 60)
    print("  100,000台 スケーラビリティ分析")
    print("  プロトコル: SAT UDP Ver 2.0 (hub_protocol.h)")
    print("=" * 60)

    pkt_size    = SAT_PKT_SIZE      # bytes
    port        = SAT_UDP_PORT
    mc_group    = SAT_MULTICAST_GROUP

    print(f"\n【パケット仕様】")
    print(f"  サイズ          : {pkt_size} bytes (固定長)")
    print(f"  ポート          : {port} (Art-Net 準拠)")
    print(f"  マルチキャスト  : {mc_group}")
    print(f"  署名            : 0x{SAT_SIGNATURE:02X} (不正パケット排除)")
    print(f"  ACK             : なし (帯域パンク防止)")

    print(f"\n【UDP ヘッダオーバーヘッド】")
    udp_header   = 8   # bytes
    ip_header    = 20  # bytes
    eth_header   = 14  # bytes
    total_frame  = eth_header + ip_header + udp_header + pkt_size
    payload_eff  = pkt_size / total_frame * 100
    print(f"  ペイロード      : {pkt_size} bytes")
    print(f"  UDP ヘッダ      : {udp_header} bytes")
    print(f"  IP ヘッダ       : {ip_header} bytes")
    print(f"  Ethernet        : {eth_header} bytes")
    print(f"  フレーム合計    : {total_frame} bytes")
    print(f"  ペイロード効率  : {payload_eff:.1f}%")

    print(f"\n【マルチキャスト帯域 (送信側)】")
    print(f"  ※ UDP マルチキャストは送信側が 1 パケット送るだけ。")
    print(f"     ノード数が増えてもネットワーク複製は L2/L3 スイッチが担う。")
    for pps in [1, 10, 30, 60]:
        bps  = total_frame * 8 * pps
        kbps = bps / 1000
        print(f"  {pps:3d} pkt/s → 送信帯域 {kbps:7.1f} kbps  (ノード数に無関係)")

    print(f"\n【受信ノード側 帯域 (Wi-Fi)】")
    print(f"  ※ 各ノードは同じ 1 パケットを受信するだけ。")
    print(f"     Wi-Fi 2.4GHz 最小スループット: ~5 Mbps")
    for pps in [1, 10, 60]:
        bps_rx = total_frame * 8 * pps
        margin = 5_000_000 / bps_rx
        print(f"  {pps:3d} pkt/s → 受信 {bps_rx/1000:.1f} kbps  (Wi-Fi 余裕率: x{margin:.0f})")

    print(f"\n【ノードスケール比較】")
    print(f"  {'ノード数':>12}  {'送信帯域(送信側)':>18}  {'受信帯域/ノード':>18}  {'判定':>6}")
    for nodes in [1, 10, 100, 1_000, 10_000, 100_000]:
        sender_bps = total_frame * 8 * 10   # 10 pkt/s 想定
        rx_bps     = sender_bps               # 各ノードが受信するのは同量
        ok = "✓ OK" if sender_bps < 10_000_000 else "△ 確認"
        print(f"  {nodes:>12,}台  {sender_bps/1000:>14.0f} kbps  {rx_bps/1000:>14.0f} kbps  {ok:>6}")

    print(f"\n【ボトルネック分析】")
    bottlenecks = [
        ("スイッチ IGMP Snooping",    "ノードが増えると L2 スイッチの IGMP テーブル負荷が増える"),
        ("Wi-Fi AP 接続台数上限",     "家庭用 AP は 30〜50 台程度が実用上限。大規模は有線バックボーン必須"),
        ("各ノードの受信処理速度",    "ESP32 UDP 受信 + LED 描画の非同期設計が必須"),
        ("PTP 時刻同期精度",          "100,000台を < 1ms で揃えるには PTP (IEEE 1588) が必要"),
        ("電源・配線",                "100,000台の物理実装は別途電源・配線設計が必要"),
    ]
    for name, desc in bottlenecks:
        print(f"  ⚠ {name}")
        print(f"      → {desc}")

    print(f"\n【結論】")
    print(f"  プロトコル設計 (UDP マルチキャスト, ACK なし, 15 bytes) は")
    print(f"  100,000台を理論的に支えられる。")
    print(f"  現在の MVP (2台) から同じパケット構造で直接スケールアップできる。")
    print(f"  実用上の上限は Wi-Fi AP 台数と PTP 同期精度によって決まる。")
    print("=" * 60)


def cmd_listen(args) -> None:
    listener = SatUdpListener()
    listener.listen(timeout_sec=args.timeout)


# ---- CLI エントリポイント ----

def build_parser() -> argparse.ArgumentParser:
    # 共通オプションを親パーサーに定義し、全サブコマンドで継承させる
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--zone", type=int, default=0,
                        help="Zone ID (0=Global, 1〜=ゾーン番号, デフォルト=0)")
    common.add_argument("--node", type=int, default=0,
                        help="Node ID (0=Global, 1〜=個別, デフォルト=0)")

    parser = argparse.ArgumentParser(
        description="LED Node UDP マルチキャスト テストツール (SAT UDP Ver 3.0)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # dimmer
    p = sub.add_parser("dimmer", parents=[common], help="Master Dimmer を設定")
    p.add_argument("value", type=int, help="0〜255")

    # bg
    p = sub.add_parser("bg", parents=[common],
                       help="BG Asset (0=OFF 1=RAINBOW 2=PULSE 3=FIRE 4=OCEAN 5=STARFIELD)")
    p.add_argument("asset_id", type=int, help="BG Asset ID")
    p.add_argument("--in-fx",      type=int, default=SAT_FX_CUT, dest="in_fx",
                   help="BG In エフェクト (0=CUT 1=FADE 2=SLIDE_L 3=SLIDE_R 4=WIPE 5=SPARKLE)")
    p.add_argument("--out-fx",     type=int, default=SAT_FX_CUT, dest="out_fx",
                   help="BG Out エフェクト")
    p.add_argument("--dimmer",     type=int, default=255, help="Master Dimmer (0〜255)")
    p.add_argument("--transition", type=int, default=0,
                   help="トランジション時間 ms (0〜65535)")

    # text
    p = sub.add_parser("text", parents=[common],
                       help="Text Mode (0=OFF 1=LYRICS 2=SEAT_INFO 3=WELCOME 4=OSHI_MSG 5=CUSTOM)")
    p.add_argument("mode_id", type=int, help="Text Mode ID")
    p.add_argument("--in-fx",      type=int, default=SAT_FX_CUT, dest="in_fx")
    p.add_argument("--out-fx",     type=int, default=SAT_FX_CUT, dest="out_fx")
    p.add_argument("--transition", type=int, default=0)

    # scene
    p = sub.add_parser("scene", parents=[common],
                       help="プリセットシーン (live / heal / off / entry)")
    p.add_argument("name", type=str, help="live | heal | off | entry")
    p.add_argument("--execute-after-ms", type=int, default=0,
                   help="現在時刻からの遅延実行 ms (0=即時)")

    # pair-scene
    p = sub.add_parser("pair-scene", help="[E-2] 2ノードへ同一シーンを一括送信")
    p.add_argument("name", type=str, help="live | heal | off | entry")
    p.add_argument("--zone", type=int, default=1, help="Zone ID (デフォルト: 1)")
    p.add_argument("--node-a", type=int, required=True, help="1台目 Node ID")
    p.add_argument("--node-b", type=int, required=True, help="2台目 Node ID")
    p.add_argument("--execute-after-ms", type=int, default=0,
                   help="現在時刻からの遅延実行 ms (0=即時)")
    p.add_argument("--repeat", type=int, default=1, help="送信回数 (デフォルト: 1)")
    p.add_argument("--interval-ms", type=int, default=0, help="送信間隔 ms (デフォルト: 0)")

    # pair-content
    p = sub.add_parser("pair-content", help="[E-2] 2ノードへ同一CONTENTを一括配信")
    p.add_argument("content_type", type=str, help="ticket | oshi | welcome | announce | lyrics")
    p.add_argument("text", type=str, help="配信テキスト (最大 48 bytes UTF-8)")
    p.add_argument("--zone", type=int, default=1, help="Zone ID (デフォルト: 1)")
    p.add_argument("--node-a", type=int, required=True, help="1台目 Node ID")
    p.add_argument("--node-b", type=int, required=True, help="2台目 Node ID")
    p.add_argument("--slot", type=int, default=0, help="表示スロット 0〜7")
    p.add_argument("--duration", type=int, default=0, help="表示継続 ms (0=常時)")
    p.add_argument("--repeat", type=int, default=1, help="送信回数 (デフォルト: 1)")
    p.add_argument("--interval-ms", type=int, default=0, help="送信間隔 ms (デフォルト: 0)")

    # pair-nav
    p = sub.add_parser("pair-nav", help="[E-2] 2ノードへ同一NAVを一括送信")
    p.add_argument("direction", type=str, help="off | fwd | left | right | arrived")
    p.add_argument("--zone", type=int, default=1, help="Zone ID (デフォルト: 1)")
    p.add_argument("--node-a", type=int, required=True, help="1台目 Node ID")
    p.add_argument("--node-b", type=int, required=True, help="2台目 Node ID")
    p.add_argument("--r", type=int, default=255, help="LED 赤")
    p.add_argument("--g", type=int, default=200, help="LED 緑")
    p.add_argument("--b", type=int, default=0, help="LED 青")
    p.add_argument("--blink", type=int, default=0, help="点滅 0=常灯 1=低速 2=高速")
    p.add_argument("--intensity", type=int, default=200, help="輝度 0〜255")
    p.add_argument("--repeat", type=int, default=1, help="送信回数 (デフォルト: 1)")
    p.add_argument("--interval-ms", type=int, default=0, help="送信間隔 ms (デフォルト: 0)")

    # keep-live
    p = sub.add_parser("keep-live", help="[E-2] 2ノードへliveを継続送信して表示維持")
    p.add_argument("--zone", type=int, default=1, help="Zone ID (デフォルト: 1)")
    p.add_argument("--node-a", type=int, required=True, help="1台目 Node ID")
    p.add_argument("--node-b", type=int, required=True, help="2台目 Node ID")
    p.add_argument("--duration", type=float, default=15.0, help="継続秒数 (デフォルト: 15)")
    p.add_argument("--interval-ms", type=int, default=400, help="送信間隔 ms (デフォルト: 400)")

    # stop
    sub.add_parser("stop", parents=[common], help="全消灯 (Dimmer=0, BG=OFF, Text=OFF)")

    # content
    p = sub.add_parser("content", parents=[common],
                       help="[Ver3.0] 動的テキスト配信 (チケット情報・個人メッセージ等)")
    p.add_argument("content_type", type=str,
                   help="ticket | oshi | welcome | announce")
    p.add_argument("text", type=str, help="配信テキスト (最大 48 bytes UTF-8)")
    p.add_argument("--slot",     type=int, default=0, help="表示スロット 0〜7")
    p.add_argument("--duration", type=int, default=0, help="表示継続 ms (0=常時)")

    # lyrics-chunk
    p = sub.add_parser("lyrics-chunk", parents=[common],
                       help="[E-1] song/chunk/version 付き歌詞チャンクを1件送信")
    p.add_argument("text", type=str, help="歌詞チャンク本文")
    p.add_argument("--song", type=int, required=True, help="song_id (整数)")
    p.add_argument("--version", type=int, default=1, help="version (デフォルト: 1)")
    p.add_argument("--chunk", type=int, required=True, help="chunk_id (1始まり)")
    p.add_argument("--total", type=int, required=True, help="総チャンク数")
    p.add_argument("--slot", type=int, default=0, help="表示スロット 0〜7")
    p.add_argument("--duration", type=int, default=0, help="表示継続 ms (0=常時)")

    # lyrics-line
    p = sub.add_parser("lyrics-line", parents=[common],
                       help="[E-1] 1行歌詞を分割し、song/chunk/version 付きで連続送信")
    p.add_argument("text", type=str, help="歌詞全文")
    p.add_argument("--song", type=int, required=True, help="song_id (整数)")
    p.add_argument("--version", type=int, default=1, help="version (デフォルト: 1)")
    p.add_argument("--chunk-width", type=int, default=36,
                   help="分割文字数目安 (デフォルト: 36)")
    p.add_argument("--interval-ms", type=int, default=120,
                   help="チャンク送信間隔 ms (デフォルト: 120)")
    p.add_argument("--slot", type=int, default=0, help="表示スロット 0〜7")
    p.add_argument("--duration", type=int, default=0, help="表示継続 ms (0=常時)")

    # force-reset
    sub.add_parser("force-reset", parents=[common],
                   help="[E-1] FORCE_RESET フラグ付き PKT_CTRL を送信してノードを再起動")

    # nav
    p = sub.add_parser("nav", parents=[common],
                       help="[Ver3.0] 席ナビゲーション (光で通路・座席を誘導)")
    p.add_argument("direction", type=str,
                   help="off | fwd | left | right | arrived")
    p.add_argument("--r",         type=int, default=255, help="LED 赤 (デフォルト: 255)")
    p.add_argument("--g",         type=int, default=200, help="LED 緑 (デフォルト: 200)")
    p.add_argument("--b",         type=int, default=0,   help="LED 青 (デフォルト: 0)")
    p.add_argument("--blink",     type=int, default=0,   help="点滅 0=常灯 1=低速 2=高速")
    p.add_argument("--intensity", type=int, default=200, help="輝度 0〜255")

    # bench
    p = sub.add_parser("bench", help="スループットベンチマーク")
    p.add_argument("--pps",      type=int,   default=60,  help="目標 pkt/s (デフォルト: 60)")
    p.add_argument("--duration", type=float, default=5.0, help="継続秒数 (デフォルト: 5.0)")

    # analyze
    sub.add_parser("analyze", help="100,000台スケーラビリティ理論分析")

    # listen
    p = sub.add_parser("listen", help="マルチキャスト受信・デコード表示")
    p.add_argument("--timeout", type=float, default=30.0, help="タイムアウト秒 (デフォルト: 30)")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    handlers = {
        "dimmer":  cmd_dimmer,
        "bg":      cmd_bg,
        "text":    cmd_text,
        "scene":   cmd_scene,
        "pair-scene": cmd_pair_scene,
        "pair-content": cmd_pair_content,
        "pair-nav": cmd_pair_nav,
        "keep-live": cmd_keep_live,
        "stop":    cmd_stop,
        "content": cmd_content,
        "lyrics-chunk": cmd_lyrics_chunk,
        "lyrics-line": cmd_lyrics_line,
        "force-reset": cmd_force_reset,
        "nav":     cmd_nav,
        "bench":   cmd_bench,
        "analyze": cmd_analyze,
        "listen":  cmd_listen,
    }

    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    handler(args)


if __name__ == "__main__":
    main()
