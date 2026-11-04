"""Take off, climb 1 m, spell HELLO, land. Run only while joined to the drone Wi-Fi."""

import socket
import sys
import time

DRONE_IP = "192.168.10.1"
PORT = 8889


def local_ip():
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect((DRONE_IP, PORT))
        return probe.getsockname()[0]
    finally:
        probe.close()


def main():
    local = local_ip()
    print(f"local {local}", flush=True)
    if not local.startswith("192.168.10."):
        sys.exit("This PC is not on the drone Wi-Fi.")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((local, 0))
    airborne = False

    def send(cmd, timeout):
        print(f">> {cmd}", flush=True)
        sock.sendto(cmd.encode("utf-8"), (DRONE_IP, PORT))
        sock.settimeout(timeout)
        try:
            data, _ = sock.recvfrom(2048)
        except socket.timeout:
            print("   (no reply)", flush=True)
            return ""
        reply = data.decode("utf-8", errors="replace").strip()
        print(f"<< {reply}", flush=True)
        return reply

    try:
        ready = False
        for _ in range(5):
            reply = send("command", 3)
            if "ok" in reply.lower() and "error" not in reply.lower():
                ready = True
                break
            time.sleep(0.3)
        if not ready:
            sys.exit("The drone did not enter SDK mode.")

        battery = "".join(ch for ch in send("battery?", 4) if ch.isdigit())
        if battery and int(battery) < 15:
            sys.exit(f"Battery is {battery}%. Not taking off.")

        if "ok" not in send("takeoff", 20).lower():
            sys.exit("Takeoff was refused.")
        airborne = True

        if "ok" not in send("up 100", 15).lower():
            print("Climb was refused.", flush=True)
            return

        send("EXT mled sl 255", 1.5)
        for letter in "HELLO":
            send(f"EXT mled s r {letter}", 1.5)
            time.sleep(0.8)
    finally:
        if airborne:
            send("land", 20)
        sock.close()


if __name__ == "__main__":
    main()
