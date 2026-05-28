"""
test_wifi_led_interactive.py

対話型 RGB コントローラ
リアルタイムで LED の色を制御
"""

import socket
import time

def send_color(controller_ip, r, g, b, port=5000):
    """RGB を UDP で送信"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        data = bytes([r, g, b])
        sock.sendto(data, (controller_ip, port))
        sock.close()
        print(f"✓ RGB({r:3d}, {g:3d}, {b:3d}) sent")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def rgb_to_hex(r, g, b):
    """RGB を 16 進数に変換"""
    return f"#{r:02X}{g:02X}{b:02X}"

def hex_to_rgb(hex_str):
    """16 進数を RGB に変換"""
    hex_str = hex_str.lstrip('#')
    if len(hex_str) != 6:
        return None
    try:
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    except:
        return None

def show_presets():
    """プリセット色を表示"""
    presets = {
        '1': (255, 0, 0),       # Red
        '2': (0, 255, 0),       # Green
        '3': (0, 0, 255),       # Blue
        '4': (255, 255, 0),     # Yellow
        '5': (255, 0, 255),     # Magenta
        '6': (0, 255, 255),     # Cyan
        '7': (255, 255, 255),   # White
        '8': (0, 0, 0),         # Black (off)
    }
    
    print("\nプリセット色:")
    for key, (r, g, b) in presets.items():
        print(f"  {key}: RGB({r:3d}, {g:3d}, {b:3d}) {rgb_to_hex(r, g, b)}")
    
    return presets

def main():
    print("=" * 60)
    print("ESP32 Wi-Fi LED Control - Interactive Mode")
    print("=" * 60)
    
    controller_ip = input("ESP32-S3 の IP アドレスを入力 (例: 192.168.1.100): ").strip()
    
    if not controller_ip:
        print("IP が入力されていません")
        return
    
    print(f"\n接続先: {controller_ip}:5000")
    print("コマンド:")
    print("  1-8        : プリセット色を送信")
    print("  R,G,B      : RGB 値を送信 (例: 255,128,0)")
    print("  #RRGGBB    : 16 進数で色を送信 (例: #FF8000)")
    print("  p          : プリセット一覧を表示")
    print("  q          : 終了")
    print("=" * 60)
    
    presets = show_presets()
    
    while True:
        try:
            cmd = input("\n> ").strip().lower()
            
            if cmd == 'q':
                print("終了します")
                break
            
            elif cmd == 'p':
                show_presets()
            
            elif cmd in presets:
                r, g, b = presets[cmd]
                send_color(controller_ip, r, g, b)
            
            elif ',' in cmd:
                # RGB 入力
                try:
                    parts = cmd.split(',')
                    r = int(parts[0].strip())
                    g = int(parts[1].strip())
                    b = int(parts[2].strip())
                    
                    if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255):
                        print("✗ RGB は 0-255 の範囲で入力してください")
                        continue
                    
                    send_color(controller_ip, r, g, b)
                except:
                    print("✗ 形式: R,G,B (例: 255,128,0)")
            
            elif cmd.startswith('#'):
                # 16 進数入力
                rgb = hex_to_rgb(cmd)
                if rgb:
                    r, g, b = rgb
                    send_color(controller_ip, r, g, b)
                else:
                    print("✗ 形式: #RRGGBB (例: #FF8000)")
            
            else:
                print("✗ 不正なコマンド。'p' でヘルプを表示")
        
        except KeyboardInterrupt:
            print("\n\n中止しました")
            break
        except Exception as e:
            print(f"✗ エラー: {e}")

if __name__ == "__main__":
    main()
