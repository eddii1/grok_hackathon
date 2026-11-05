#!/usr/bin/env bash
# Single player: drone server + frontend. Ctrl+C stops everything.  DRONE_IP=... to override.
source "$(dirname "$0")/common.sh"
start_drone
start_frontend
echo; echo "OPEN: http://localhost:5173/"
wait
