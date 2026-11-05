"""Scan local network for Tello drones and display their status."""

import json
import os
import socket
import subprocess
import sys
import threading
import time

CMD_PORT = 8889


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


def probe_drone(local_ip, target_ip, results, lock):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.bind((local_ip, 0))
        s.settimeout(0.6)
        s.sendto(b"command", (target_ip, CMD_PORT))
        data, _ = s.recvfrom(1024)
        if data and b"ok" in data.lower():
            bat = ""
            sn = ""
            try:
                s.settimeout(0.8)
                s.sendto(b"battery?", (target_ip, CMD_PORT))
                b_data, _ = s.recvfrom(1024)
                bat = b_data.decode("utf-8", errors="replace").strip()
            except Exception:
                pass
            try:
                s.settimeout(0.8)
                s.sendto(b"sn?", (target_ip, CMD_PORT))
                sn_data, _ = s.recvfrom(1024)
                sn = sn_data.decode("utf-8", errors="replace").strip()
            except Exception:
                pass

            with lock:
                results.append({"ip": target_ip, "battery": bat, "sn": sn})
    except Exception:
        pass
    finally:
        s.close()


def scan_network():
    local = wifi_ipv4()
    if not local or local == "0.0.0.0" or local.startswith("127."):
        print(f"Invalid local IP: {local}")
        return []

    prefix = ".".join(local.split(".")[:3]) + "."
    print(f"Scanning {prefix}0/24 from local IP {local}...", flush=True)

    results = []
    lock = threading.Lock()
    threads = []
    for i in range(1, 255):
        t = threading.Thread(
            target=probe_drone, args=(local, prefix + str(i), results, lock)
        )
        t.daemon = True
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=2.0)

    return results


if __name__ == "__main__":
    drones = scan_network()
    if drones:
        print(f"Found {len(drones)} drone(s):")
        for d in drones:
            print(
                f"  IP: {d['ip']} | SN: {d['sn']} | Battery: {d['battery']}%",
                flush=True,
            )
            with open(
                os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), ".drone-ip"
                ),
                "w",
            ) as f:
                f.write(d["ip"] + "\n")
            if d["sn"]:
                with open(
                    os.path.join(
                        os.path.dirname(os.path.abspath(__file__)),
                        f".drone-ip-{d['sn']}",
                    ),
                    "w",
                ) as f:
                    f.write(d["ip"] + "\n")
        sys.exit(0)
    else:
        print("No drones responded.")
        sys.exit(1)

