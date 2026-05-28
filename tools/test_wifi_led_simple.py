"""
test_wifi_led_simple.py

シンプルな RGB 送信テスト
ESP32-S3（中央ノード）が Wi-Fi UDP ポート 5000 でリッスン中と仮定
"""

import socket
import time
import sys

def send_color(controller_ip, r, g, b, port=5000):
    """RGB を UDP で送信"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        data = bytes([r, g, b])
        sock.sendto(data, (controller_ip, port))
        sock.close()
        print(f"✓ Sent RGB({r:3d}, {g:3d}, {b:3d}) to {controller_ip}:{port}")
        return True
    except Exception as e:
        print(f"✗ Error sending color: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("使い方: python test_wifi_led_simple.py <ESP32_IP> [R] [G] [B]")
        print("例:")
        print("  python test_wifi_led_simple.py 192.168.1.100")
        print("  python test_wifi_led_simple.py 192.168.1.100 255 0 0")
        sys.exit(1)

    controller_ip = sys.argv[1]
    
    if len(sys.argv) >= 5:
        # 固定の RGB を送信
        r = int(sys.argv[2])
        g = int(sys.argv[3])
        b = int(sys.argv[4])
        send_color(controller_ip, r, g, b)
    else:
        # RGB 循環テスト
        print(f"RGB Cycling Test: {controller_ip}")
        print("RGB を循環させます (Ctrl+C で中止)")
        
        colors = [
            (255, 0, 0),    # Red
            (0, 255, 0),    # Green
            (0, 0, 255),    # Blue
            (255, 255, 0),  # Yellow
            (255, 0, 255),  # Magenta
            (0, 255, 255),  # Cyan
        ]
        
        try:
            cycle = 0
            while True:
                for r, g, b in colors:
                    send_color(controller_ip, r, g, b)
                    time.sleep(1)
                cycle += 1
                print(f"--- Cycle {cycle} complete ---")
        except KeyboardInterrupt:
            print("\n中止しました")

if __name__ == "__main__":
    main()
