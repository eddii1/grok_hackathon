"""RoboMaster TT (Tello Talent) Controller.

Spell 'HELLO' letter-by-letter on the 8x8 dot-matrix display and connect
the drone to Wi-Fi / Hotspot (Station Mode).

Usage:
  # 1. Connect drone to 'Samsung S24 Ultra' hotspot (run while PC is on drone Wi-Fi):
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

DEFAULT_DRONE_IP = "192.168.10.1"
CMD_PORT = 8889
STATE_PORT = 8890

# Target phone hotspot credentials
HOTSPOT_SSID = "Samsung S24 Ultra "
HOTSPOT_PASS = "12345678m"

MESSAGE = "HELLO"
COLOR = "r"  # r=red, b=blue, p=purple
HOLD_S = 1.3
COMMAND_TIMEOUT_S = 2.5


def get_wifi_ip_to(drone_ip):
    """Find the local IP address on the interface that routes to drone_ip."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((drone_ip, CMD_PORT))
        return s.getsockname()[0]
    except Exception:
        return "0.0.0.0"
    finally:
        s.close()


def send_cmd(sock, drone_ip, cmd, timeout=COMMAND_TIMEOUT_S):
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
    for attempt in range(1, 4):
        reply = send_cmd(sock, drone_ip, "command")
        if "ok" in reply.lower():
            print("[OK] SDK mode active.\n")
            return True
        time.sleep(0.4)
    print(f"[!] Warning: Drone at {drone_ip} did not return 'ok'.")
    return False


def set_station_mode(sock, drone_ip, ssid, password):
    """Instruct the drone to connect to the target Wi-Fi network."""
    enter_sdk_mode(sock, drone_ip)

    # Some Tello firmwares accept quoted SSIDs, others raw string
    cmd = f"ap {ssid} {password}".strip()
    print(f"\nInstructing drone to connect to Wi-Fi: '{ssid}'...")
    reply = send_cmd(sock, drone_ip, cmd, timeout=4.0)

    if not reply or "error" in reply.lower():
        # Retry with quotes if SSID has spaces
        alt_cmd = f'ap "{ssid.strip()}" {password}'
        print(f"Retrying with alternative format: {alt_cmd}")
        reply = send_cmd(sock, drone_ip, alt_cmd, timeout=4.0)

    if "ok" in reply.lower() or "reboot" in reply.lower():
        print("\n[SUCCESS] Drone accepted station mode! It will reboot in ~3s and join the network.")
        print(f"Ensure your PC is connected to '{ssid}', then run: python scripts/hello_matrix.py")
        return True
    else:
        print(f"\n[!] Drone response: '{reply}'")
        return False


def show_hello(sock, drone_ip, color, hold_s, loops):
    """Spell HELLO letter-by-letter on the 8x8 dot-matrix display."""
    enter_sdk_mode(sock, drone_ip)

    # Top RGB LED
    rgb = {"r": "255 0 0", "b": "0 0 255", "p": "255 0 255"}.get(color, "255 0 0")
    send_cmd(sock, drone_ip, f"EXT led {rgb}", timeout=1.0)

    # Dot-matrix brightness (0-255)
    send_cmd(sock, drone_ip, "EXT mled sl 255", timeout=1.0)

    for loop in range(loops):
        if loops > 1:
            print(f"\n--- Pass {loop + 1} of {loops} ---")
        for letter in MESSAGE:
            print(f"[Matrix] Showing '{letter}' in {color}...")
            send_cmd(sock, drone_ip, f"EXT mled s {color} {letter}", timeout=1.0)
            time.sleep(hold_s)
        time.sleep(0.5)

    print("\n[Done] Finished spelling HELLO letter by letter.")


def scan_for_drone_on_lan():
    """Look for any drone responding on the current local network."""
    local = get_wifi_ip_to("8.8.8.8")
    if local == "0.0.0.0" or local.startswith("127."):
        return None

    prefix = ".".join(local.split(".")[:3])
    print(f"Scanning local network {prefix}.0/24 for connected drone...")
    found = []
    lock = threading.Lock()

    def probe(ip):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.3)
        try:
            s.sendto(b"command", (ip, CMD_PORT))
            d, _ = s.recvfrom(1024)
            if d:
                with lock:
                    found.append(ip)
        except Exception:
            pass
        finally:
            s.close()

    threads = []
    for i in range(1, 255):
        t = threading.Thread(target=probe, args=(f"{prefix}.{i}",), daemon=True)
        threads.append(t)
        t.start()
        if i % 30 == 0:
            time.sleep(0.03)

    for t in threads:
        t.join(timeout=1.0)

    return found[0] if found else None


def main():
    parser = argparse.ArgumentParser(description="RoboMaster TT Matrix & Wi-Fi Station Mode")
    parser.add_argument("--sta", action="store_true", help="Connect drone to Wi-Fi / phone hotspot")
    parser.add_argument("--ssid", default=HOTSPOT_SSID, help=f"Wi-Fi SSID for station mode (default: '{HOTSPOT_SSID}')")
    parser.add_argument("--password", default=HOTSPOT_PASS, help="Wi-Fi password for station mode")
    parser.add_argument("--ip", help="Drone IP address (default: auto-detect)")
    parser.add_argument("--color", choices=["r", "b", "p"], default=COLOR, help="Color: r (red), b (blue), p (purple)")
    parser.add_argument("--hold", type=float, default=HOLD_S, help="Seconds per letter")
    parser.add_argument("--loops", type=int, default=1, help="Number of repetitions")

    args = parser.parse_args()

    drone_ip = args.ip
    if not drone_ip:
        # Check if drone is on local subnet first
        lan_ip = scan_for_drone_on_lan()
        if lan_ip:
            print(f"[Auto-detect] Found drone on LAN at: {lan_ip}")
            drone_ip = lan_ip
        else:
            drone_ip = DEFAULT_DRONE_IP

    # Bind explicitly to the interface IP routing to the drone (prevents VPN/Tailscale hijacking)
    local_ip = get_wifi_ip_to(drone_ip)
    print(f"Target Drone IP:   {drone_ip}")
    print(f"Local Outbound IP: {local_ip}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        if local_ip and local_ip != "0.0.0.0":
            sock.bind((local_ip, 0))
        else:
            sock.bind(("", 0))
    except Exception:
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
