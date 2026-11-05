"""Controller for drone TELLO-99484E."""

import argparse
import os
import socket
import subprocess
import sys
import threading
import time

DEFAULT_DRONE_IP = "192.168.10.1"
CMD_PORT = 8889
STATE_PORT = 8890

# Phone hotspot
HOTSPOT_SSID = "Samsung"
HOTSPOT_PASS = "12345678m"

MESSAGE = "HELLO"
COLOR = "r"
HOLD_S = 1.3
COMMAND_TIMEOUT_S = 2.5
DRONE_CODE = "TELLO-99484E"
DRONE_IP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), f".drone-ip-{DRONE_CODE}")


def wifi_ipv4():
    try:
        out = subprocess.check_output(
            ["netsh", "interface", "ip", "show", "address", "name=Wi-Fi"],
            text=True,
            errors="replace",
        )
        for line in out.splitlines():
            if "IP Address" in line and ":" in line:
                ip = line.split(":", 1)[1].strip()
                if ip and not ip.startswith("169.254."):
                    return ip
    except Exception:
        pass
    return "0.0.0.0"


def send_cmd(sock, drone_ip, cmd, timeout=COMMAND_TIMEOUT_S, label=None):
    print(f">> {label or cmd}", flush=True)
    sock.sendto(cmd.encode("utf-8"), (drone_ip, CMD_PORT))
    sock.settimeout(timeout)
    try:
        data, _ = sock.recvfrom(2048)
        reply = data.decode("utf-8", errors="replace").strip("\x00\r\n ")
        print(f"<< {reply}", flush=True)
        return reply
    except socket.timeout:
        print("   (no reply)", flush=True)
        return ""


def enter_sdk_mode(sock, drone_ip):
    print(f"Connecting to {DRONE_CODE} at {drone_ip}:{CMD_PORT}...")
    for attempt in range(1, 6):
        reply = send_cmd(sock, drone_ip, "command")
        if "ok" in reply.lower():
            print("[OK] SDK mode active.\n")
            return True
        time.sleep(0.4)
    print(f"[!] Warning: Drone at {drone_ip} did not return 'ok'.")
    return False


def set_station_mode(sock, drone_ip, ssid, password):
    if not enter_sdk_mode(sock, drone_ip):
        return False
    cmd = f"ap {ssid} {password}"
    print(f"\nInstructing {DRONE_CODE} to connect to Wi-Fi: '{ssid}'...")
    reply = send_cmd(sock, drone_ip, cmd, timeout=6.0, label=f"ap {ssid} ****")
    if "ok" in reply.lower() or "reboot" in reply.lower():
        print(f"\n[SUCCESS] {DRONE_CODE} accepted station mode! It will reboot onto '{ssid}'.")
        return True
    return False


def probe_drone(local_ip, drone_ip, timeout=0.5):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        if local_ip and local_ip != "0.0.0.0":
            s.bind((local_ip, 0))
        s.settimeout(timeout)
        s.sendto(b"command", (drone_ip, CMD_PORT))
        data, addr = s.recvfrom(1024)
        if data and b"ok" in data.lower():
            return addr[0]
    except OSError:
        return None
    finally:
        s.close()
    return None


def scan_for_drone_on_lan():
    local = wifi_ipv4()
    if not local or local == "0.0.0.0" or local.startswith("127."):
        return None
    prefix = ".".join(local.split(".")[:3]) + "."
    found = []
    lock = threading.Lock()

    def probe(i):
        hit = probe_drone(local, prefix + str(i), timeout=0.4)
        if hit:
            with lock:
                found.append(hit)

    threads = [threading.Thread(target=probe, args=(i,), daemon=True) for i in range(1, 255)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=1.5)
    return found[0] if found else None


def main():
    parser = argparse.ArgumentParser(description=f"Control {DRONE_CODE}")
    parser.add_argument("--sta", action="store_true", help="Connect drone to Wi-Fi")
    parser.add_argument("--ssid", default=HOTSPOT_SSID)
    parser.add_argument("--password", default=HOTSPOT_PASS)
    parser.add_argument("--ip", help="Drone IP")
    args = parser.parse_args()

    local_ip = wifi_ipv4()
    drone_ip = args.ip or scan_for_drone_on_lan() or DEFAULT_DRONE_IP
    print(f"[{DRONE_CODE}] Target Drone IP: {drone_ip} | Local: {local_ip}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        if local_ip and not local_ip.startswith("0."):
            sock.bind((local_ip, 0))
        else:
            sock.bind(("", 0))
    except Exception:
        sock.bind(("", 0))

    try:
        if args.sta:
            ok = set_station_mode(sock, drone_ip, args.ssid, args.password)
            sys.exit(0 if ok else 1)
        else:
            enter_sdk_mode(sock, drone_ip)
    finally:
        sock.close()


if __name__ == "__main__":
    main()

