"""Send the one-time station-mode join to the drone.

Connects to 192.168.10.1 and sends 'command' then 'ap Samsung 12345678m'.
"""

import socket
import sys

DRONE = "192.168.10.1"
PORT = 8889
SSID = "Samsung"
PASSWORD = "12345678m"


def main():
    local_ip = sys.argv[1] if len(sys.argv) > 1 else "192.168.10.2"
    print(f"Connecting to drone from local IP: {local_ip}...")
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
            print("STA_FAIL: Drone did not respond to 'command' in SDK mode.", flush=True)
            return 1

        print("Querying drone status...")
        bat = send("battery?", 2)
        sn = send("sn?", 2)
        print(f"Drone SN: {sn}, Battery: {bat}%")

        # Send AP command
        reply = send(f"ap {SSID} {PASSWORD}", 6, label=f"ap {SSID} ****")
        print(f"<< {reply or '(empty)'}", flush=True)
        if "ok" in reply.lower() or "reboot" in reply.lower():
            print("STA_OK: Drone accepted Station Mode command! It will reboot onto 'Samsung'.", flush=True)
            return 0
        else:
            print("STA_FAIL: Drone rejected station command.", flush=True)
            return 1
    finally:
        sock.close()


if __name__ == "__main__":
    sys.exit(main())
