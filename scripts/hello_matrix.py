"""RoboMaster TT (Tello Talent) Controller.

Spell 'HELLO' letter-by-letter on the 8x8 dot-matrix display and connect
the drone to Wi-Fi / Hotspot (Station Mode).

Usage:
  # 1. Connect drone to 'Samsung S24 Ultra' hotspot:
  python scripts/hello_matrix.py --sta

  # 2. Show 'HELLO' letter-by-letter on the matrix:
  python scripts/hello_matrix.py

  # 3. Specify custom IP or color (r=red, b=blue, p=purple):
  python scripts/hello_matrix.py --color b --hold 1.5
"""

import argparse
import socket
import sys
import threading
import time

DEFAULT_DRONE_IP = "192.168.10.1"
CMD_PORT = 8889

# Default hotspot credentials from user setup
HOTSPOT_SSID = "Samsung S24 Ultra "
HOTSPOT_PASS = "12345678m"

MESSAGE = "HELLO"
COLOR = "r"  # r=red, b=blue, p=purple
HOLD_S = 1.3
COMMAND_TIMEOUT_S = 2.5


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def ping_udp(ip, port=CMD_PORT, timeout=0.4):
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

    # Check direct AP IP first
    if ping_udp(DEFAULT_DRONE_IP):
        return DEFAULT_DRONE_IP

    # Check local LAN
    local = get_local_ip()
    if local != "127.0.0.1":
        drones = scan_subnet(local)
        if drones:
            print(f"[Auto-detect] Found drone on LAN at: {drones[0]}")
            return drones[0]

    return DEFAULT_DRONE_IP


def send(sock, drone_ip, cmd, timeout=COMMAND_TIMEOUT_S):
    print(f">> {cmd}")
    sock.sendto(cmd.encode("utf-8"), (drone_ip, CMD_PORT))
    sock.settimeout(timeout)
    try:
        data, _ = sock.recvfrom(1024)
        reply = data.decode("utf-8", errors="replace").strip()
        print(f"<< {reply}")
        return reply
    except socket.timeout:
        print("   (no reply)")
        return ""


def enter_sdk_mode(sock, drone_ip):
    print(f"Connecting to drone at {drone_ip}:{CMD_PORT}...")
    for _ in range(3):
        reply = send(sock, drone_ip, "command")
        if "ok" in reply.lower():
            print("[OK] SDK mode active.\n")
            return True
        time.sleep(0.3)
    return False


def set_station_mode(sock, drone_ip, ssid, password):
    """Tell the drone to connect to the target Wi-Fi network."""
    enter_sdk_mode(sock, drone_ip)
    cmd = f"ap {ssid} {password}".strip()
    print(f"\nInstructing drone to connect to Wi-Fi: '{ssid}'...")
    reply = send(sock, drone_ip, cmd, timeout=4.0)
    if "ok" in reply.lower() or "reboot" in reply.lower():
        print("\n[SUCCESS] Drone accepted station mode! It will reboot in ~3s.")
        print(f"Reconnect your PC to '{ssid}' to communicate on the same network.")
    else:
        print(f"\n[!] Drone response: '{reply}'")


def show_hello(sock, drone_ip, color, hold_s, loops):
    """Spell HELLO letter-by-letter on the 8x8 dot-matrix display."""
    enter_sdk_mode(sock, drone_ip)

    # Set top LED
    rgb = {"r": "255 0 0", "b": "0 0 255", "p": "255 0 255"}.get(color, "255 0 0")
    send(sock, drone_ip, f"EXT led {rgb}", 1.0)

    # Set matrix brightness to maximum
    send(sock, drone_ip, "EXT mled sl 255", 1.0)

    for loop in range(loops):
        for letter in MESSAGE:
            print(f"Displaying letter: '{letter}'")
            send(sock, drone_ip, f"EXT mled s {color} {letter}", 1.0)
            time.sleep(hold_s)
        time.sleep(0.5)

    print("\n[Done] Finished spelling HELLO letter by letter.")


def main():
    parser = argparse.ArgumentParser(description="RoboMaster TT Matrix & Wi-Fi Setup")
    parser.add_argument("--sta", action="store_true", help="Connect drone to Wi-Fi / phone hotspot")
    parser.add_argument("--ssid", default=HOTSPOT_SSID, help=f"Wi-Fi SSID for station mode (default: '{HOTSPOT_SSID}')")
    parser.add_argument("--password", default=HOTSPOT_PASS, help="Wi-Fi password for station mode")
    parser.add_argument("--ip", help="Drone IP address (default: auto-detect)")
    parser.add_argument("--color", choices=["r", "b", "p"], default=COLOR, help="Color: r (red), b (blue), p (purple)")
    parser.add_argument("--hold", type=float, default=HOLD_S, help="Seconds per letter")
    parser.add_argument("--loops", type=int, default=1, help="Number of repetitions")

    args = parser.parse_args()

    drone_ip = resolve_drone_ip(args.ip)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", 0))

    try:
        if args.sta:
            set_station_mode(sock, drone_ip, args.ssid, args.password)
        else:
            show_hello(sock, drone_ip, args.color, args.hold, args.loops)
    finally:
        sock.close()


if __name__ == "__main__":
    main()
