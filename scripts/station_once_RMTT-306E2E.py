"""Send the one-time station-mode join. Reads the hotspot secret from hello_matrix_RMTT-306E2E.py."""

import re
import socket
import sys
from pathlib import Path

SRC = Path(__file__).with_name("hello_matrix_RMTT-306E2E.py")
text = SRC.read_text(encoding="utf-8")
SSID = re.search(r'HOTSPOT_SSID = "([^"]*)"', text).group(1)
PASSWORD = re.search(r'HOTSPOT_PASS = "([^"]*)"', text).group(1)
DRONE = "192.168.10.1"
PORT = 8889


def main():
    local_ip = sys.argv[1]
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((local_ip, 0))

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
        for _ in range(5):
            reply = send("command", 3)
            print(f"<< {reply or '(empty)'}", flush=True)
            if "ok" in reply.lower() and "error" not in reply.lower():
                ready = True
                break
        if not ready:
            print("STA_FAIL no sdk", flush=True)
            return 1

        stored = send("ap?", 3)
        parts = stored.split()
        ssid_ok = SSID in parts
        pass_ok = PASSWORD in parts
        print(
            f"<< ap? stored_ssid={parts[0] if parts else '(none)'} "
            f"ssid_match={'yes' if ssid_ok else 'no'} "
            f"password_match={'yes' if pass_ok else 'no'}",
            flush=True,
        )

        reply = send(f"ap {SSID} {PASSWORD}", 6, label=f"ap {SSID} ****")
        print(f"<< {reply or '(empty)'}", flush=True)
        if "ok" in reply.lower() or "reboot" in reply.lower():
            print("STA_OK", flush=True)
            return 0
        print("STA_FAIL", flush=True)
        return 1
    finally:
        sock.close()


if __name__ == "__main__":
    sys.exit(main())
