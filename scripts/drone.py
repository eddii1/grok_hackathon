"""RoboMaster TT (Tello Talent) Controller.

Single unified script to:
  1. Show HELLO letter-by-letter on the 8x8 dot-matrix display.
  2. Connect the drone to a Wi-Fi / Hotspot (Station Mode).
  3. Scan the local network to find connected drones.
  4. Query drone battery, telemetry, and hardware info.

Usage:
  # Display 'HELLO' letter-by-letter on the matrix:
  python scripts/drone.py hello

  # Connect drone to phone hotspot (defaults to 'Samsung S24 Ultra'):
  python scripts/drone.py sta

  # Connect drone to custom Wi-Fi network:
  python scripts/drone.py sta --ssid "MyNetwork" --password "MyPassword"

  # Find drone IP on current local network:
  python scripts/drone.py scan

  # Query drone status / battery:
  python scripts/drone.py status
"""

import argparse
import socket
import sys
import threading
import time

DEFAULT_DRONE_IP = "192.168.10.1"
CMD_PORT = 8889
STATE_PORT = 8890

# Default hotspot credentials detected on this machine
DEFAULT_SSID = "Samsung S24 Ultra "
DEFAULT_PASS = "12345678m"


class DroneController:
    def __init__(self, drone_ip=None, timeout=3.0):
        self.drone_ip = drone_ip or self.detect_drone_ip()
        self.timeout = timeout
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("", 0))
        self.sock.settimeout(timeout)

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass

    @staticmethod
    def get_local_ip():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"
        finally:
            s.close()

    def detect_drone_ip(self):
        """Auto-detect whether drone is in direct AP mode (192.168.10.1) or on local LAN."""
        # 1. Check direct AP IP first
        if self.ping_test(DEFAULT_DRONE_IP):
            return DEFAULT_DRONE_IP

        # 2. Check if a drone is on current subnet
        local_ip = self.get_local_ip()
        if local_ip != "127.0.0.1":
            found = self.scan_subnet(local_ip, max_hosts=60)
            if found:
                return found[0]

        return DEFAULT_DRONE_IP

    @staticmethod
    def ping_test(ip, port=CMD_PORT, timeout=0.5):
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

    @classmethod
    def scan_subnet(cls, base_ip, max_hosts=254):
        parts = base_ip.split(".")
        if len(parts) != 4:
            return []
        prefix = ".".join(parts[:3])
        found = []
        lock = threading.Lock()

        def probe(target):
            if cls.ping_test(target, timeout=0.3):
                with lock:
                    found.append(target)

        threads = []
        for i in range(1, max_hosts + 1):
            t = threading.Thread(target=probe, args=(f"{prefix}.{i}",), daemon=True)
            threads.append(t)
            t.start()
            if i % 30 == 0:
                time.sleep(0.04)

        for t in threads:
            t.join(timeout=1.0)
        return found

    def send(self, cmd, timeout=None):
        t = timeout or self.timeout
        self.sock.settimeout(t)
        print(f">> {cmd}")
        self.sock.sendto(cmd.encode("utf-8"), (self.drone_ip, CMD_PORT))
        try:
            data, _ = self.sock.recvfrom(1024)
            reply = data.decode("utf-8", errors="replace").strip()
            print(f"<< {reply}")
            return reply
        except socket.timeout:
            print("   (no reply / timeout)")
            return ""

    def enter_sdk_mode(self, max_retries=3):
        print(f"Connecting to drone at {self.drone_ip}:{CMD_PORT}...")
        for i in range(1, max_retries + 1):
            reply = self.send("command", timeout=2.0)
            if "ok" in reply.lower():
                print("[OK] Drone entered SDK mode.\n")
                return True
            time.sleep(0.4)
        print(f"[!] Warning: Drone at {self.drone_ip} did not return 'ok' to SDK command.")
        return False

    def show_hello(self, color="r", hold_s=1.3, loops=1):
        """Displays 'HELLO' letter by letter on the 8x8 matrix display."""
        self.enter_sdk_mode()

        # Set top LED to bright color matching the matrix
        rgb = {"r": "255 0 0", "b": "0 0 255", "p": "255 0 255"}.get(color, "255 0 0")
        self.send(f"EXT led {rgb}", timeout=1.0)

        # Set dot matrix brightness to maximum (255)
        self.send("EXT mled sl 255", timeout=1.0)

        for loop_idx in range(loops):
            if loops > 1:
                print(f"\n--- Pass {loop_idx + 1} of {loops} ---")
            for char in "HELLO":
                print(f"[Matrix] Showing '{char}' in {color}...")
                self.send(f"EXT mled s {color} {char}", timeout=1.0)
                time.sleep(hold_s)
            # Clear or pause between loops
            time.sleep(0.5)

        print("\n[Done] Finished displaying 'HELLO' letter by letter.")

    def set_station_mode(self, ssid, password):
        """Instructs the drone to join a local Wi-Fi / Hotspot."""
        if not self.enter_sdk_mode():
            print("Error: Could not reach drone in SDK mode. Ensure you are connected to the drone AP (TELLO-xxxx or RMTT-xxxx).")
            return False

        cmd = f"ap {ssid} {password}".strip()
        print(f"\nInstructing drone to connect to Wi-Fi SSID: '{ssid}'...")
        reply = self.send(cmd, timeout=4.0)
        if "ok" in reply.lower() or "reboot" in reply.lower():
            print("\n[SUCCESS] Drone accepted Station Mode command!")
            print("The drone will reboot in ~3 seconds and join the network.")
            print(f"Reconnect your PC to '{ssid}' and run: python scripts/drone.py scan")
            return True
        else:
            print(f"\n[!] Unexpected reply from drone: '{reply}'")
            return False

    def query_status(self):
        """Query drone battery, hardware, and versions."""
        self.enter_sdk_mode()
        print("\n=== Drone Telemetry ===")
        battery = self.send("battery?", timeout=1.5)
        hw = self.send("hardware?", timeout=1.5)
        sdk = self.send("sdk?", timeout=1.5)
        sn = self.send("sn?", timeout=1.5)
        wifi_snr = self.send("wifi?", timeout=1.5)

        # Query TT Expansion Kit if available
        ext_ver = self.send("EXT version?", timeout=1.5)
        tof = self.send("EXT tof?", timeout=1.5)

        print("-" * 35)
        print(f"  Battery:        {battery}%")
        print(f"  Hardware:       {hw}")
        print(f"  SDK Version:    {sdk}")
        print(f"  Serial Number:  {sn}")
        print(f"  Wi-Fi SNR:      {wifi_snr}")
        print(f"  TT ESP32 Ver:   {ext_ver or 'N/A'}")
        print(f"  ToF Distance:   {tof or 'N/A'}")
        print("-" * 35)


def main():
    parser = argparse.ArgumentParser(description="DJI RoboMaster TT / Tello Controller")
    parser.add_argument("action", choices=["hello", "sta", "status", "scan"], default="hello", nargs="?",
                        help="Action to perform (default: hello)")
    parser.add_argument("--ip", help="Drone IP address (default: auto-detect)")
    parser.add_argument("--color", choices=["r", "b", "p"], default="r", help="Matrix color: r (red), b (blue), p (purple)")
    parser.add_argument("--hold", type=float, default=1.3, help="Seconds to display each letter (default: 1.3)")
    parser.add_argument("--loops", type=int, default=1, help="Number of times to loop HELLO (default: 1)")
    parser.add_argument("--ssid", default=DEFAULT_SSID, help=f"Wi-Fi SSID for station mode (default: '{DEFAULT_SSID}')")
    parser.add_argument("--password", default=DEFAULT_PASS, help="Wi-Fi password for station mode")

    args = parser.parse_args()

    if args.action == "scan":
        local_ip = DroneController.get_local_ip()
        print(f"Scanning local network {local_ip}/24 for active DJI drones...")
        found = DroneController.scan_subnet(local_ip)
        if DroneController.ping_test(DEFAULT_DRONE_IP):
            found.append(f"{DEFAULT_DRONE_IP} (Direct AP)")
        print("\nScan Results:")
        if found:
            for ip in set(found):
                print(f"  * Found drone at: {ip}")
        else:
            print("  No drones responded. Ensure drone is powered on and connected to this network.")
        return

    drone = DroneController(drone_ip=args.ip)
    try:
        if args.action == "hello":
            drone.show_hello(color=args.color, hold_s=args.hold, loops=args.loops)
        elif args.action == "sta":
            drone.set_station_mode(ssid=args.ssid, password=args.password)
        elif args.action == "status":
            drone.query_status()
    finally:
        drone.close()


if __name__ == "__main__":
    main()
