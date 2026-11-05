#!/usr/bin/env bash
# Put the RMTT/Tello drone on your phone hotspot (station mode), then return this Mac to the hotspot.
# Usage: HOTSPOT_PASS=... run/drone_join.sh [HOTSPOT_SSID] [DRONE_SSID]
#   1. Power the drone on in direct mode (its own RMTT-xxxx Wi-Fi is visible).
#   2. Run this. It joins the drone's Wi-Fi, sends `ap <ssid> <pass>`, and rejoins the hotspot.
#   3. The drone reboots onto the hotspot (~20 s). Then: DRONE_IP=auto run/single.sh  (or run/multi.sh)
set -e
HOTSPOT_SSID="${1:-AndroidAP}"
DRONE_SSID="${2:-RMTT-306E2E}"
: "${HOTSPOT_PASS:?set HOTSPOT_PASS=<hotspot password>}"
IF=$(networksetup -listallhardwareports | awk '/Wi-Fi/{getline; print $2}')

echo "joining drone Wi-Fi $DRONE_SSID on $IF..."
networksetup -setairportnetwork "$IF" "$DRONE_SSID"
for _ in $(seq 20); do ping -c1 -t1 192.168.10.1 >/dev/null 2>&1 && break; sleep 1; done

python3 - "$HOTSPOT_SSID" "$HOTSPOT_PASS" <<'PY'
import socket, sys
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(5)
for cmd in ("command", f"ap {sys.argv[1]} {sys.argv[2]}"):
    s.sendto(cmd.encode(), ("192.168.10.1", 8889))
    try:
        print(cmd.split()[0], "->", s.recv(1024).decode(errors="replace").strip())
    except socket.timeout:
        sys.exit(f"no reply to '{cmd.split()[0]}': is the Mac on {sys.argv[0]}'s drone Wi-Fi and the drone in direct mode?")
PY

echo "rejoining $HOTSPOT_SSID..."
networksetup -setairportnetwork "$IF" "$HOTSPOT_SSID" "$HOTSPOT_PASS"
echo "done. The drone reboots onto $HOTSPOT_SSID in ~20 s. Then run:  DRONE_IP=auto run/single.sh"
