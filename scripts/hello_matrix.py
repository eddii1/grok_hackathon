"""RoboMaster TT (Tello Talent) Controller.

Spell 'HELLO' letter-by-letter on the 8x8 dot-matrix display and connect
the drone to Wi-Fi / Hotspot (Station Mode).

Usage:
  # 1. Takeoff to 1m, show HELLO on matrix, and land:
  python scripts/hello_matrix.py --fly

  # 2. Show 'HELLO' on desk without taking off:
  python scripts/hello_matrix.py

  # 3. Connect drone to 'Samsung' hotspot (while on drone Wi-Fi):
  python scripts/hello_matrix.py --sta
"""

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

# Phone hotspot (single-word SSID, WPA2-Personal)
HOTSPOT_SSID = "Samsung"
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


def send_cmd(sock, drone_ip, cmd, timeout=COMMAND_TIMEOUT_S, label=None):
    print(f">> {label or cmd}")
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
    ssid = ssid.strip()
    password = password.strip()
    if (" " in ssid) or (" " in password):
        print(
            "[!] The drone's `ap` command cannot join a network whose name or "
            "password contains a space.\n"
            f"    '{ssid}' will not work. Rename the phone hotspot to one word "
            "(for example S24Ultra), put that name in HOTSPOT_SSID, then run "
            "this again while the PC is joined to the drone's TELLO- Wi-Fi."
        )
        return False

    if not enter_sdk_mode(sock, drone_ip):
        return False

    cmd = f"ap {ssid} {password}"
    print(f"\nInstructing drone to connect to Wi-Fi: '{ssid}'...")
    reply = send_cmd(sock, drone_ip, cmd, timeout=4.0, label=f"ap {ssid} ****")

    if "ok" in reply.lower() or "reboot" in reply.lower():
        print("\n[SUCCESS] Drone accepted station mode! It will reboot in ~3s and join the network.")
        print(f"Ensure your PC is connected to '{ssid}', then run: python scripts/hello_matrix.py")
        return True
    else:
        print(f"\n[!] Drone response: '{reply}'")
        return False


def show_hello(sock, drone_ip, color, hold_s, loops):
    """Spell HELLO letter-by-letter on the 8x8 dot-matrix display."""
    if not enter_sdk_mode(sock, drone_ip):
        print(
            "[!] The matrix was not changed. The drone did not answer.\n"
            "    Join its TELLO- Wi-Fi (it is 192.168.10.1), or put it on this "
            "same hotspot first with --sta.\n"
            "    If TELLO- is missing, hold the drone power button for 5 seconds "
            "until the light flashes yellow. That restores its own Wi-Fi."
        )
        return False

    hw = send_cmd(sock, drone_ip, "hardware?", timeout=2.0)
    if hw and "RMTT" not in hw.upper() and "TELLO" in hw.upper():
        print(
            "[!] hardware? did not report the TT expansion board (RMTT). "
            "The 8x8 matrix is on that board; a plain Tello has no matrix."
        )

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
    return True
    return True
    return True
    return True


def fly_and_show_hello(sock, drone_ip, color, hold_s):
    """Takeoff to ~1m, display HELLO on matrix while hovering, then land safely."""
    if not enter_sdk_mode(sock, drone_ip):
        print("[!] Drone did not respond to SDK mode command. Cannot fly.")
        return False

    # Safety check: Battery
    bat_str = send_cmd(sock, drone_ip, "battery?", timeout=2.0)
    try:
        bat = int(bat_str.strip())
        print(f"Drone battery: {bat}%")
        if bat < 15:
            print(f"[!] Battery too low ({bat}%) for safe flight. Please charge battery.")
            return False
    except Exception:
        print(f"Warning: Could not verify battery percentage ('{bat_str}').")

    # Verify hardware
    send_cmd(sock, drone_ip, "hardware?", timeout=2.0)

    # Pre-configure LED and matrix display before takeoff
    rgb = {"r": "255 0 0", "b": "0 0 255", "p": "255 0 255"}.get(color, "255 0 0")
    send_cmd(sock, drone_ip, f"EXT led {rgb}", timeout=1.0)
    send_cmd(sock, drone_ip, "EXT mled sl 255", timeout=1.0)

    print("\n>>> TAKING OFF (climbing to ~1m hover)...")
    takeoff_reply = send_cmd(sock, drone_ip, "takeoff", timeout=12.0)
    if "ok" not in takeoff_reply.lower():
        print(f"[!] Takeoff failed: '{takeoff_reply}'. Aborting flight.")
        return False

    try:
        print("\n>>> HOVERING AT ~1m: Spelling HELLO letter-by-letter on matrix...")
        for letter in MESSAGE:
            print(f"[Matrix in Flight] Showing '{letter}' in {color}...")
            send_cmd(sock, drone_ip, f"EXT mled s {color} {letter}", timeout=1.0)
            time.sleep(hold_s)

        print("\n[Done] Message complete while hovering.")
    finally:
        print("\n>>> LANDING DRONE...")
        land_reply = send_cmd(sock, drone_ip, "land", timeout=10.0)
        print(f"Landing status: {land_reply}")
        return True


def stream_camera(drone_ip):
    """Start live video streaming from the Tello camera and display in an OpenCV broadcasting window."""
    try:
        import cv2
        from djitellopy import Tello
    except ImportError as e:
        print(f"[!] Missing dependency for camera streaming: {e}")
        print("    Run: pip install opencv-python djitellopy")
        return False

    print(f"\n>>> Connecting to drone at {drone_ip} for camera feed...")
    tello = Tello(host=drone_ip, retry_count=2)
    try:
        tello.connect(wait_for_state=False)
        print(">>> Starting video stream ('streamon')...")
        tello.streamon()
        frame_reader = tello.get_frame_read()

        print("\n" + "=" * 60)
        print("LIVE BROADCASTING WINDOW ACTIVE")
        print("  * Showing live camera feed from RoboMaster TT")
        print("  * Press 'q' or 'ESC' on the video window to stop.")
        print("  * Press 's' to take a snapshot photo.")
        print("=" * 60 + "\n")

        window_name = f"RoboMaster TT - Live Camera ({drone_ip})"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 960, 720)

        snapshot_count = 0
        last_frame_time = time.time()
        while True:
            frame = frame_reader.frame
            if frame is not None and frame.size > 0:
                last_frame_time = time.time()
                display_frame = frame.copy()
                # Telemetry header overlay
                cv2.putText(
                    display_frame,
                    f"RoboMaster TT Live | {drone_ip}",
                    (20, 35),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2,
                )
                cv2.imshow(window_name, display_frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:
                print("Closing camera window...")
                break
            elif key == ord("s") and frame is not None:
                snapshot_count += 1
                fn = f"snapshot_{snapshot_count}.jpg"
                cv2.imwrite(fn, frame)
                print(f"[Snapshot] Saved {fn}")

            # Safety check if stream froze for >10s
            if time.time() - last_frame_time > 10.0:
                print("Warning: No video frames received for 10s.")

    except KeyboardInterrupt:
        print("\nStopping camera stream...")
    except Exception as e:
        print(f"[!] Camera stream error: {e}")
    finally:
        try:
            tello.streamoff()
        except Exception:
            pass
        cv2.destroyAllWindows()
        try:
            tello.end()
        except Exception:
            pass
        print("[Done] Camera stream stopped.")
        return True


DRONE_IP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".drone-ip")


def wifi_ipv4():
    """IPv4 on the Wi-Fi adapter. Ignores the VPN, which would hide the hotspot."""
    try:
        out = subprocess.check_output(
            ["netsh", "interface", "ip", "show", "address", "name=Wi-Fi"],
            text=True,
            errors="replace",
        )
    except (OSError, subprocess.CalledProcessError):
        return get_wifi_ip_to("8.8.8.8")
    for line in out.splitlines():
        if "IP Address" in line and ":" in line:
            ip = line.split(":", 1)[1].strip()
            if ip and not ip.startswith("169.254."):
                return ip
    return get_wifi_ip_to("8.8.8.8")


def probe_drone(local_ip, drone_ip, timeout=0.6):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        if local_ip and local_ip != "0.0.0.0":
            s.bind((local_ip, 0))
        s.settimeout(timeout)
        s.sendto(b"command", (drone_ip, CMD_PORT))
        data, addr = s.recvfrom(1024)
        if data:
            return addr[0]
    except OSError:
        return None
    finally:
        s.close()
    return None


def remember_drone(ip):
    try:
        with open(DRONE_IP_FILE, "w", encoding="utf-8") as handle:
            handle.write(ip + "\n")
    except OSError:
        pass


def remembered_drone():
    try:
        with open(DRONE_IP_FILE, encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return ""


def scan_for_drone_on_lan():
    """Look for any drone responding on the current local network."""
    local = wifi_ipv4()
    if not local or local == "0.0.0.0" or local.startswith("127."):
        return None

    cached = remembered_drone()
    if cached:
        found = probe_drone(local, cached, timeout=0.8)
        if found:
            print(f"Using drone at {found}")
            return found

    prefix = ".".join(local.split(".")[:3])
    print(f"Scanning local network {prefix}.0/24 for connected drone...")
    found = []
    lock = threading.Lock()

    def probe(ip):
        hit = probe_drone(local, ip, timeout=0.5)
        if hit:
            with lock:
                found.append(hit)

    threads = []
    for i in range(1, 255):
        t = threading.Thread(target=probe, args=(f"{prefix}.{i}",), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=2.0)

    if not found:
        return None
    remember_drone(found[0])
    return found[0]


def main():
    parser = argparse.ArgumentParser(description="RoboMaster TT Matrix & Wi-Fi Station Mode")
    parser.add_argument("--sta", action="store_true", help="Connect drone to Wi-Fi / phone hotspot")
    parser.add_argument("--ssid", default=HOTSPOT_SSID, help=f"Wi-Fi SSID for station mode (default: '{HOTSPOT_SSID}')")
    parser.add_argument("--password", default=HOTSPOT_PASS, help="Wi-Fi password for station mode")
    parser.add_argument("--ip", help="Drone IP address (default: auto-detect)")
    parser.add_argument("--color", choices=["r", "b", "p"], default=COLOR, help="Color: r (red), b (blue), p (purple)")
    parser.add_argument("--hold", type=float, default=HOLD_S, help="Seconds per letter")
    parser.add_argument("--loops", type=int, default=1, help="Number of repetitions")
    parser.add_argument("--fly", action="store_true", help="Fly drone to ~1m, display HELLO on matrix, then land safely")
    parser.add_argument("--camera", action="store_true", help="Open live broadcasting camera window from the drone")

    args = parser.parse_args()

    drone_ip = args.ip
    if not drone_ip:
        # Check if drone is on local subnet first
        lan_ip = scan_for_drone_on_lan()
        if lan_ip:
            print(f"[Auto-detect] Found drone on LAN at: {lan_ip}")
            remember_drone(lan_ip)
            drone_ip = lan_ip
        else:
            # The drone AP has no internet, so a route to 8.8.8.8 does not
            # prove we are on it. 192.168.10.1 is on-link only on TELLO-/RMTT-.
            local = get_wifi_ip_to(DEFAULT_DRONE_IP)
            on_drone_ap = local.startswith("192.168.10.")
            if not on_drone_ap:
                sys.exit(
                    "No drone answered on this network, and this PC is not on a "
                    "TELLO- Wi-Fi.\n"
                    "The matrix commands were not sent.\n"
                    "Turn the drone on. If its TELLO- network does not appear, "
                    "hold the power button for 5 seconds until the light flashes "
                    "yellow, then join that Wi-Fi and run this again.\n"
                    "To use the phone hotspot afterwards, rename it to one word "
                    "with no spaces and run: python scripts/hello_matrix.py --sta"
                )
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
        if args.camera:
            sock.close()
            stream_camera(drone_ip)
        elif args.sta:
            ok = set_station_mode(sock, drone_ip, args.ssid, args.password)
            if not ok:
                sys.exit(1)
        elif args.fly:
            fly_and_show_hello(sock, drone_ip, args.color, args.hold)
        else:
            ok = show_hello(sock, drone_ip, args.color, args.hold, args.loops)
            if not ok:
                sys.exit(1)
    finally:
        try:
            sock.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
