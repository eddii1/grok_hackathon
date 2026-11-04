"""RoboMaster TT / Tello Live Camera Stream & Broadcaster.

Decodes H.264 video streams on UDP port 11111 using PyAV and OpenCV.
Works in both Direct AP mode (192.168.10.1) and Station Mode (local Wi-Fi).

Usage:
  python scripts/camera_stream_RMTT-306E2E.py
  python scripts/camera_stream_RMTT-306E2E.py 10.37.75.54 10.37.75.120
"""

import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import av
import cv2

CMD_PORT = 8889
VIDEO_PORT = 11111
SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "captures"


def wifi_ipv4():
    """Get active Wi-Fi IPv4 address, ignoring virtual tunnels."""
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


def send_cmd(sock, drone_ip, cmd, timeout=3.0):
    print(f">> {cmd}", flush=True)
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


def find_drone_on_lan(local_ip):
    """Scan local /24 subnet for responding Tello drone."""
    if local_ip.startswith("192.168.10."):
        return "192.168.10.1"

    prefix = ".".join(local_ip.split(".")[:3]) + "."
    print(f"Scanning local network {prefix}0/24 for drone on port 8889...", flush=True)
    found = []
    lock = threading.Lock()

    def probe(i):
        target = prefix + str(i)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.bind((local_ip, 0))
            s.settimeout(0.4)
            s.sendto(b"command", (target, CMD_PORT))
            d, _ = s.recvfrom(1024)
            if d and b"ok" in d.lower():
                with lock:
                    found.append(target)
        except Exception:
            pass
        finally:
            s.close()

    threads = [threading.Thread(target=probe, args=(i,), daemon=True) for i in range(1, 255)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=1.5)

    return found[0] if found else None


def live_broadcast(local_ip, drone_ip):
    print(f"\n{'=' * 65}")
    print(f"STARTING LIVE BROADCAST: Drone={drone_ip}  Local={local_ip}")
    print(f"{'=' * 65}\n", flush=True)

    cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        cmd_sock.bind((local_ip, 0))
    except Exception:
        cmd_sock.bind(("", 0))

    video_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    video_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        video_sock.bind((local_ip, VIDEO_PORT))
    except Exception:
        video_sock.bind(("", VIDEO_PORT))
    video_sock.settimeout(1.0)

    # 1. Initialize SDK mode
    ready = False
    for attempt in range(1, 5):
        reply = send_cmd(cmd_sock, drone_ip, "command", timeout=2.5)
        if "ok" in reply.lower():
            ready = True
            break
        time.sleep(0.3)

    if not ready:
        print("[!] Failed to enter SDK mode. Is the drone powered on and connected?", flush=True)
        video_sock.close()
        cmd_sock.close()
        return 1

    # Query battery
    bat = send_cmd(cmd_sock, drone_ip, "battery?", timeout=1.5) or "N/A"
    print(f"Drone Battery: {bat}%\n", flush=True)

    # 2. Turn on video stream
    send_cmd(cmd_sock, drone_ip, "streamon", timeout=4.0)

    # 3. Create H.264 decoder and OpenCV window
    codec = av.CodecContext.create("h264", "r")
    window_name = f"RoboMaster TT - Live Broadcasting Window [{drone_ip}]"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 960, 720)

    SNAPSHOT_DIR.mkdir(exist_ok=True)
    snapshot_idx = 0
    fps_time = time.time()
    fps_counter = 0
    fps = 0

    print("=" * 65)
    print("LIVE CAMERA WINDOW IS OPEN!")
    print("  * Press 'q' or 'ESC' in the window to quit.")
    print("  * Press 's' to capture a snapshot image.")
    print("=" * 65 + "\n", flush=True)

    try:
        while True:
            try:
                packet_data, _ = video_sock.recvfrom(2048)
            except socket.timeout:
                continue

            try:
                packets = codec.parse(packet_data)
                for packet in packets:
                    frames = codec.decode(packet)
                    for frame in frames:
                        fps_counter += 1
                        if time.time() - fps_time >= 1.0:
                            fps = fps_counter
                            fps_counter = 0
                            fps_time = time.time()

                        img = frame.to_ndarray(format="bgr24")

                        # Telemetry overlay
                        cv2.putText(
                            img,
                            f"RoboMaster TT Live | Bat: {bat}% | FPS: {fps}",
                            (20, 35),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.7,
                            (0, 255, 0),
                            2,
                        )
                        cv2.putText(
                            img,
                            "[q]: Exit | [s]: Snapshot",
                            (20, img.shape[0] - 20),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            (255, 255, 255),
                            1,
                        )
                        cv2.imshow(window_name, img)

            except av.AVError:
                pass

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:
                print("Exit requested by user.", flush=True)
                break
            elif key == ord("s"):
                snapshot_idx += 1
                fn = SNAPSHOT_DIR / f"RMTT-306E2E_snapshot_{snapshot_idx}.jpg"
                cv2.imwrite(str(fn), img)
                print(f"[Snapshot] Saved to {fn}", flush=True)

    except KeyboardInterrupt:
        print("\nStopping live broadcast...", flush=True)
    finally:
        try:
            send_cmd(cmd_sock, drone_ip, "streamoff", timeout=2.0)
        except Exception:
            pass
        video_sock.close()
        cmd_sock.close()
        cv2.destroyAllWindows()
        print("[Done] Broadcasting window closed.", flush=True)

    return 0


def main():
    local_ip = sys.argv[1] if len(sys.argv) > 1 else wifi_ipv4()
    drone_ip = sys.argv[2] if len(sys.argv) > 2 else ""

    if not drone_ip:
        drone_ip = find_drone_on_lan(local_ip) or "192.168.10.1"

    print(f"Local IP: {local_ip}")
    print(f"Drone IP: {drone_ip}")
    return live_broadcast(local_ip, drone_ip)


if __name__ == "__main__":
    sys.exit(main())

