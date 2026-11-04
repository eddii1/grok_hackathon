"""Find the drone on the current Wi-Fi and save one camera frame. Does not fly."""

import socket
import sys
import threading
import time
from pathlib import Path

import av
import cv2

PORT = 8889
VIDEO_PORT = 11111
OUT = Path(__file__).with_name("camera_test_RMTT-306E2E.jpg")


def wifi_ipv4():
    import subprocess

    out = subprocess.check_output(
        ["netsh", "interface", "ip", "show", "address", "name=Wi-Fi"],
        text=True,
        errors="replace",
    )
    for line in out.splitlines():
        if "IP Address" in line and ":" in line:
            ip = line.split(":", 1)[1].strip()
            if ip and not ip.startswith("169.254.") and not ip.startswith("192.168.10."):
                return ip
    return ""


def probe(local, ip, timeout=0.5):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind((local, 0))
        sock.settimeout(timeout)
        sock.sendto(b"command", (ip, PORT))
        data, addr = sock.recvfrom(1024)
        if data and b"ok" in data.lower():
            return addr[0]
    except OSError:
        return None
    finally:
        sock.close()
    return None


def find_drone(local):
    prefix = ".".join(local.split(".")[:3]) + "."
    found = []
    lock = threading.Lock()

    def one(i):
        hit = probe(local, prefix + str(i))
        if hit:
            with lock:
                found.append(hit)

    threads = [threading.Thread(target=one, args=(i,), daemon=True) for i in range(1, 255)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2.0)
    return found[0] if found else None


def send(sock, drone, cmd, timeout):
    print(f">> {cmd}", flush=True)
    sock.sendto(cmd.encode("utf-8"), (drone, PORT))
    sock.settimeout(timeout)
    try:
        data, _ = sock.recvfrom(2048)
    except socket.timeout:
        print("   (no reply)", flush=True)
        return ""
    reply = data.decode("utf-8", errors="replace").strip("\x00\r\n ")
    print(f"<< {reply}", flush=True)
    return reply


def save_frame(local, drone):
    video = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    video.bind((local, VIDEO_PORT))
    video.settimeout(1.0)
    cmd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    cmd.bind((local, 0))
    try:
        ready = False
        for _ in range(4):
            reply = send(cmd, drone, "command", 3)
            if "ok" in reply.lower():
                ready = True
                break
        if not ready:
            print("CAMERA_FAIL sdk", flush=True)
            return 1
        reply = send(cmd, drone, "streamon", 8)
        if "ok" not in reply.lower() and "error" in reply.lower():
            print("CAMERA_FAIL streamon", flush=True)
            return 1

        codec = av.CodecContext.create("h264", "r")
        frame = None
        deadline = time.time() + 10
        packets = 0
        while time.time() < deadline and frame is None:
            try:
                data, _ = video.recvfrom(2048)
            except socket.timeout:
                continue
            packets += 1
            try:
                decoded = codec.decode(av.Packet(data))
            except av.AVError:
                continue
            for item in decoded:
                frame = item.to_ndarray(format="bgr24")
                break
        print(f"video_packets {packets}", flush=True)
        if frame is None:
            print("CAMERA_FAIL no frame", flush=True)
            return 1

        height, width = frame.shape[:2]
        ok = cv2.imwrite(str(OUT), frame)
        mean = frame.mean(axis=(0, 1))
        std = float(frame.std())
        blue, green, red = (float(x) for x in mean)
        kind = "real"
        if std < 8:
            kind = "blank"
        elif green > red + 25 and green > blue + 25 and green > 40:
            kind = "green"
        print(
            f"FRAME {width}x{height} bytes={OUT.stat().st_size if ok else 0} "
            f"std={std:.1f} bgr=({blue:.0f},{green:.0f},{red:.0f}) kind={kind} "
            f"path={OUT}",
            flush=True,
        )
        return 0 if ok else 1
    finally:
        try:
            send(cmd, drone, "streamoff", 4)
        except OSError as exc:
            print(f"streamoff failed: {exc}", flush=True)
        video.close()
        cmd.close()


def main():
    local = sys.argv[1] if len(sys.argv) > 1 else wifi_ipv4()
    drone = sys.argv[2] if len(sys.argv) > 2 else ""
    if not drone:
        drone = find_drone(local) or ""
    if not drone:
        print("DRONE_NONE", flush=True)
        return 1
    print(f"DRONE_IP {drone}", flush=True)
    print(f"LOCAL {local}", flush=True)
    return save_frame(local, drone)


if __name__ == "__main__":
    sys.exit(main())
