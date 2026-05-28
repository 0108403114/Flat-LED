"""
td_sat_sender.py
================
TouchDesigner から SAT UDP Ver 3.0 プロトコルでサテライト LED ノードを制御するモジュール。

【TD での使い方 (Script DAT)】
  import sys
  sys.path.insert(0, 'C:/Projects/02_HomeLiveHall_Trial01/tools')
  import td_sat_sender as sat

  # 起動時に一度だけコントローラを作成
  ctrl = sat.TdLedController()

  # シーン切替
  ctrl.send_scene('LIVE')      # FIRE + 歌詞テキスト
  ctrl.send_scene('HEALING')   # OCEAN
  ctrl.send_scene('ENTRY')     # STARFIELD
  ctrl.send_scene('OFF')       # 消灯

  # BG / Dimmer を個別指定
  ctrl.send_ctrl(bg='FIRE', dimmer=200, trans_ms=500)

  # ハートビート (3秒以内に 1 回送らないとセーフ白に遷移)
  ctrl.send_heartbeat()

  # 歌詞テキスト送信 (14文字以内推奨)
  ctrl.send_lyrics_line('Hello World')

  # 後始末
  ctrl.close()

【ハートビートについて】
  ESP32 は最後のハートビートから 3 秒間信号が来ないとセーフ白に遷移します。
  TD の Timer CHOP (周期 1.5秒) + Execute DAT で ctrl.send_heartbeat() を
  定期呼び出しする必要があります。
"""

import socket
import struct
import threading
import time
import re

# ============================================================
#  プロトコル定数 (hub_protocol.h / led_udp_test_tool.py と同期)
# ============================================================
MCAST_GROUP  = "239.255.0.1"
UDP_PORT     = 6454
SIGNATURE    = 0x53

PKT_CTRL      = 0x10
PKT_CONTENT   = 0x20
PKT_HEARTBEAT = 0x40

CTRL_SIZE      = 25
CONTENT_SIZE   = 60
HEARTBEAT_SIZE = 8
CONTENT_TEXT_MAX = 48

FLAG_PTP_VALID   = (1 << 0)
FLAG_REDUNDANT   = (1 << 3)
FLAG_FORCE_RESET = (1 << 4)

SCENE_NONE    = 0
SCENE_LIVE    = 1
SCENE_HEALING = 2
SCENE_ENTRY   = 3
SCENE_OFF     = 4
SCENE_READY   = 5
SCENE_EVENT_1 = 6
SCENE_EVENT_2 = 7
SCENE_EVENT_3 = 8
SCENE_FIREWORKS = 9

BG_OFF      = 0
BG_RAINBOW  = 1
BG_PULSE    = 2
BG_FIRE     = 3
BG_OCEAN    = 4
BG_STARFIELD = 5
BG_FIREWORKS_LOCAL = 6

TEXT_OFF     = 0
TEXT_LYRICS  = 1
TEXT_CUSTOM  = 5

FX_CUT  = 0
FX_FADE = 1
FX_SLIDE_L = 2
FX_SLIDE_R = 3
FX_WIPE = 4
FX_SPARKLE = 5

FX_MAP = {
    'CUT': FX_CUT,
    'FADE': FX_FADE,
    'SLIDE_L': FX_SLIDE_L,
    'SLIDE_R': FX_SLIDE_R,
    'WIPE': FX_WIPE,
    'SPARKLE': FX_SPARKLE,
}

CONTENT_LYRICS = 0x05

SCENE_MAP = {
    'LIVE':    SCENE_LIVE,
    'HEALING': SCENE_HEALING,
    'ENTRY':   SCENE_ENTRY,
    'OFF':     SCENE_OFF,
    'READY':   SCENE_READY,
    'EVENT_1': SCENE_EVENT_1,
    'EVENT_2': SCENE_EVENT_2,
    'EVENT_3': SCENE_EVENT_3,
    'FIREWORKS': SCENE_FIREWORKS,
    'NONE':    SCENE_NONE,
}

BG_MAP = {
    'OFF':      BG_OFF,
    'RAINBOW':  BG_RAINBOW,
    'PULSE':    BG_PULSE,
    'FIRE':     BG_FIRE,
    'OCEAN':    BG_OCEAN,
    'STARFIELD': BG_STARFIELD,
    'FIREWORKS_LOCAL': BG_FIREWORKS_LOCAL,
}

TEXT_MAP = {
    'OFF':    TEXT_OFF,
    'LYRICS': TEXT_LYRICS,
    'CUSTOM': TEXT_CUSTOM,
}

_TS_BRACKET_RE = re.compile(r"^\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]\s*(.*)$")
_TS_PIPE_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*\|\s*(.*)$")

# ============================================================
#  CRC-8/MAXIM
# ============================================================
def _crc8(data: bytes) -> int:
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8C if (crc & 1) else (crc >> 1)
    return crc


def _nid(zone: int, node: int) -> bytes:
    """Zone/Node を 3 バイトに変換"""
    return bytes([zone & 0xFF, (node >> 8) & 0xFF, node & 0xFF])


# ============================================================
#  パケット構築
# ============================================================
_seq = 0

def _next_seq() -> int:
    global _seq
    _seq = (_seq + 1) & 0xFF
    return _seq


def build_ctrl(zone: int = 0, node: int = 0,
               dimmer: int = 255,
               bg: int = BG_OFF,
               text_mode: int = TEXT_OFF,
               bg_in_fx: int = FX_CUT,
               bg_out_fx: int = FX_CUT,
               text_in_fx: int = FX_CUT,
               text_out_fx: int = FX_CUT,
               trans_ms: int = 0,
               scene_id: int = SCENE_NONE,
               execute_at_ms: int = 0,
               flags: int = 0) -> bytes:
    """
    CTRL パケット (25 bytes) を構築して返す。
    zone=0, node=0 はグローバルブロードキャスト。
    """
    nid = _nid(zone, node)
    buf = bytearray(CTRL_SIZE)
    buf[0]  = SIGNATURE
    buf[1]  = PKT_CTRL
    buf[2]  = 0x03          # protocol version
    buf[3]  = nid[0]; buf[4] = nid[1]; buf[5] = nid[2]
    buf[6]  = dimmer & 0xFF
    buf[7]  = bg & 0xFF
    buf[8]  = bg_in_fx & 0xFF
    buf[9]  = bg_out_fx & 0xFF
    buf[10] = text_mode & 0xFF
    buf[11] = text_in_fx & 0xFF
    buf[12] = text_out_fx & 0xFF
    buf[13] = (trans_ms >> 8) & 0xFF
    buf[14] = trans_ms & 0xFF
    buf[15] = (execute_at_ms >> 24) & 0xFF
    buf[16] = (execute_at_ms >> 16) & 0xFF
    buf[17] = (execute_at_ms >>  8) & 0xFF
    buf[18] = execute_at_ms & 0xFF
    if execute_at_ms != 0:
        flags |= FLAG_PTP_VALID
    buf[19] = flags & 0xFF
    buf[20] = scene_id & 0xFF
    buf[21] = 0; buf[22] = 0  # reserved
    buf[23] = _next_seq()
    buf[24] = _crc8(buf[:24])
    return bytes(buf)


def build_heartbeat() -> bytes:
    """HEARTBEAT パケット (8 bytes) を構築して返す。"""
    buf = bytearray(HEARTBEAT_SIZE)
    buf[0] = SIGNATURE
    buf[1] = PKT_HEARTBEAT
    buf[2] = 0x03
    # buf[3-6] timestamp (省略、0 で OK)
    buf[7] = _crc8(buf[:7])
    return bytes(buf)


def build_lyrics(text: str,
                 zone: int = 0, node: int = 0,
                 song_id: int = 1, version: int = 1) -> bytes:
    """
    歌詞 1 行を 1 チャンクの CONTENT パケットとして構築する。
    14 文字以内の ASCII テキストを想定。
    """
    # フォーマット: S{4hex}|V{2dec}|C{2dec}/{2dec}|{text}
    payload = f"S{song_id:04X}|V{version:02d}|C01/01|{text}"
    encoded = payload.encode('ascii', errors='replace')[:CONTENT_TEXT_MAX]

    nid = _nid(zone, node)
    buf = bytearray(CONTENT_SIZE)
    buf[0] = SIGNATURE
    buf[1] = PKT_CONTENT
    buf[2] = 0x03
    buf[3] = nid[0]; buf[4] = nid[1]; buf[5] = nid[2]
    buf[6] = CONTENT_LYRICS
    buf[7] = 0      # slot
    buf[8] = 0; buf[9] = 0   # duration_ms (0=常時)
    buf[10] = len(encoded)
    buf[11:11+len(encoded)] = encoded
    buf[59] = _crc8(buf[:59])
    return bytes(buf)


def build_content_custom(text: str,
                        zone: int = 0, node: int = 0,
                        content_type: int = 0x00) -> bytes:
    """
    カスタムテキスト（Welcome/Thanks など）を CONTENT パケットとして構築する。
    text: 最大 48 文字の ASCII テキスト
    content_type: 0x00=CUSTOM, 0x05=LYRICS など
    """
    encoded = text.encode('ascii', errors='replace')[:CONTENT_TEXT_MAX]

    nid = _nid(zone, node)
    buf = bytearray(CONTENT_SIZE)
    buf[0] = SIGNATURE
    buf[1] = PKT_CONTENT
    buf[2] = 0x03
    buf[3] = nid[0]; buf[4] = nid[1]; buf[5] = nid[2]
    buf[6] = content_type & 0xFF
    buf[7] = 0      # slot
    buf[8] = 0; buf[9] = 0   # duration_ms (0=常時)
    buf[10] = len(encoded)
    buf[11:11+len(encoded)] = encoded
    buf[59] = _crc8(buf[:59])
    return bytes(buf)


def _split_ascii_chunks(text: str, max_chunk_len: int) -> list[str]:
    cleaned = (text or "").strip()
    if not cleaned:
        return [""]
    replaced = cleaned.encode("ascii", errors="replace").decode("ascii")
    return [replaced[i:i + max_chunk_len] for i in range(0, len(replaced), max_chunk_len)]


def build_lyrics_chunks(text: str,
                       zone: int = 0, node: int = 0,
                       song_id: int = 1, version: int = 1) -> list[bytes]:
    """1行テキストを Cxx/tt 形式の複数チャンクへ分割して返す。"""
    # payload: S{4hex}|V{2dec}|C{2dec}/{2dec}|{chunk}
    # 先頭メタデータ分を引いた残りを本文に使う
    meta_len = len(f"S{song_id:04X}|V{version:02d}|C01/01|")
    max_chunk_len = max(1, CONTENT_TEXT_MAX - meta_len)
    chunks = _split_ascii_chunks(text, max_chunk_len)
    total = len(chunks)
    packets = []

    nid = _nid(zone, node)
    for idx, chunk in enumerate(chunks, start=1):
        payload = f"S{song_id:04X}|V{version:02d}|C{idx:02d}/{total:02d}|{chunk}"
        encoded = payload.encode("ascii", errors="replace")[:CONTENT_TEXT_MAX]

        buf = bytearray(CONTENT_SIZE)
        buf[0] = SIGNATURE
        buf[1] = PKT_CONTENT
        buf[2] = 0x03
        buf[3] = nid[0]; buf[4] = nid[1]; buf[5] = nid[2]
        buf[6] = CONTENT_LYRICS
        buf[7] = 0
        buf[8] = 0; buf[9] = 0
        buf[10] = len(encoded)
        buf[11:11+len(encoded)] = encoded
        buf[59] = _crc8(buf[:59])
        packets.append(bytes(buf))

    return packets


def _parse_timestamped_line(line: str):
    m = _TS_BRACKET_RE.match(line)
    if m:
        mm = int(m.group(1))
        ss = int(m.group(2))
        frac = m.group(3) or "0"
        frac_s = float(f"0.{frac}")
        return (mm * 60 + ss + frac_s, m.group(4).strip())

    m2 = _TS_PIPE_RE.match(line)
    if m2:
        return (float(m2.group(1)), m2.group(2).strip())

    return None


def parse_lyrics_file(file_path: str,
                     interval_s: float = 2.0,
                     timed: bool = True) -> list[tuple[float, str]]:
    """歌詞ファイルを読み取り、(offset_sec, text) の配列へ変換する。"""
    events = []
    plain_lines = []

    with open(file_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parsed = _parse_timestamped_line(line) if timed else None
            if parsed:
                offset, text = parsed
                if text:
                    events.append((max(0.0, float(offset)), text))
            else:
                plain_lines.append(line)

    if events:
        events.sort(key=lambda x: x[0])
        return events

    for i, text in enumerate(plain_lines):
        events.append((i * max(0.1, float(interval_s)), text))
    return events


def play_lyrics_events(ctrl,
                      events: list[tuple[float, str]],
                      song_id: int = 1,
                      version: int = 1,
                      zone: int = 0,
                      node: int = 0,
                      start_delay_s: float = 0.0,
                      chunked: bool = True,
                      stop_flag_getter=None):
    """(offset, text) イベント列を時刻制御で順次送信する。"""
    start_at = time.time() + max(0.0, float(start_delay_s))
    for offset, text in events:
        if stop_flag_getter and stop_flag_getter():
            return
        target = start_at + max(0.0, float(offset))
        while True:
            if stop_flag_getter and stop_flag_getter():
                return
            now = time.time()
            remain = target - now
            if remain <= 0:
                break
            time.sleep(min(0.05, remain))
        if chunked and hasattr(ctrl, 'send_lyrics_chunks'):
            ctrl.send_lyrics_chunks(text, song_id=song_id, version=version, zone=zone, node=node)
        else:
            ctrl.send_lyrics_line(text, song_id=song_id, version=version, zone=zone, node=node)


# ============================================================
#  コントローラクラス
# ============================================================
class TdLedController:
    """
    TouchDesigner から使う LED コントローラ。

    使用例:
        ctrl = TdLedController()
        ctrl.send_scene('LIVE')
        ctrl.send_heartbeat()  # 1.5 秒ごとに呼ぶ
        ctrl.close()

    zone=0, node=0 はグローバル（全ノード一斉制御）。
    特定ノードだけ操作したい場合は zone/node を指定する。
    """

    def __init__(self,
                 group: str = MCAST_GROUP,
                 port: int = UDP_PORT,
                 ttl: int = 2,
                 monitor: bool = False):
        self._group = group
        self._port  = port
        self._monitor = monitor
        self._sock  = socket.socket(socket.AF_INET,
                                    socket.SOCK_DGRAM,
                                    socket.IPPROTO_UDP)
        self._sock.setsockopt(socket.IPPROTO_IP,
                              socket.IP_MULTICAST_TTL, ttl)
        print(f"[TdLedController] ready  {group}:{port}")

    # ----------------------------------------------------------
    def _send(self, data: bytes) -> None:
        self._sock.sendto(data, (self._group, self._port))

    # ----------------------------------------------------------
    def _log_send(self, kind: str, detail: str) -> None:
        if self._monitor:
            stamp = time.strftime('%H:%M:%S')
            print(f"[TD SEND {stamp}] {kind}: {detail}")

    # ----------------------------------------------------------
    def send_scene(self, scene_name: str,
                   zone: int = 0, node: int = 0) -> None:
        """
        シーンプリセットを送信する。
        scene_name: 'LIVE' / 'HEALING' / 'ENTRY' / 'OFF'
        """
        sid = SCENE_MAP.get(scene_name.upper())
        if sid is None:
            print(f"[TdLedController] unknown scene '{scene_name}'")
            return
        pkt = build_ctrl(zone=zone, node=node, scene_id=sid)
        self._send(pkt)
        self._log_send('CTRL', f'scene={scene_name} Z{zone}N{node}')
        print(f"[TdLedController] scene={scene_name} Z{zone}N{node}")

    # ----------------------------------------------------------
    def send_ctrl(self,
                  bg: str = 'OFF',
                  dimmer: int = 255,
                  text_mode: str = 'OFF',
                  bg_in_fx: str = 'CUT',
                  bg_out_fx: str = 'CUT',
                  text_in_fx: str = 'CUT',
                  text_out_fx: str = 'CUT',
                  trans_ms: int = 0,
                  zone: int = 0, node: int = 0) -> None:
        """
        BG アセット / 輝度 / テキストモードを個別に指定して送信する。
        bg:        'OFF' / 'FIRE' / 'OCEAN' / 'STARFIELD' / 'RAINBOW' / 'PULSE'
        text_mode: 'OFF' / 'LYRICS' / 'CUSTOM'
        *_fx:      'CUT' / 'FADE' / 'SLIDE_L' / 'SLIDE_R' / 'WIPE' / 'SPARKLE'
        dimmer:    0〜255
        trans_ms:  フェード時間 (ms)
        """
        bg_id = BG_MAP.get(bg.upper(), BG_OFF)
        txt_id = TEXT_MAP.get(text_mode.upper(), TEXT_OFF)
        bg_in_id = FX_MAP.get(bg_in_fx.upper(), FX_CUT)
        bg_out_id = FX_MAP.get(bg_out_fx.upper(), FX_CUT)
        text_in_id = FX_MAP.get(text_in_fx.upper(), FX_CUT)
        text_out_id = FX_MAP.get(text_out_fx.upper(), FX_CUT)
        pkt = build_ctrl(
            zone=zone,
            node=node,
            dimmer=dimmer,
            bg=bg_id,
            text_mode=txt_id,
            bg_in_fx=bg_in_id,
            bg_out_fx=bg_out_id,
            text_in_fx=text_in_id,
            text_out_fx=text_out_id,
            trans_ms=trans_ms,
        )
        self._send(pkt)
        self._log_send(
            'CTRL',
            f'bg={bg} dim={dimmer} txt={text_mode} '
            f'fx=({bg_in_fx},{bg_out_fx},{text_in_fx},{text_out_fx}) '
            f'trans={trans_ms}ms Z{zone}N{node}'
        )
        print(
            f"[TdLedController] ctrl bg={bg} dim={dimmer} txt={text_mode} "
            f"fx=({bg_in_fx},{bg_out_fx},{text_in_fx},{text_out_fx}) "
            f"trans={trans_ms}ms Z{zone}N{node}"
        )

    # ----------------------------------------------------------
    def send_heartbeat(self) -> None:
        """
        ハートビートを送信する。
        3 秒以内に 1 回送らないと LED ノードがセーフ白に遷移する。
        TD の Timer CHOP (周期 1.5秒) + Execute DAT で定期呼び出しすること。
        """
        self._send(build_heartbeat())
        self._log_send('HEARTBEAT', 'global')

    # ----------------------------------------------------------
    def send_lyrics_line(self, text: str,
                         song_id: int = 1, version: int = 1,
                         zone: int = 0, node: int = 0) -> None:
        """
        歌詞テキストを 1 行送信する (14 文字 = 88px 幅に収まる目安)。
        text: ASCII 文字列 (日本語は '?' 置換される)
        """
        pkt = build_lyrics(text, zone=zone, node=node,
                           song_id=song_id, version=version)
        self._send(pkt)
        self._log_send('CONTENT(LYRICS)', f"'{text}' song=0x{song_id:04X} ver={version} Z{zone}N{node}")
        print(f"[TdLedController] lyrics='{text}' song=0x{song_id:04X} ver={version}")

    # ----------------------------------------------------------
    def send_lyrics_chunks(self, text: str,
                           song_id: int = 1, version: int = 1,
                           zone: int = 0, node: int = 0,
                           chunk_gap_s: float = 0.03) -> None:
        """1行を複数チャンクに分割して送信する。"""
        packets = build_lyrics_chunks(text, zone=zone, node=node,
                                      song_id=song_id, version=version)
        for i, pkt in enumerate(packets, start=1):
            self._send(pkt)
            self._log_send('CONTENT(LYRICS)', f'chunk {i}/{len(packets)} song=0x{song_id:04X} ver={version} Z{zone}N{node}')
            if i < len(packets):
                time.sleep(max(0.0, float(chunk_gap_s)))
        print(f"[TdLedController] lyrics-chunks sent ({len(packets)} chunks)")

    # ----------------------------------------------------------
    def play_lyrics_file(self,
                         file_path: str,
                         interval_s: float = 2.0,
                         timed: bool = True,
                         song_id: int = 1,
                         version: int = 1,
                         zone: int = 0,
                         node: int = 0,
                         start_delay_s: float = 0.0,
                         chunked: bool = True,
                         stop_flag_getter=None) -> int:
        """歌詞ファイルを読み込み、時間制御で送信する。"""
        events = parse_lyrics_file(file_path, interval_s=interval_s, timed=timed)
        play_lyrics_events(self, events,
                          song_id=song_id,
                          version=version,
                          zone=zone,
                          node=node,
                          start_delay_s=start_delay_s,
                          chunked=chunked,
                          stop_flag_getter=stop_flag_getter)
        return len(events)

    # ----------------------------------------------------------
    def send_dimmer(self, dimmer: int,
                    zone: int = 0, node: int = 0) -> None:
        """輝度だけを変更する (BG/テキストは維持)。"""
        pkt = build_ctrl(zone=zone, node=node,
                         dimmer=max(0, min(255, dimmer)))
        self._send(pkt)
        self._log_send('CTRL', f'dimmer={dimmer} Z{zone}N{node}')

    # ----------------------------------------------------------
    def send_text_custom(self, text: str,
                         zone: int = 0, node: int = 0) -> None:
        """
        カスタムテキスト（Welcome/Thanks/Countdown など）を CONTENT として送信する。
        text: 最大 48 文字
        """
        if not text:
            return
        text = text[:48]  # 最大 48 文字に制限
        # CONTENT パケット生成（LYRICS ではなく CUSTOM テキスト）
        pkt = build_content_custom(zone=zone, node=node,
                                  content_type=0x00,  # 0x00 = CUSTOM
                                  text=text)
        self._send(pkt)
        self._log_send('CONTENT(CUSTOM)', f"'{text}' Z{zone}N{node}")
        print(f"[TdLedController] text_custom='{text}' Z{zone}N{node}")

    # ----------------------------------------------------------
    def send_countdown(self, seconds: int,
                       zone: int = 0, node: int = 0) -> None:
        """
        カウントダウン形式でテキストを送信する。
        seconds: 残り秒数 (0 ～ 999)
        表示形式: "開始まで M:SS" (例: "開始まで 3:00")
        """
        if seconds < 0:
            seconds = 0
        minutes = seconds // 60
        secs = seconds % 60
        text = f"開始まで {minutes}:{secs:02d}"
        self.send_text_custom(text, zone=zone, node=node)

    # ----------------------------------------------------------
    def send_thanks(self, zone: int = 0, node: int = 0) -> None:
        """
        Thanks メッセージを送信する。
        """
        self.send_text_custom("Thank you!", zone=zone, node=node)

    # ----------------------------------------------------------
    def close(self) -> None:
        self._sock.close()
        print("[TdLedController] socket closed")


# ============================================================
#  TD Script DAT からの簡易使用例 (コメント参照)
# ============================================================
#
# ---- TD Script DAT (onSetupParameters) ----
# import sys
# sys.path.insert(0, 'C:/Projects/02_HomeLiveHall_Trial01/tools')
# import td_sat_sender as sat
# parent().store('led_ctrl', sat.TdLedController())
#
# ---- TD Script DAT (onCook または Execute DAT) ----
# ctrl = parent().fetch('led_ctrl')
# ctrl.send_heartbeat()          # Timer CHOP で 1.5秒ごと
#
# ---- Button Comp の Callback ----
# ctrl = parent().fetch('led_ctrl')
# ctrl.send_scene('LIVE')
#
