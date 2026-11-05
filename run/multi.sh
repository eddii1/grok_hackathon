#!/usr/bin/env bash
# Multiplayer: drone + rover bridge (auto-connect, full reconnect watchdog) + team service + frontend.
# Ctrl+C stops everything.  DRONE_IP=... ROVER_IP=... to override.
source "$(dirname "$0")/common.sh"
ROVER=http://127.0.0.1:5001

rover_connect() {
  curl -s -m 20 -X POST $ROVER/api/wifi/connect -H 'Content-Type: application/json' \
    -d "{\"ip\":\"$ROVER_IP\",\"conn_type\":\"sta\"}" >/dev/null
}

rover_alive() {  # CONNECTED and odometry updated in the last 5 s (status alone stays CONNECTED on a dead session)
  curl -s -m 3 $ROVER/api/fleet | python3 -c \
    'import json,sys; d=json.load(sys.stdin); sys.exit(not (d["status"]=="CONNECTED" and d["server_time"]-d["pose_time"]<5))'
}

watchdog() {  # full reconnect: drop the dead SDK session and connect again
  while sleep 5; do
    rover_alive && continue
    sleep 5; rover_alive && continue  # ignore a single slow sample
    echo "$(date +%T) rover session dead -> full reconnect"
    curl -s -m 15 -X POST $ROVER/api/wifi/disconnect >/dev/null
    sleep 2
    rover_connect
    wait_for "rover reconnect" 30 rover_alive || echo "$(date +%T) reconnect failed; power-cycle the rover if this repeats"
  done
}

start_drone
bg rover "$ROOT" env ROVER_PORT=5001 rover/.venv/bin/python rover/app.py
wait_for "rover bridge" 60 curl -sf -m 2 $ROVER/api/status
rover_connect
wait_for "rover connection" 40 rover_alive
watchdog > >(tee -a "$LOGS/rover-watchdog.log") 2>&1 &
PIDS+=($!)
bg multi "$ROOT/backend" uv run fleet-multiplayer --drone-url http://127.0.0.1:8001 --rover-url $ROVER
wait_for "team service" 60 curl -sf -m 2 http://127.0.0.1:8002/state
start_frontend
echo; echo "OPEN: http://localhost:5173/?multi"
wait
