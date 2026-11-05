"""Browser remote for a RoboMaster TT / Tello on the local network.

Usage:
  python scripts/remote.py
  python scripts/remote.py 10.37.75.76

Opens a control page on http://127.0.0.1:8765
Sticks are capped at ±40. Emergency cuts the motors.
"""

import json
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from room_map import CEILING_CM, ROOM_PAGE, RoomMap
from search_mission import PAGE as SEARCH_PAGE, SearchMission

DRONE_IP = "10.37.75.76"
CMD_PORT = 8889
STATE_PORT = 8890
VIDEO_PORT = 11111
HTTP_PORT = 8765
RC_CAP = 40
MAX_HEIGHT_CM = CEILING_CM
RC_HZ = 12

ROOT = Path(__file__).resolve().parent.parent
SNAP_DIR = ROOT / "captures"


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


def clamp(v, lo, hi):
    return max(lo, min(hi, int(v)))


class DroneLink:
    def __init__(self, drone_ip, local_ip):
        self.drone_ip = drone_ip
        self.local_ip = local_ip
        self.sock = None
        self.lock = threading.Lock()
        self.ready = threading.Event()
        self.ready.set()
        self.connected = False
        self.last_reply = ""
        self.log = []
        self.state = {}
        self.state_age = None
        self.sticks = (0, 0, 0, 0)
        self.sticks_at = 0.0
        self.rc_pause_until = 0.0
        self.quiet_until = 0.0
        self.flying = False
        self.jpeg = None
        self.jpeg_at = 0.0
        self.video_on = False
        self.recording = False
        self.writer = None
        self.record_path = None
        self.record_lock = threading.Lock()
        self.room = RoomMap(SNAP_DIR / "room_map.json")
        self.search = SearchMission(self)
        self.speed_cms = 30
        self._spinning = False
        self._stop = threading.Event()

    def note(self, text):
        line = f"{time.strftime('%H:%M:%S')}  {text}"
        print(line, flush=True)
        self.log.append(line)
        del self.log[:-12]

    def open(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # The TT in station mode answers (and sends video) to local port 8889.
        # It often executes the command and sends no "ok" text at all.
        try:
            sock.bind((self.local_ip, CMD_PORT))
        except OSError:
            try:
                sock.bind(("", CMD_PORT))
            except OSError:
                sock.bind((self.local_ip, 0))
        self.sock = sock
        self.note(f"commands {sock.getsockname()} -> {self.drone_ip}:{CMD_PORT}")
        self.send_nowait("command")
        self.send_nowait(f"speed {self.speed_cms}")
        threading.Thread(target=self._keepalive, daemon=True).start()
        threading.Thread(target=self._rc_loop, daemon=True).start()
        threading.Thread(target=self._state_loop, daemon=True).start()
        threading.Thread(target=self._video_loop, daemon=True).start()
        threading.Thread(target=self._map_loop, daemon=True).start()
        return True

    def send_nowait(self, cmd):
        if self.sock is None:
            return
        with self.lock:
            self.sock.sendto(cmd.encode("utf-8"), (self.drone_ip, CMD_PORT))

    def send(self, cmd, timeout=2.0):
        """Send a command that expects a reply. Blocks rc while waiting."""
        self.ready.clear()
        try:
            with self.lock:
                self.sock.sendto(cmd.encode("utf-8"), (self.drone_ip, CMD_PORT))
                self.sock.settimeout(timeout)
                try:
                    data, _ = self.sock.recvfrom(2048)
                    reply = data.decode("utf-8", errors="replace").strip("\x00\r\n ")
                except socket.timeout:
                    reply = ""
            self.last_reply = reply or "(no reply)"
            self.note(f">> {cmd}   << {self.last_reply}")
            return reply
        finally:
            self.ready.set()

    def send_rc(self, a, b, c, d):
        if not self.ready.is_set() or self.sock is None:
            return
        # A landing is cancelled by any stick command, including zeros.
        if self.search.landing:
            return
        cmd = f"rc {a} {b} {c} {d}"
        with self.lock:
            if not self.ready.is_set():
                return
            self.sock.sendto(cmd.encode("utf-8"), (self.drone_ip, CMD_PORT))

    def set_speed(self, value):
        self.speed_cms = clamp(value, 10, 60)
        self.send_nowait(f"speed {self.speed_cms}")
        self.note(f"speed {self.speed_cms} cm/s")
        return self.speed_cms

    def set_sticks(self, roll, pitch, throttle, yaw):
        cap = self.speed_cms
        h = self._height()
        throttle = clamp(throttle, -cap, cap)
        pitch = clamp(pitch, -cap, cap)
        if h is not None and h >= MAX_HEIGHT_CM - 15 and throttle > 0:
            throttle = 0 if h >= MAX_HEIGHT_CM - 5 else min(throttle, 8)
        if self.room.block_forward and pitch > 0:
            pitch = 0
        self.sticks = (
            clamp(roll, -cap, cap),
            pitch,
            throttle,
            clamp(yaw, -cap, cap),
        )
        if any(self.sticks):
            self.sticks_at = time.time()

    def _yaw(self):
        raw = self.state.get("yaw")
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    def _slow_spin(self):
        # rc yaw 15 is a small stick, so a full circle takes about half a minute.
        # The page keeps posting zero sticks, which would cancel the turn,
        # so the normal stick loop stays quiet until this finishes.
        self._spinning = True
        self.set_sticks(0, 0, 0, 0)
        self.rc_pause_until = time.time() + 45
        self.note("slow spin started")
        start = self._yaw()
        last = start
        turned = 0.0
        began = time.time()
        try:
            while time.time() - began < 42 and turned < 350:
                now = self._yaw()
                if now is not None and last is not None:
                    step = now - last
                    if step > 180:
                        step -= 360
                    if step < -180:
                        step += 360
                    turned += abs(step)
                    last = now
                self.send_rc(0, 0, 0, 15)
                time.sleep(0.12)
            self.send_rc(0, 0, 0, 0)
            self.note("slow spin finished")
        finally:
            self.rc_pause_until = time.time() + 0.4
            self._spinning = False

    def _height(self):
        raw = self.state.get("h")
        try:
            return int(float(raw))
        except (TypeError, ValueError):
            return None

    def _rc_loop(self):
        period = 1.0 / RC_HZ
        while not self._stop.is_set():
            # rc cancels takeoff and land. The page posts zeros continuously,
            # so only forward a stick while it is actually held, plus one
            # zero frame on release. Stay silent during takeoff and land.
            if self.search.landing and time.time() >= self.rc_pause_until:
                h = self._height()
                if (h is not None and h <= 8) or time.time() > self.search.land_until:
                    self.search.landing = False
            if time.time() < self.rc_pause_until or self.search.landing:
                time.sleep(period)
                continue
            if time.time() - self.sticks_at > 0.45:
                self.sticks = (0, 0, 0, 0)
            a, b, c, d = self.sticks
            if any((a, b, c, d)) or time.time() - self.sticks_at < 0.25:
                self.send_rc(a, b, c, d)
            time.sleep(period)

    def _map_loop(self):
        while not self._stop.is_set():
            self.room.tick(self.state)
            time.sleep(0.1)

    def _keepalive(self):
        while not self._stop.is_set():
            time.sleep(8)
            if self._stop.is_set() or time.time() < self.quiet_until:
                continue
            self.send_nowait("command")

    def _state_loop(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("", STATE_PORT))
        except OSError as exc:
            self.note(f"state port {STATE_PORT} busy ({exc})")
            s.close()
            return
        s.settimeout(2.0)
        self.note(f"listening for state on :{STATE_PORT}")
        while not self._stop.is_set():
            try:
                data, _ = s.recvfrom(2048)
            except socket.timeout:
                continue
            text = data.decode("utf-8", errors="replace").strip("\x00\r\n ")
            parsed = {}
            for part in text.split(";"):
                if ":" not in part:
                    continue
                key, val = part.split(":", 1)
                parsed[key.strip()] = val.strip()
            if parsed:
                self.state = parsed
                self.state_age = time.time()
                self.connected = True
                h = self._height()
                if h is not None:
                    self.flying = h > 8
        s.close()

    def _video_loop(self):
        try:
            import av
            import cv2
        except Exception as exc:
            self.note(f"video unavailable ({exc})")
            return
        vs = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        vs.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        vs.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2 * 1024 * 1024)
        try:
            vs.bind(("", VIDEO_PORT))
        except OSError as exc:
            self.note(f"video port busy ({exc})")
            vs.close()
            return
        vs.settimeout(1.0)
        codec = av.CodecContext.create("h264", "r")
        self.video_on = True
        self.note(f"video on :{VIDEO_PORT}")
        last_ask = 0.0
        last_packet = 0.0
        last_frame = 0.0
        packets = 0
        announced = False
        while not self._stop.is_set():
            # Takeoff and land stop the camera. Ask again whenever packets dry up.
            quiet = time.time() - last_packet > 1.5
            if (self.jpeg is None or quiet) and time.time() - last_ask > 2.0:
                self.send_nowait("streamon")
                last_ask = time.time()
                if quiet and announced:
                    self.note("camera stalled, streamon again")
                    codec = av.CodecContext.create("h264", "r")
            try:
                packet, _ = vs.recvfrom(2048)
            except socket.timeout:
                continue
            last_packet = time.time()
            packets += 1
            if not announced:
                self.note("camera packets arriving")
                announced = True
            try:
                decoded = False
                for pkt in codec.parse(packet):
                    for frame in codec.decode(pkt):
                        img = frame.to_ndarray(format="bgr24")
                        ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
                        if ok:
                            self.jpeg = buf.tobytes()
                            self.jpeg_at = time.time()
                            last_frame = self.jpeg_at
                            decoded = True
                            self._write_frame(img)
                            self.room.see(img, self.state)
                if not decoded and last_frame and time.time() - last_frame > 2.0:
                    codec = av.CodecContext.create("h264", "r")
                    last_frame = time.time()
            except Exception:
                codec = av.CodecContext.create("h264", "r")
        self._close_writer()
        vs.close()

    def _write_frame(self, img):
        if not self.recording:
            return
        import cv2

        with self.record_lock:
            if not self.recording:
                return
            if self.writer is None:
                SNAP_DIR.mkdir(exist_ok=True)
                height, width = img.shape[:2]
                path = SNAP_DIR / f"remote_{time.strftime('%H%M%S')}.mp4"
                self.record_path = path
                self.writer = cv2.VideoWriter(
                    str(path), cv2.VideoWriter_fourcc(*"mp4v"), 15.0, (width, height)
                )
                self.note(f"recording {path.name}")
            self.writer.write(img)

    def _close_writer(self):
        with self.record_lock:
            writer = self.writer
            self.writer = None
            self.recording = False
            if writer is not None:
                writer.release()

    def toggle_record(self):
        if self.jpeg is None and not self.recording:
            return {"ok": False, "recording": False, "file": None, "reply": "camera not ready"}
        with self.record_lock:
            if self.recording:
                self.recording = False
                writer = self.writer
                self.writer = None
                path = self.record_path
                self.record_path = None
            else:
                self.recording = True
                return {"ok": True, "recording": True, "file": None, "reply": "recording"}
        if writer is not None:
            writer.release()
        name = path.name if path is not None else None
        self.note(f"saved {name}" if name else "recording stopped")
        reply = f"saved {name}" if name else "recording stopped"
        return {"ok": True, "recording": False, "file": name, "reply": reply}

    def action(self, name):
        name = name.lower().strip()
        if name == "takeoff":
            bat = self._battery()
            temp = self._temp()
            if bat is not None and bat < 15:
                self.note(f"takeoff refused, battery {bat}%")
                return False, f"battery {bat}% is too low to take off"
            if temp is not None and temp >= 90:
                self.note(f"takeoff refused, board {temp}C")
                return False, f"board is {temp}C, too hot to take off"
            self.set_sticks(0, 0, 0, 0)
            self.rc_pause_until = time.time() + 8
            self.quiet_until = time.time() + 8
            self.send_nowait("command")
            time.sleep(0.2)
            self.send_nowait("takeoff")
            self.note("takeoff sent")
            return True, "takeoff sent"
        if name == "spin":
            if not self.flying and (self._height() or 0) < 8:
                self.note("spin refused, still on the ground")
                return False, "take off first, then it turns a full circle"
            if self._spinning:
                return True, "already turning slowly"
            threading.Thread(target=self._slow_spin, daemon=True).start()
            return True, "slow full turn"
        if name == "land":
            self.search.force_land()
            return True, "force landing"
        if name == "stop":
            self.set_sticks(0, 0, 0, 0)
            self.send_nowait("stop")
            return True, "hover"
        if name == "emergency":
            self.set_sticks(0, 0, 0, 0)
            self.send_nowait("emergency")
            self.flying = False
            return True, "motors cut"
        return False, "unknown action"

    def _temp(self):
        vals = []
        for key in ("temph", "templ"):
            try:
                vals.append(int(float(self.state.get(key))))
            except (TypeError, ValueError):
                pass
        return max(vals) if vals else None

    def _battery(self):
        raw = self.state.get("bat")
        if raw is None:
            return None
        try:
            return int(float(raw))
        except ValueError:
            return None

    def snapshot(self):
        if not self.jpeg:
            return None
        SNAP_DIR.mkdir(exist_ok=True)
        path = SNAP_DIR / f"remote_{time.strftime('%H%M%S')}.jpg"
        path.write_bytes(self.jpeg)
        self.note(f"saved {path.name}")
        return path.name

    def device_connected(self):
        """True only while state packets are still arriving."""
        if self.state_age is None:
            return False
        return time.time() - self.state_age < 3

    def status(self):
        self.connected = self.device_connected()
        age = None if self.state_age is None else round(time.time() - self.state_age, 1)
        a, b, c, d = self.sticks
        return {
            "connected": self.connected,
            "drone_ip": self.drone_ip,
            "local_ip": self.local_ip,
            "flying": self.flying,
            "video": self.jpeg is not None,
            "video_age": None if not self.jpeg_at else round(time.time() - self.jpeg_at, 1),
            "recording": self.recording,
            "record_file": self.record_path.name if self.record_path else None,
            "last_reply": self.last_reply,
            "sticks": {"roll": a, "pitch": b, "throttle": c, "yaw": d},
            "state": self.state,
            "state_age": age,
            "log": list(self.log),
            "speed_cms": self.speed_cms,
            "ceiling_cm": MAX_HEIGHT_CM,
            "obstacle_cm": self.room.obstacle_cm,
            "block_forward": self.room.block_forward,
        }


LINK = None


PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TT remote</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fragment+Mono&family=Schibsted+Grotesk:wght@500;700&display=swap" rel="stylesheet">
<style>
  :root {
    --housing: #2a3124;
    --housing-2: #1c2219;
    --well: #10140e;
    --paper: #f3ead4;
    --ink: #1a1c14;
    --amber: #e39b12;
    --air: #9ec9b8;
    --brick: #d94a32;
    --line: rgba(243, 234, 212, 0.16);
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; height: 100%; }
  body {
    background:
      radial-gradient(1200px 500px at 70% -10%, #3a4432 0%, transparent 55%),
      var(--housing-2);
    color: var(--paper);
    font-family: "Schibsted Grotesk", sans-serif;
    min-height: 100%;
  }
  .shell {
    max-width: 1100px;
    margin: 0 auto;
    padding: 22px 22px 32px;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 16px;
    padding-bottom: 14px;
    border-bottom: 1px solid var(--line);
  }
  h1 {
    margin: 0;
    font-weight: 700;
    font-size: 28px;
    letter-spacing: -0.03em;
  }
  h1 span { color: var(--amber); }
  .sub { margin: 4px 0 0; color: rgba(243,234,212,0.62); font-size: 14px; }
  .readouts {
    display: flex;
    gap: 18px;
    font-family: "Fragment Mono", monospace;
    font-size: 13px;
  }
  .readouts b { display: block; font-size: 22px; font-weight: 400; color: var(--paper); }
  .readouts em { font-style: normal; color: rgba(243,234,212,0.55); }
  .dot {
    width: 8px; height: 8px; border-radius: 50%;
    display: inline-block; margin-right: 6px; background: var(--brick);
  }
  .dot.on { background: var(--air); }
  .stage {
    display: grid;
    grid-template-columns: 1.4fr 0.8fr;
    gap: 16px;
    margin-top: 16px;
  }
  .screen {
    background: var(--well);
    border-radius: 18px;
    min-height: 320px;
    position: relative;
    overflow: hidden;
    border: 1px solid var(--line);
  }
  .screen img { width: 100%; height: 100%; object-fit: cover; display: block; min-height: 320px; background: #10140e; }
  .screen img[hidden] { display: none; }
  .screen .wait {
    position: absolute; inset: 0;
    display: grid; place-items: center;
    color: rgba(243,234,212,0.45);
    font-size: 15px;
  }
  .screen .wait[hidden] { display: none; }
  .hud {
    position: absolute; left: 12px; bottom: 12px; z-index: 2;
    display: flex; gap: 8px; align-items: stretch;
  }
  .compass, .vsi {
    background: rgba(16, 20, 14, 0.78);
    border: 1px solid rgba(243, 234, 212, 0.35);
    border-radius: 12px;
  }
  .compass { width: 86px; height: 86px; position: relative; }
  .rose { position: absolute; inset: 0; transition: transform 0.15s linear; }
  .rose b {
    position: absolute; font-size: 12px; font-family: "Fragment Mono", monospace;
  }
  .rose .n { left: 50%; top: 5px; transform: translateX(-50%); color: var(--amber); }
  .rose .e { right: 6px; top: 50%; transform: translateY(-50%); }
  .rose .s { left: 50%; bottom: 5px; transform: translateX(-50%); }
  .rose .w { left: 6px; top: 50%; transform: translateY(-50%); }
  .needle {
    position: absolute; left: 50%; top: 8px; z-index: 1;
    width: 0; height: 0; transform: translateX(-50%);
    border-left: 5px solid transparent; border-right: 5px solid transparent;
    border-bottom: 16px solid var(--paper);
  }
  .vsi {
    width: 54px; padding: 6px 6px 4px;
    display: flex; flex-direction: column; align-items: center; gap: 3px;
    font-family: "Fragment Mono", monospace; font-size: 10px;
    color: rgba(243,234,212,0.7);
  }
  .track {
    width: 14px; flex: 1; min-height: 48px; position: relative;
    background: rgba(243,234,212,0.12); border-radius: 7px;
  }
  .track i {
    position: absolute; left: 1px; right: 1px; height: 4px; border-radius: 2px;
    background: var(--amber); bottom: 50%;
  }
  .vsi em { font-style: normal; color: var(--paper); font-size: 11px; }
  .panel {
    background: var(--housing);
    border-radius: 18px;
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    border: 1px solid var(--line);
  }
  button {
    font-family: inherit;
    font-size: 16px;
    font-weight: 700;
    border: 0;
    border-radius: 12px;
    padding: 14px 12px;
    cursor: pointer;
    background: var(--paper);
    color: var(--ink);
  }
  button:focus-visible { outline: 2px solid var(--amber); outline-offset: 2px; }
  button.ghost { background: transparent; color: var(--paper); border: 1px solid var(--line); }
  button.brick { background: var(--brick); color: white; }
  button:disabled { opacity: 0.45; cursor: default; }
  .row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .sticks {
    margin-top: 16px;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
  }
  .gimbal {
    background: var(--housing);
    border-radius: 18px;
    padding: 14px 14px 16px;
    border: 1px solid var(--line);
  }
  .gimbal p { margin: 0 0 10px; font-size: 14px; color: rgba(243,234,212,0.7); }
  .pad {
    touch-action: none;
    aspect-ratio: 1;
    max-height: 280px;
    margin: 0 auto;
    background:
      linear-gradient(var(--line), var(--line)) center/1px 100% no-repeat,
      linear-gradient(var(--line), var(--line)) center/100% 1px no-repeat,
      radial-gradient(circle at center, #1a2118 0%, var(--well) 72%);
    border-radius: 50%;
    position: relative;
    border: 10px solid #141910;
    cursor: grab;
  }
  .knob {
    width: 64px; height: 64px; border-radius: 50%;
    background: radial-gradient(circle at 35% 30%, #fff6e4, var(--paper) 45%, #c9b48a);
    position: absolute; left: 50%; top: 50%;
    transform: translate(-50%, -50%);
    box-shadow: 0 8px 16px rgba(0,0,0,0.35);
    pointer-events: none;
  }
  .speed { display: flex; align-items: center; gap: 10px; font-size: 14px; }
  .speed input { flex: 1; accent-color: var(--amber); }
  .hint {
    margin: 14px 0 0;
    color: rgba(243,234,212,0.5);
    font-size: 13px;
  }
  .log {
    margin-top: 14px;
    font-family: "Fragment Mono", monospace;
    font-size: 12px;
    color: rgba(243,234,212,0.55);
    line-height: 1.55;
    min-height: 3em;
  }
  @media (max-width: 800px) {
    .stage, .sticks { grid-template-columns: 1fr; }
    header { flex-direction: column; align-items: flex-start; }
  }
</style>
</head>
<body>
<div class="shell">
  <header>
    <div>
      <h1>TT <span>remote</span></h1>
      <p class="sub"><i class="dot" id="dot"></i><span id="link">Device not connected</span></p>
    </div>
    <div class="readouts">
      <div><em>battery</em><b id="bat">–</b></div>
      <div><em>height</em><b id="h">–</b></div>
      <div><em>yaw</em><b id="yaw">–</b></div>
      <div><em>board</em><b id="temp">–</b></div>
    </div>
  </header>

  <div class="stage">
    <div class="screen">
      <div class="wait" id="wait">camera starting</div>
      <img id="cam" alt="drone camera" hidden>
      <div class="hud">
        <div class="compass" title="North is the heading at power on. The mark is the nose.">
          <i class="needle"></i>
          <div class="rose" id="rose"><b class="n">N</b><b class="e">E</b><b class="s">S</b><b class="w">W</b></div>
        </div>
        <div class="vsi" title="Up and down">
          <span>up</span>
          <div class="track"><i id="vsiMark"></i></div>
          <span>down</span>
          <em id="vsiLabel">level</em>
        </div>
      </div>
    </div>
    <div class="panel">
      <div class="row">
        <button id="takeoff" type="button">Take off</button>
        <button id="land" class="brick" type="button">Force land</button>
      </div>
      <label class="speed">Speed <b id="speedLabel">30</b>
        <input id="speed" type="range" min="10" max="60" value="30" step="5">
      </label>
      <button id="hover" class="ghost" type="button">Hover</button>
      <button id="spin" class="ghost" type="button">Turn 360</button>
      <button id="snap" class="ghost" type="button">Save photo</button>
      <button id="rec" class="ghost" type="button">Record video</button>
      <button id="cut" class="brick" type="button">Cut motors</button>
      <p class="sub" id="msg"></p>
    </div>
  </div>

  <div class="sticks">
    <div class="gimbal">
      <p>Left hand — turn and height</p>
      <div class="pad" id="padL" data-x="yaw" data-y="throttle"><div class="knob"></div></div>
    </div>
    <div class="gimbal">
      <p>Right hand — slide and nose</p>
      <div class="pad" id="padR" data-x="roll" data-y="pitch"><div class="knob"></div></div>
    </div>
  </div>
  <p class="hint">Hold a stick or use keys. W S nose, A D slide, Q E turn, R F height. Space hovers. Height stops at 1.9 m. Forward stops when the camera sees something close. <a href="/room">Room map</a> · <a href="/search">Search</a></p>
  <div class="log" id="log"></div>
</div>
<script>
const axes = { roll: 0, pitch: 0, throttle: 0, yaw: 0 };
const pads = {};
let CAP = 30;

function setAxis(name, v) { axes[name] = Math.max(-CAP, Math.min(CAP, Math.round(v))); }

function bindPad(el) {
  const knob = el.querySelector(".knob");
  const xName = el.dataset.x;
  const yName = el.dataset.y;
  pads[el.id] = { x: 0, y: 0 };
  function place(px, py) {
    const r = el.getBoundingClientRect();
    const cx = r.left + r.width / 2;
    const cy = r.top + r.height / 2;
    const max = r.width / 2 - 36;
    let dx = px - cx;
    let dy = py - cy;
    const mag = Math.hypot(dx, dy) || 1;
    if (mag > max) { dx = dx / mag * max; dy = dy / mag * max; }
    knob.style.transform = `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px))`;
    const nx = dx / max;
    const ny = -dy / max;
    pads[el.id] = { x: nx, y: ny };
    setAxis(xName, nx * CAP);
    setAxis(yName, ny * CAP);
  }
  function reset() {
    knob.style.transform = "translate(-50%, -50%)";
    pads[el.id] = { x: 0, y: 0 };
    setAxis(xName, 0);
    setAxis(yName, 0);
  }
  el.addEventListener("pointerdown", (e) => {
    el.setPointerCapture(e.pointerId);
    place(e.clientX, e.clientY);
  });
  el.addEventListener("pointermove", (e) => {
    if (el.hasPointerCapture(e.pointerId)) place(e.clientX, e.clientY);
  });
  el.addEventListener("pointerup", reset);
  el.addEventListener("pointercancel", reset);
}

bindPad(document.getElementById("padL"));
bindPad(document.getElementById("padR"));

const keys = {};
addEventListener("keydown", (e) => {
  if (e.repeat) return;
  if (["Space", "KeyW", "KeyA", "KeyS", "KeyD", "KeyQ", "KeyE", "KeyR", "KeyF"].includes(e.code)) e.preventDefault();
  keys[e.code] = true;
  if (e.code === "Space") act("stop");
});
addEventListener("keyup", (e) => { keys[e.code] = false; });
addEventListener("blur", () => { for (const k in keys) keys[k] = false; });

function fromKeys() {
  const left = document.getElementById("padL");
  const right = document.getElementById("padR");
  if (!left.hasPointerCapture && !right.matches(":active")) {
    /* keyboard fills axes the pads are not holding */
  }
  const padHolding = Object.values(pads).some(p => p.x || p.y);
  if (padHolding) return;
  setAxis("pitch", (keys.KeyW ? CAP : 0) + (keys.KeyS ? -CAP : 0));
  setAxis("roll", (keys.KeyD ? CAP : 0) + (keys.KeyA ? -CAP : 0));
  setAxis("yaw", (keys.KeyE ? CAP : 0) + (keys.KeyQ ? -CAP : 0));
  setAxis("throttle", (keys.KeyR ? CAP : 0) + (keys.KeyF ? -CAP : 0));
}

async function post(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {})
  });
  return res.json();
}

async function act(name) {
  const buttons = document.querySelectorAll("button");
  buttons.forEach(b => b.disabled = true);
  try {
    const res = await post("/api/action", { name });
    document.getElementById("msg").textContent = res.reply || "";
  }
  finally { buttons.forEach(b => b.disabled = false); }
}

document.getElementById("takeoff").onclick = () => act("takeoff");
document.getElementById("land").onclick = () => act("land");
const speedInput = document.getElementById("speed");
speedInput.oninput = () => {
  CAP = Number(speedInput.value);
  document.getElementById("speedLabel").textContent = CAP;
};
speedInput.onchange = () => post("/api/speed", { value: CAP });
document.getElementById("hover").onclick = () => act("stop");
document.getElementById("spin").onclick = () => act("spin");
document.getElementById("snap").onclick = () => post("/api/snap", {});
document.getElementById("rec").onclick = async () => {
  const res = await post("/api/record", {});
  document.getElementById("msg").textContent = res.reply || "";
};
document.getElementById("cut").onclick = () => {
  if (confirm("Cut the motors? The drone will drop.")) act("emergency");
};

setInterval(() => {
  fromKeys();
  post("/api/stick", axes).catch(() => {});
}, 80);

const cam = document.getElementById("cam");
const wait = document.getElementById("wait");
function armVideo() {
  cam.hidden = false;
  wait.hidden = true;
}
setInterval(() => { cam.src = "/camera.jpg?t=" + Date.now(); }, 200);
cam.onerror = () => { wait.hidden = false; wait.textContent = "no camera picture yet"; };

async function poll() {
  try {
    const s = await (await fetch("/api/state")).json();
    const st = s.state || {};
    document.getElementById("dot").classList.toggle("on", s.connected);
    document.getElementById("link").textContent = s.connected
      ? "Device connected · " + s.drone_ip + (s.flying ? " · in the air" : " · on the ground")
      : "Device not connected";
    document.getElementById("bat").textContent = st.bat != null ? st.bat + "%" : "–";
    document.getElementById("h").textContent = st.h != null ? st.h + " cm" : "–";
    document.getElementById("yaw").textContent = st.yaw != null ? st.yaw + "°" : "–";
    const yawDeg = Number(st.yaw);
    if (!Number.isNaN(yawDeg)) document.getElementById("rose").style.transform = "rotate(" + (-yawDeg) + "deg)";
    const climb = Math.max(-1, Math.min(1, Number(st.vgz || 0) / 12));
    document.getElementById("vsiMark").style.bottom = (50 + climb * 40) + "%";
    const pitch = Number(st.pitch || 0);
    const vgz = Number(st.vgz || 0);
    document.getElementById("vsiLabel").textContent = vgz > 2 ? "up" : vgz < -2 ? "down" : pitch > 8 ? "nose up" : pitch < -8 ? "nose down" : "level";
    const board = st.temph != null ? st.temph : st.templ;
    document.getElementById("temp").textContent = board != null ? board + "°" : "–";
    if (s.connected && board != null && Number(board) >= 90) {
      document.getElementById("msg").textContent = "Board is " + board + "°. It will not take off until it cools.";
    }
    document.getElementById("log").textContent = (s.log || []).slice(-4).join("\n");
    const rec = document.getElementById("rec");
    rec.textContent = s.recording ? "Stop recording" : "Record video";
    rec.classList.toggle("brick", !!s.recording);
    if (cam.hidden) armVideo();
    if (s.video_age != null && s.video_age > 3 && !cam.dataset.reloading) {
      cam.dataset.reloading = "1";
      cam.src = "/video?t=" + Date.now();
      setTimeout(() => { cam.dataset.reloading = ""; }, 2000);
    }
  } catch (e) {
    document.getElementById("link").textContent = "page lost the server";
  }
}
setInterval(poll, 500);
poll();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        return

    def _json(self, code, payload):
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            raw = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if path == "/api/state":
            self._json(200, LINK.status())
            return
        if path == "/room":
            raw = ROOM_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if path == "/search":
            raw = SEARCH_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if path == "/api/search":
            self._json(200, LINK.search.snapshot())
            return
        if path == "/search/found.jpg":
            frame = LINK.search.found_jpeg
            if not frame:
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(frame)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(frame)
            return
        if path == "/api/mesh":
            with LINK.room.lock:
                payload = LINK.room.mesh or {"file": "", "xyz": [], "rgb": [], "faces": []}
            self._json(200, payload)
            return
        if path == "/api/map":
            with LINK.room.lock:
                payload = LINK.room.snapshot()
            payload["connected"] = LINK.device_connected()
            payload["drone_ip"] = LINK.drone_ip
            self._json(200, payload)
            return
        if path == "/depth.jpg":
            frame = LINK.room.depth_jpeg
            if not frame:
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(frame)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(frame)
            return
        if path == "/camera.jpg":
            frame = LINK.jpeg
            if not frame:
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(frame)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(frame)
            return
        if path == "/video":
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                while True:
                    frame = LINK.jpeg
                    if frame:
                        header = (
                            b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                            + str(len(frame)).encode()
                            + b"\r\n\r\n"
                        )
                        self.wfile.write(header + frame + b"\r\n")
                        self.wfile.flush()
                    time.sleep(0.07)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                return
        self._json(404, {"error": "not found"})

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        body = self._body()
        if path == "/api/stick":
            LINK.set_sticks(
                body.get("roll", 0),
                body.get("pitch", 0),
                body.get("throttle", 0),
                body.get("yaw", 0),
            )
            self._json(200, {"ok": True})
            return
        if path == "/api/action":
            ok, reply = LINK.action(str(body.get("name", "")))
            self._json(200, {"ok": ok, "reply": reply})
            return
        if path == "/api/snap":
            name = LINK.snapshot()
            self._json(200, {"ok": bool(name), "file": name})
            return
        if path == "/api/speed":
            value = LINK.set_speed(body.get("value", 30))
            self._json(200, {"ok": True, "speed_cms": value})
            return
        if path == "/api/record":
            self._json(200, LINK.toggle_record())
            return
        if path == "/api/map/clear":
            LINK.room.clear()
            self._json(200, {"ok": True})
            return
        if path == "/api/search":
            reply = LINK.search.start(str(body.get("query", "")))
            self._json(200, {"ok": True, "reply": reply})
            return
        if path == "/api/search/stop":
            LINK.search.halt()
            self._json(200, {"ok": True, "reply": "hover"})
            return
        if path == "/api/search/again":
            reply = LINK.search.look_again()
            self._json(200, {"ok": True, "reply": reply})
            return
        if path == "/api/search/land":
            LINK.search.force_land()
            self._json(200, {"ok": True, "reply": "landing"})
            return
        if path == "/api/map/start":
            on = LINK.room.set_mapping(bool(body.get("on")))
            LINK.note("mapping on" if on else "mapping off")
            self._json(200, {"ok": True, "mapping": on})
            return
        self._json(404, {"error": "not found"})


def main():
    global LINK
    import sys

    drone_ip = sys.argv[1] if len(sys.argv) > 1 else DRONE_IP
    local_ip = wifi_ipv4()
    print(f"Wi-Fi {local_ip}  drone {drone_ip}", flush=True)
    LINK = DroneLink(drone_ip, local_ip)
    threading.Thread(target=LINK.open, daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), Handler)
    print(f"Remote: http://127.0.0.1:{HTTP_PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping", flush=True)
    finally:
        LINK._stop.set()
        try:
            LINK.set_sticks(0, 0, 0, 0)
            LINK.send("stop", timeout=1.0)
        except Exception:
            pass
        server.shutdown()


if __name__ == "__main__":
    main()
