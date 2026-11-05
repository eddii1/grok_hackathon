"""
Interactive Wi-Fi Connection Tool for DJI RoboMaster EP Rover.
Generates the Samsung Wi-Fi QR code and listens for the rover connecting to the hotspot.
"""

import os
import sys
import time
import socket
import subprocess
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rover.rover_controller import rover_ctrl

SSID = "Samsung"
PASSWORD = "12345678m"


def main():
    print("=" * 65)
    print("  DJI RoboMaster EP Rover - Wi-Fi Setup Assistant")
    print(f"  Target Network: SSID = '{SSID}' | Password = '{PASSWORD}'")
    print("=" * 65)

    # 1. Generate QR Code
    print("\n[Step 1] Generating official RoboMaster Wi-Fi QR Code...")
    qr_text, qr_path = rover_ctrl.generate_samsung_qr(ssid=SSID, password=PASSWORD)
    print(f"  -> Encrypted QR Payload: {qr_text}")
    print(f"  -> Saved QR Code Image: {qr_path}")

    # 2. Open QR Code for user to scan
    print("\n[Step 2] Displaying QR code on screen...")
    try:
        os.startfile(qr_path)
        print("  -> QR Code opened in your default image viewer!")
    except Exception as e:
        print(f"  -> Could not automatically open image: {e}")
        print(f"     Please manually open: {qr_path}")

    # 3. Instructions
    print("\n" + "-" * 65)
    print("INSTRUCTIONS TO CONNECT ROVER:")
    print(" 1. Ensure the rover is powered ON.")
    print(" 2. Slide the controller connection switch to 'ROUTER MODE' (STA mode,")
    print("    icon showing interconnected nodes/router, NOT the direct Wi-Fi AP icon).")
    print(" 3. Aim the rover's camera directly at the QR Code image on your screen.")
    print(" 4. Press the small connection button next to the controller switch once.")
    print(" 5. You should hear the rover emit a confirmation chime/beep!")
    print("-" * 65)

    # 4. Listen for rover broadcast
    print(f"\n[Step 3] Listening for rover broadcast on Wi-Fi '{SSID}' (timeout: 60s)...")
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("0.0.0.0", 45678))
        s.settimeout(60.0)
        start_t = time.time()
        while time.time() - start_t < 60:
            try:
                data, addr = s.recvfrom(1024)
                if addr and addr[0]:
                    rover_ip = addr[0]
                    print(f"\n>>> SUCCESS! Detected Rover broadcast from IP: {rover_ip} <<<")
                    print("Testing initialization...")
                    if rover_ctrl.connect(target_ip=rover_ip):
                        print(f"Rover successfully connected and streaming! Battery: {rover_ctrl.battery_level}%")
                    return 0
            except socket.timeout:
                print(".", end="", flush=True)
                # Fallback: scan local subnet for port 40923
                found_ip = rover_ctrl.scan_for_rover_ip(timeout=1.0)
                if found_ip:
                    print(f"\n>>> SUCCESS! Detected Rover on local subnet at: {found_ip} <<<")
                    if rover_ctrl.connect(target_ip=found_ip):
                        print(f"Rover successfully connected and streaming! Battery: {rover_ctrl.battery_level}%")
                    return 0
        print("\nTimed out waiting for rover broadcast.")
        print("Tip: You can also use the Web Dashboard to view status and trigger connection anytime!")
    finally:
        s.close()

    return 1


if __name__ == "__main__":
    sys.exit(main())

