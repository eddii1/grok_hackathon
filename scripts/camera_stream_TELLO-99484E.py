"""RoboMaster TT / Tello Live Camera Stream & Broadcaster for TELLO-99484E.

Decodes H.264 video streams on UDP port 11111 using PyAV and OpenCV.
Works in both Direct AP mode (192.168.10.1) and Station Mode (local Wi-Fi).

Usage:
  python scripts/camera_stream_TELLO-99484E.py
  python scripts/camera_stream_TELLO-99484E.py <LOCAL_IP> <DRONE_IP>
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
DRONE_CODE = "TELLO-99484E"
SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "captures"


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
    if local_ip.startswith("192.168.10."):
        return "192.168.10.1"

    prefix = ".".join(local_ip.split(".")[:3]) + "."
    print(f"Scanning local network {prefix}0/24 for {DRONE_CODE}...", flush=True)
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
    print(f"STARTING LIVE BROADCAST: [{DRONE_CODE}] Drone={drone_ip}  Local={local_ip}")
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

    # Enter SDK mode
    ready = False
    for attempt in range(1, 6):
        reply = send_cmd(cmd_sock, drone_ip, "command", timeout=2.5)
        if "ok" in reply.lower():
            ready = True
            break
        time.sleep(0.3)

    if not ready:
        print(f"[!] Failed to enter SDK mode on {DRONE_CODE} ({drone_ip}).", flush=True)
        video_sock.close()
        cmd_sock.close()
        return 1

    bat = send_cmd(cmd_sock, drone_ip, "battery?", timeout=1.5) or "N/A"
    print(f"Drone Battery: {bat}%\n", flush=True)

    # Enable stream
    send_cmd(cmd_sock, drone_ip, "streamon", timeout=4.0)

    codec = av.CodecContext.create("h264", "r")
    window_name = f"Tello Live Broadcast [{DRONE_CODE} | {drone_ip}]"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 960, 720)

    SNAPSHOT_DIR.mkdir(exist_ok=True)
    snapshot_idx = 0
    fps_time = time.time()
    fps_counter = 0
    fps = 0

    print("=" * 65)
    print("LIVE BROADCASTING WINDOW ACTIVE")
    print(f"  * Showing video stream from {DRONE_CODE}")
    print("  * Press 'q' or 'ESC' in the window to quit.")
    print("  * Press 's' to save snapshot image.")
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

                        cv2.putText(
                            img,
                            f"{DRONE_CODE} Live | Bat: {bat}% | FPS: {fps}",
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
                fn = SNAPSHOT_DIR / f"{DRONE_CODE}_snapshot_{snapshot_idx}.jpg"
                cv2.imwrite(str(fn), img)
                print(f"[Snapshot] Saved to {fn}", flush=True)

    except KeyboardInterrupt:
        print("\nStopping camera stream...", flush=True)
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

    print(f"[{DRONE_CODE}] Local IP: {local_ip} | Drone IP: {drone_ip}")
    return live_broadcast(local_ip, drone_ip)


if __name__ == "__main__":
    sys.exit(main())
