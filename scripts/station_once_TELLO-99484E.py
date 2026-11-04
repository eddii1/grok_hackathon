"""One-time station-mode join for TELLO-99484E."""

import socket
import sys

DRONE = "192.168.10.1"
PORT = 8889
SSID = "Samsung"
PASSWORD = "12345678m"
DRONE_CODE = "TELLO-99484E"


def main():
    local_ip = sys.argv[1] if len(sys.argv) > 1 else "192.168.10.2"
    print(f"Connecting to {DRONE_CODE} from local IP: {local_ip}...", flush=True)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind((local_ip, 0))
    except Exception:
        sock.bind(("", 0))

    def send(cmd, timeout, label=None):
        print(f">> {label or cmd}", flush=True)
        sock.sendto(cmd.encode("utf-8"), (DRONE, PORT))
        sock.settimeout(timeout)
        try:
            data, _ = sock.recvfrom(2048)
        except socket.timeout:
            print("   (no reply)", flush=True)
            return ""
        return data.decode("utf-8", errors="replace").strip("\x00\r\n ")

    try:
        ready = False
        for i in range(1, 6):
            print(f"Attempt {i}: Sending 'command'...")
            reply = send("command", 3)
            print(f"<< {reply or '(empty)'}", flush=True)
            if "ok" in reply.lower() and "error" not in reply.lower():
                ready = True
                break

        if not ready:
            print(f"STA_FAIL: {DRONE_CODE} did not respond to 'command'.", flush=True)
            return 1

        print("Querying drone status...")
        bat = send("battery?", 2)
        sn = send("sn?", 2)
        print(f"{DRONE_CODE} SN: {sn}, Battery: {bat}%")

        reply = send(f"ap {SSID} {PASSWORD}", 6, label=f"ap {SSID} ****")
        print(f"<< {reply or '(empty)'}", flush=True)
        if "ok" in reply.lower() or "reboot" in reply.lower():
            print(f"STA_OK: {DRONE_CODE} accepted Station Mode command!", flush=True)
            return 0
        return 1
    finally:
        sock.close()


if __name__ == "__main__":
    sys.exit(main())
