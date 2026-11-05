# Shared helpers for run/single.sh and run/multi.sh. Logs go to run/logs/.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOGS="$ROOT/run/logs"; mkdir -p "$LOGS"
DRONE_IP="${DRONE_IP:-10.224.117.218}"
ROVER_IP="${ROVER_IP:-10.224.117.67}"
PIDS=()

cleanup() { echo; echo "stopping..."; trap - INT TERM; kill "${PIDS[@]}" 2>/dev/null; kill 0 2>/dev/null; exit 0; }  # kill 0: whole group, incl. vite/uv children
trap cleanup INT TERM

bg() {  # bg <name> <dir> <cmd...>: run in background, log to run/logs/<name>.log
  local name=$1 dir=$2; shift 2
  (cd "$dir" && exec "$@") >"$LOGS/$name.log" 2>&1 &
  PIDS+=($!); LAST_PID=$!; LAST_LOG="$LOGS/$name.log"; echo "started $name (log: run/logs/$name.log)"
}

wait_for() {  # wait_for <label> <seconds> <test cmd...>; gives up at once if the last bg process died
  local label=$1 secs=$2 pid=${WAIT_PID:-} log=${WAIT_LOG:-}; shift 2
  for _ in $(seq "$secs"); do
    "$@" >/dev/null 2>&1 && { echo "$label ready"; return 0; }
    if [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; then
      echo "ERROR: $label crashed on startup:"; tail -n 4 "$log" | sed 's/^/    /'; return 1
    fi
    sleep 1
  done
  echo "WARNING: $label not ready after ${secs}s - check run/logs"; return 1
}

start_drone() {
  bg drone "$ROOT/backend" uv run fleet-viewer --tello "$DRONE_IP"
  WAIT_PID=$LAST_PID WAIT_LOG=$LAST_LOG wait_for "drone server" 60 curl -sf -m 2 http://127.0.0.1:8001/state \
    || echo "    -> power-cycle the drone (it obeys only the first program after boot) or check DRONE_IP; rover still starts"
}

start_frontend() {  # voice (speech-to-text and text-to-speech) is Grok Voice via the drone server
  bg frontend "$ROOT/frontend" npm run dev
  wait_for "frontend" 60 curl -sf -m 2 http://localhost:5173/
}
