#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LED Node UART テストツール

中央ノード代わりに PC から UART で LED ノードにコマンドを送信
画像・パターン表示を検証

使用方法:
    python led_uart_test_tool.py [コマンド] [引数...]
    
例:
    python led_uart_test_tool.py color 255 0 0     # 赤塗り
    python led_uart_test_tool.py color 0 255 0     # 緑塗り
    python led_uart_test_tool.py brightness 50     # 輝度 50%
    python led_uart_test_tool.py stop               # 全消灯
    python led_uart_test_tool.py heartbeat          # ハートビート送信
"""

try:
    import serial
except ImportError:
    serial = None
import struct
import time
import sys
import colorsys
from enum import IntEnum


class HubUartCmd(IntEnum):
    SET_BRIGHTNESS = 0x01
    SET_COLOR = 0x02
    SET_EFFECT = 0x03
    PLAY_ASSET = 0x04
    STOP = 0x05
    HEARTBEAT = 0x10
    ACK = 0x11
    RESET = 0xFF


class HubUartFrame:
    """UART フレーム構造体"""
    STX = 0xAA
    ETX = 0x55
    PAYLOAD_MAX = 32
    
    def __init__(self):
        self.stx = self.STX
        self.cmd = 0
        self.len = 0
        self.payload = bytearray(self.PAYLOAD_MAX)
        self.crc8 = 0
        self.etx = self.ETX
    
    @staticmethod
    def crc8_maxim(data):
        """CRC-8/MAXIM を計算"""
        crc = 0
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0x8C
                else:
                    crc >>= 1
        return crc
    
    def calc_crc8(self):
        """このフレームの CRC-8 を計算"""
        data = bytearray()
        data.append(self.stx)
        data.append(self.cmd)
        data.append(self.len)
        data.extend(self.payload[:self.len])
        return self.crc8_maxim(data)
    
    def encode(self):
        """フレームをバイト列にエンコード"""
        frame_len = 1 + 1 + 1 + self.len + 1 + 1
        buffer = bytearray(frame_len)
        
        self.crc8 = self.calc_crc8()
        
        pos = 0
        buffer[pos] = self.stx
        pos += 1
        buffer[pos] = self.cmd
        pos += 1
        buffer[pos] = self.len
        pos += 1
        buffer[pos:pos+self.len] = self.payload[:self.len]
        pos += self.len
        buffer[pos] = self.crc8
        pos += 1
        buffer[pos] = self.etx
        
        return bytes(buffer)
    
    @classmethod
    def decode(cls, data):
        """バイト列からフレームをデコード"""
        if len(data) < 5:
            return None, 0  # 不完全
        
        frame = cls()
        pos = 0
        
        # STX チェック
        if data[pos] != cls.STX:
            return None, -1  # フレーミングエラー
        frame.stx = data[pos]
        pos += 1
        
        frame.cmd = data[pos]
        pos += 1
        frame.len = data[pos]
        pos += 1
        
        if frame.len > cls.PAYLOAD_MAX:
            return None, -1
        
        expected_len = 1 + 1 + 1 + frame.len + 1 + 1
        if len(data) < expected_len:
            return None, 0  # 不完全
        
        frame.payload[:frame.len] = data[pos:pos+frame.len]
        pos += frame.len
        
        frame.crc8 = data[pos]
        pos += 1
        frame.etx = data[pos]
        pos += 1
        
        # ETX チェック
        if frame.etx != cls.ETX:
            return None, -1
        
        # CRC チェック
        expected_crc = frame.calc_crc8()
        if frame.crc8 != expected_crc:
            print(f"[CRC Error] Expected: 0x{expected_crc:02X}, Got: 0x{frame.crc8:02X}")
            return None, -1
        
        return frame, expected_len


class LedUartTester:
    """LED Node UART テスターPC"""
    
    def __init__(self, port='COM3', baudrate=115200, timeout=1.0, wait_ack=False, boot_wait=2.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.wait_ack = wait_ack
        self.boot_wait = boot_wait
        self.ser = None
        self.rx_buffer = bytearray()
    
    def connect(self, flush_input=True):
        """シリアルポート接続"""
        if serial is None:
            print("✗ pyserial is not installed. Install with: pip install pyserial")
            return False

        try:
            self.ser = serial.Serial(
                self.port,
                self.baudrate,
                timeout=self.timeout,
                write_timeout=0,
            )
            # NOTE: setDTR(False) は意図的に行わない。
            # ESP32-S3 の USB CDC は DTR=Low を「ホスト未接続」と解釈し、
            # データを受け取らない可能性があるため DTR はデフォルト(High)のままにする。

            time.sleep(self.boot_wait)

            # 起動直後に残っているゴミデータを捨てる（listen モード時はスキップ）
            if flush_input:
                try:
                    self.ser.reset_input_buffer()
                except Exception:
                    pass

            print(f"✓ Connected to {self.port} at {self.baudrate} bps")
            return True
        except Exception as e:
            print(f"✗ Failed to connect: {e}")
            return False
    
    def disconnect(self):
        """シリアルポート切断"""
        if self.ser:
            self.ser.close()
            print("✓ Disconnected")
    
    def read_esp32_log(self, timeout_sec=2.0):
        """ESP32 からのシリアルログを読んで表示する（デバッグ用）"""
        if not self.ser:
            return
        end = time.time() + timeout_sec
        lines = bytearray()
        while time.time() < end:
            n = self.ser.in_waiting
            if n > 0:
                lines.extend(self.ser.read(n))
                end = time.time() + 0.3  # 受信があれば少し延長
            else:
                time.sleep(0.05)
        if lines:
            text = lines.decode('utf-8', errors='replace').rstrip()
            if text:
                print("--- ESP32 log ---")
                for line in text.splitlines():
                    print(f"  {line}")
                print("-----------------")

    def send_frame(self, frame, verbose=True):
        """フレーム送信"""
        if not self.ser:
            print("✗ Not connected")
            return False
        
        data = frame.encode()
        try:
            self.ser.write(data)
        except serial.SerialTimeoutException:
            return False
        if verbose:
            print(f"→ Sent: {' '.join(f'{b:02X}' for b in data)}")
        return True
    
    def receive_frame(self, timeout=2.0):
        """フレーム受信（タイムアウト付き）"""
        if not self.ser:
            print("✗ Not connected")
            return None
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.ser.in_waiting > 0:
                byte = self.ser.read(1)
                self.rx_buffer.extend(byte)
            
            # フレームデコード試行
            frame, result = HubUartFrame.decode(self.rx_buffer)
            if result > 0:
                # デコード成功 → バッファをシフト
                del self.rx_buffer[:result]
                print(f"← Received: [CMD=0x{frame.cmd:02X}, LEN={frame.len}]")
                return frame
            elif result < 0:
                # エラー → 1バイト捨てる
                del self.rx_buffer[:1]
            
            time.sleep(0.01)
        
        print("✗ Receive timeout")
        return None
    
    def cmd_set_color(self, r, g, b, read_log=False):
        """SET_COLOR コマンド"""
        frame = HubUartFrame()
        frame.cmd = HubUartCmd.SET_COLOR
        frame.len = 3
        frame.payload[0] = r
        frame.payload[1] = g
        frame.payload[2] = b
        
        print(f"[SET_COLOR] R={r}, G={g}, B={b}")
        self.send_frame(frame)
        if read_log:
            self.read_esp32_log(timeout_sec=1.5)
        if not self.wait_ack:
            return True

        ack = self.receive_frame(timeout=1.0)
        if ack and ack.cmd == HubUartCmd.ACK:
            print("✓ ACK received\n")
            return True
        return False
    
    def cmd_set_brightness(self, brightness):
        """SET_BRIGHTNESS コマンド"""
        frame = HubUartFrame()
        frame.cmd = HubUartCmd.SET_BRIGHTNESS
        frame.len = 1
        frame.payload[0] = brightness
        
        print(f"[SET_BRIGHTNESS] {brightness}/255 ({brightness*100//255}%)")
        self.send_frame(frame)
        if not self.wait_ack:
            return True

        ack = self.receive_frame(timeout=1.0)
        if ack and ack.cmd == HubUartCmd.ACK:
            print("✓ ACK received\n")
            return True
        return False
    
    def cmd_stop(self):
        """STOP コマンド"""
        frame = HubUartFrame()
        frame.cmd = HubUartCmd.STOP
        frame.len = 0
        
        print("[STOP]")
        self.send_frame(frame)
        if not self.wait_ack:
            return True

        ack = self.receive_frame(timeout=1.0)
        if ack and ack.cmd == HubUartCmd.ACK:
            print("✓ ACK received\n")
            return True
        return False
    
    def cmd_heartbeat(self):
        """HEARTBEAT コマンド"""
        frame = HubUartFrame()
        frame.cmd = HubUartCmd.HEARTBEAT
        frame.len = 0
        
        print("[HEARTBEAT]")
        self.send_frame(frame)
        if not self.wait_ack:
            return True

        ack = self.receive_frame(timeout=1.0)
        if ack and ack.cmd == HubUartCmd.ACK:
            print("✓ ACK received\n")
            return True
        return False
    
    def run_demo(self):
        """デモシーケンス"""
        print("\n" + "="*60)
        print("  LED Node UART Demo - Color Test Sequence")
        print("="*60 + "\n")

        # 赤
        print("[Demo 1] Red color")
        self.cmd_set_color(255, 0, 0)
        time.sleep(2)
        
        # 緑
        print("[Demo 2] Green color")
        self.cmd_set_color(0, 255, 0)
        time.sleep(2)
        
        # 青
        print("[Demo 3] Blue color")
        self.cmd_set_color(0, 0, 255)
        time.sleep(2)
        
        # 黄
        print("[Demo 4] Yellow color (RGB: 255,255,0)")
        self.cmd_set_color(255, 255, 0)
        time.sleep(2)
        
        # 輝度テスト
        print("[Demo 5] Brightness test (255 -> 128 -> 64 -> 32)")
        for brightness in [255, 128, 64, 32]:
            self.cmd_set_brightness(brightness)
            time.sleep(1)
        
        # ハートビート + STOP
        print("[Demo 6] Heartbeat + Stop")
        self.cmd_heartbeat()
        time.sleep(1)
        self.cmd_stop()
        
        print("\n" + "="*60)
        print("  Demo completed!")
        print("="*60 + "\n")

    def stream_color_cycle(self, duration_sec=10.0, target_fps=60.0):
        """高頻度ストリーム送信ベンチ（ACKなし前提）"""
        print("\n" + "=" * 60)
        print("  UART Stream Benchmark (Color Cycle)")
        print("=" * 60)
        print(f"duration: {duration_sec:.1f}s, target_fps: {target_fps:.1f}")

        if target_fps <= 0:
            print("✗ target_fps must be > 0")
            return

        interval = 1.0 / target_fps
        start = time.perf_counter()
        next_tick = start
        sent = 0
        dropped = 0

        while True:
            now = time.perf_counter()
            elapsed = now - start
            if elapsed >= duration_sec:
                break

            # 経過時間で Hue を回して色を変化
            hue = (elapsed * 0.25) % 1.0
            r_f, g_f, b_f = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
            r = int(r_f * 255)
            g = int(g_f * 255)
            b = int(b_f * 255)

            frame = HubUartFrame()
            frame.cmd = HubUartCmd.SET_COLOR
            frame.len = 3
            frame.payload[0] = r
            frame.payload[1] = g
            frame.payload[2] = b
            if self.send_frame(frame, verbose=False):
                sent += 1
            else:
                dropped += 1

            if self.wait_ack:
                self.receive_frame(timeout=0.01)

            next_tick += interval
            sleep_time = next_tick - time.perf_counter()
            if sleep_time > 0:
                time.sleep(sleep_time)

        total = time.perf_counter() - start
        actual_fps = sent / total if total > 0 else 0
        print(f"\nSent frames: {sent}")
        print(f"Dropped writes: {dropped}")
        print(f"Elapsed: {total:.3f}s")
        print(f"Actual FPS: {actual_fps:.1f}")
        print("=" * 60 + "\n")

    def burst_color(self, r, g, b, count=20, interval_ms=30, read_log=False):
        """同じ色コマンドを複数回送信して受信取りこぼしを回避する"""
        if count <= 0:
            print("✗ count must be > 0")
            return

        if interval_ms < 0:
            print("✗ interval_ms must be >= 0")
            return

        print(f"[BURST_COLOR] R={r}, G={g}, B={b}, count={count}, interval_ms={interval_ms}")
        sent = 0
        for _ in range(count):
            frame = HubUartFrame()
            frame.cmd = HubUartCmd.SET_COLOR
            frame.len = 3
            frame.payload[0] = r
            frame.payload[1] = g
            frame.payload[2] = b

            if self.send_frame(frame, verbose=False):
                sent += 1
            if interval_ms > 0:
                time.sleep(interval_ms / 1000.0)

        print(f"Sent frames: {sent}/{count}")
        if read_log:
            self.read_esp32_log(timeout_sec=1.5)


def dryrun_print_frame(frame_name, frame):
    """ハード未接続でフレーム整合性を確認する"""
    encoded = frame.encode()
    decoded, consumed = HubUartFrame.decode(encoded)

    print(f"[DRYRUN] {frame_name}")
    print(f"  bytes: {' '.join(f'{b:02X}' for b in encoded)}")
    print(f"  len:   {len(encoded)}")
    if decoded is None or consumed <= 0:
        print("  decode: FAILED")
    else:
        payload = ' '.join(f'{b:02X}' for b in decoded.payload[:decoded.len]) if decoded.len > 0 else '(none)'
        print(f"  decode: OK cmd=0x{decoded.cmd:02X} len={decoded.len} payload={payload} crc=0x{decoded.crc8:02X}")
    print()


def run_dryrun(args):
    """dryrun コマンド: ハード未接続でフレーム生成とCRC検証"""
    if len(args) < 2:
        print("Usage: dryrun <color|brightness|stop|heartbeat|all> [args]")
        return

    target = args[1].lower()

    if target == 'color':
        if len(args) < 5:
            print("Usage: dryrun color <R> <G> <B>")
            return
        r, g, b = int(args[2]), int(args[3]), int(args[4])
        frame = HubUartFrame()
        frame.cmd = HubUartCmd.SET_COLOR
        frame.len = 3
        frame.payload[0] = r
        frame.payload[1] = g
        frame.payload[2] = b
        dryrun_print_frame(f"SET_COLOR r={r} g={g} b={b}", frame)
        return

    if target == 'brightness':
        if len(args) < 3:
            print("Usage: dryrun brightness <0-255>")
            return
        value = int(args[2])
        frame = HubUartFrame()
        frame.cmd = HubUartCmd.SET_BRIGHTNESS
        frame.len = 1
        frame.payload[0] = value
        dryrun_print_frame(f"SET_BRIGHTNESS value={value}", frame)
        return

    if target == 'stop':
        frame = HubUartFrame()
        frame.cmd = HubUartCmd.STOP
        frame.len = 0
        dryrun_print_frame("STOP", frame)
        return

    if target == 'heartbeat':
        frame = HubUartFrame()
        frame.cmd = HubUartCmd.HEARTBEAT
        frame.len = 0
        dryrun_print_frame("HEARTBEAT", frame)
        return

    if target == 'all':
        examples = [
            ("SET_COLOR RED", HubUartCmd.SET_COLOR, [255, 0, 0]),
            ("SET_COLOR GREEN", HubUartCmd.SET_COLOR, [0, 255, 0]),
            ("SET_BRIGHTNESS 64", HubUartCmd.SET_BRIGHTNESS, [64]),
            ("STOP", HubUartCmd.STOP, []),
            ("HEARTBEAT", HubUartCmd.HEARTBEAT, []),
        ]
        for name, cmd, payload in examples:
            frame = HubUartFrame()
            frame.cmd = cmd
            frame.len = len(payload)
            for i, value in enumerate(payload):
                frame.payload[i] = value
            dryrun_print_frame(name, frame)
        return

    print("Usage: dryrun <color|brightness|stop|heartbeat|all> [args]")


def main():
    """メイン処理"""
    wait_ack = '--wait-ack' in sys.argv
    read_log = '--log' in sys.argv
    boot_wait = 2.0
    args = []
    idx = 1
    while idx < len(sys.argv):
        cur = sys.argv[idx]
        if cur in ('--wait-ack', '--log'):
            idx += 1
            continue
        if cur == '--boot-wait' and idx + 1 < len(sys.argv):
            boot_wait = float(sys.argv[idx + 1])
            idx += 2
            continue
        args.append(cur)
        idx += 1

    port = 'COM3'
    idx = 1
    while idx < len(sys.argv):
        cur = sys.argv[idx]
        if cur == '--port' and idx + 1 < len(sys.argv):
            port = sys.argv[idx + 1]
            idx += 2
            continue
        idx += 1

    if len(args) > 0 and args[0].lower() == 'dryrun':
        run_dryrun(args)
        return

    tester = LedUartTester(port=port, wait_ack=wait_ack, boot_wait=boot_wait)
    
    # listen コマンドはバッファをクリアしない（起動ログを読むため）
    flush = False if (len(args) > 0 and args[0].lower() == 'listen') else True
    if not tester.connect(flush_input=flush):
        return
    
    try:
        if len(args) < 1:
            # デモモード
            tester.run_demo()
        else:
            cmd = args[0].lower()
            
            if cmd == 'color' and len(args) >= 4:
                r = int(args[1])
                g = int(args[2])
                b = int(args[3])
                tester.cmd_set_color(r, g, b, read_log=read_log)
            
            elif cmd == 'brightness' and len(args) >= 2:
                brightness = int(args[1])
                tester.cmd_set_brightness(brightness)
            
            elif cmd == 'stop':
                tester.cmd_stop()
            
            elif cmd == 'heartbeat':
                tester.cmd_heartbeat()
            
            elif cmd == 'demo':
                tester.run_demo()

            elif cmd == 'stream':
                duration = float(args[1]) if len(args) >= 2 else 10.0
                fps = float(args[2]) if len(args) >= 3 else 60.0
                tester.stream_color_cycle(duration_sec=duration, target_fps=fps)

            elif cmd == 'listen':
                duration = float(args[1]) if len(args) >= 2 else 5.0
                print(f"Listening on {tester.port} for {duration:.1f}s (Ctrl+C to stop)...")
                tester.read_esp32_log(timeout_sec=duration)

            elif cmd == 'burstcolor':
                if len(args) < 4:
                    print("Usage: burstcolor <R> <G> <B> [count] [interval_ms]")
                else:
                    r = int(args[1])
                    g = int(args[2])
                    b = int(args[3])
                    count = int(args[4]) if len(args) >= 5 else 20
                    interval_ms = int(args[5]) if len(args) >= 6 else 30
                    tester.burst_color(r, g, b, count=count, interval_ms=interval_ms, read_log=read_log)
            
            else:
                print("Usage:")
                print("  python led_uart_test_tool.py [command] [args]")
                print()
                print("Commands:")
                print("  color <R> <G> <B>         - Set color (0-255 each)")
                print("  brightness <0-255>        - Set brightness")
                print("  stop                       - Stop and turn off")
                print("  heartbeat                  - Send heartbeat")
                print("  demo                       - Run demo sequence")
                print("  stream [sec] [fps]         - Continuous color stream benchmark")
                print("  burstcolor R G B [n] [ms]  - Repeat same color command")
                print("  dryrun <...>               - No-hardware frame validation")
                print("  --wait-ack                 - ACK を待つ（デフォルトは待たない）")
                print("  --boot-wait <sec>          - ポート接続後の起動待機秒数")
                print("  --port COMx                - シリアルポート指定")
                print()
                print("Examples:")
                print("  python led_uart_test_tool.py color 255 0 0")
                print("  python led_uart_test_tool.py brightness 100")
                print("  python led_uart_test_tool.py demo")
                print("  python led_uart_test_tool.py stream 10 120")
                print("  python led_uart_test_tool.py --boot-wait 2.5 burstcolor 255 0 0 30 20")
                print("  python led_uart_test_tool.py --wait-ack color 255 0 0")
                print("  python led_uart_test_tool.py dryrun all")
                print("  python led_uart_test_tool.py dryrun color 255 0 0")
    
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    
    finally:
        tester.disconnect()


if __name__ == '__main__':
    main()
