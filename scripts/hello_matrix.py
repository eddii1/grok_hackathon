"""RoboMaster TT (Tello Talent) Controller.

Spell 'HELLO' letter-by-letter on the 8x8 dot-matrix display and connect
the drone to Wi-Fi / Hotspot (Station Mode).

Usage:
  # 1. Connect drone to 'Samsung S24 Ultra' hotspot (run while on drone Wi-Fi):
  python scripts/hello_matrix.py --sta

  # 2. Show 'HELLO' letter-by-letter on the 8x8 matrix display:
  python scripts/hello_matrix.py

  # 3. Custom options:
  python scripts/hello_matrix.py --color b --hold 1.5 --loops 2
"""

import argparse
import socket
import sys
import threading
import time
from djitellopy import Tello

DEFAULT_DRONE_IP = "192.168.10.1"

# Target phone hotspot credentials
HOTSPOT_SSID = "Samsung S24 Ultra "
HOTSPOT_PASS = "12345678m"

MESSAGE = "HELLO"
COLOR = "r"  # r=red, b=blue, p=purple
HOLD_S = 1.3


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def ping_udp(ip, port=8889, timeout=0.3):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(b"command", (ip, port))
        data, _ = s.recvfrom(1024)
        return bool(data)
    except Exception:
        return False
    finally:
        s.close()


def scan_subnet(base_ip):
    parts = base_ip.split(".")
    if len(parts) != 4:
        return []
    prefix = ".".join(parts[:3])
    found = []
    lock = threading.Lock()

    def check(ip):
        if ping_udp(ip):
            with lock:
                found.append(ip)

    threads = []
    for i in range(1, 255):
        t = threading.Thread(target=check, args=(f"{prefix}.{i}",), daemon=True)
        threads.append(t)
        t.start()
        if i % 30 == 0:
            time.sleep(0.03)

    for t in threads:
        t.join(timeout=1.0)
    return found


def resolve_drone_ip(explicit_ip=None):
    if explicit_ip:
        return explicit_ip

    # 1. Direct AP IP (192.168.10.1)
    if ping_udp(DEFAULT_DRONE_IP):
        return DEFAULT_DRONE_IP

    # 2. Check local subnet
    local = get_local_ip()
    if local != "127.0.0.1":
        print(f"Scanning local network {local}/24 for active drones...")
        drones = scan_subnet(local)
        if drones:
            print(f"[Auto-detect] Found drone on LAN at: {drones[0]}")
            return drones[0]

    return DEFAULT_DRONE_IP


def main():
    parser = argparse.ArgumentParser(description="RoboMaster TT Matrix & Station Mode")
    parser.add_argument("--sta", action="store_true", help="Connect drone to Wi-Fi / phone hotspot")
    parser.add_argument("--ssid", default=HOTSPOT_SSID, help=f"Wi-Fi SSID for station mode (default: '{HOTSPOT_SSID}')")
    parser.add_argument("--password", default=HOTSPOT_PASS, help="Wi-Fi password for station mode")
    parser.add_argument("--ip", help="Drone IP address (default: auto-detect)")
    parser.add_argument("--color", choices=["r", "b", "p"], default=COLOR, help="Color: r (red), b (blue), p (purple)")
    parser.add_argument("--hold", type=float, default=HOLD_S, help="Seconds per letter")
    parser.add_argument("--loops", type=int, default=1, help="Number of repetitions")

    args = parser.parse_args()

    drone_ip = resolve_drone_ip(args.ip)
    print(f"Target drone IP: {drone_ip}")

    tello = Tello(host=drone_ip, retry_count=2)
    try:
        print("Connecting to drone...")
        tello.connect(wait_for_state=False)

        if args.sta:
            print(f"\nInstructing drone to join Wi-Fi SSID: '{args.ssid}'...")
            try:
                tello.connect_to_wifi(args.ssid, args.password)
                print("\n[SUCCESS] Drone accepted Station Mode command! It will reboot in ~3 seconds.")
                print(f"Ensure your PC is on '{args.ssid}', then run: python scripts/hello_matrix.py")
            except Exception as e:
                print(f"Station command finished with: {e}")
        else:
            print(f"\nSpelling '{MESSAGE}' letter-by-letter on the 8x8 dot-matrix display...")
            try:
                # Set top LED
                rgb = {"r": "255 0 0", "b": "0 0 255", "p": "255 0 255"}.get(args.color, "255 0 0")
                tello.send_control_command(f"EXT led {rgb}")
            except Exception:
                pass

            try:
                # Set matrix brightness to max
                tello.send_control_command("EXT mled sl 255")
            except Exception:
                pass

            for loop in range(args.loops):
                if args.loops > 1:
                    print(f"\n--- Pass {loop + 1} of {args.loops} ---")
                for char in MESSAGE:
                    print(f"[Matrix] Showing '{char}' in {args.color}...")
                    try:
                        tello.send_control_command(f"EXT mled s {args.color} {char}")
                    except Exception as e:
                        print(f"   (command sent: {e})")
                    time.sleep(args.hold)
                time.sleep(0.5)

            print("\n[Done] Finished spelling HELLO letter by letter.")

    finally:
        try:
            tello.end()
        except Exception:
            pass


if __name__ == "__main__":
    main()
