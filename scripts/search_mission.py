"""Search dashboard. Look around, then move into the open squares.

The drone climbs to 1.6 m and photographs a 360. Green squares are open
at its height. Red squares are farther ahead, in the center of the camera.
If the object is not in that view, the drone flies two squares into a
direction with no obstacle and looks around again. It stops when the
object is found, or lands when the battery reaches 25%.
"""

import json
import math
import threading
import time
from pathlib import Path

import cv2

CELL_CM = 50
CEILING_CM = 160
ROOT = Path(__file__).resolve().parent.parent

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Search</title>
<style>
  :root { --ink:#1a1c14; --paper:#f3ead4; --well:#10140e; --amber:#e39b12; --brick:#d94a32; --leaf:#2f9e6b; }
  * { box-sizing: border-box; }
  body { margin:0; background:#1c2219; color:var(--paper); font-family:"Segoe UI",sans-serif; }
  header { display:flex; justify-content:space-between; gap:16px; align-items:flex-end; padding:18px 22px 8px; }
  h1 { margin:0; font-size:28px; letter-spacing:-0.03em; }
  a { color:#9ec9b8; }
  .device { margin:0; font-weight:750; display:flex; align-items:center; gap:8px; color:#e7b2a8; }
  .device i { width:12px; height:12px; border-radius:50%; background:#d94a32; display:block; }
  .device.on { color:#b7e4c7; }
  .device.on i { background:#2f9e6b; }
  .search { display:flex; gap:8px; padding:0 22px 12px; }
  input[type=search] { flex:1; font:inherit; font-size:18px; padding:12px 14px; border-radius:12px; border:0; background:var(--paper); color:var(--ink); }
  button { font:inherit; font-weight:700; border:0; border-radius:12px; padding:12px 16px; cursor:pointer; background:var(--paper); color:var(--ink); }
  button.go { background:var(--leaf); color:white; }
  button.stop { background:var(--brick); color:white; }
  button.mic { background:var(--amber); }
  .alert { margin:0 22px 8px; min-height:1.4em; font-weight:750; color:var(--amber); }
  .alert.found { color:#ffd7a8; font-size:22px; }
  .stage { display:grid; grid-template-columns:1fr 320px; gap:12px; padding:8px 22px 22px; }
  canvas { width:100%; height:72vh; background:var(--well); border-radius:16px; display:block; }
  .side { background:#2a3124; border-radius:16px; padding:12px; display:flex; flex-direction:column; gap:8px; }
  .side img { width:100%; height:180px; object-fit:cover; border-radius:10px; background:#10140e; }
  .quads { display:grid; grid-template-columns:1fr 1fr; gap:6px; }
  .quads div { background:#10140e; border-radius:8px; padding:8px; font-size:13px; }
  p { margin:0; color:rgba(243,234,212,.7); font-size:13px; }
  @media (max-width:900px) { .stage { grid-template-columns:1fr; } canvas { height:48vh; } }
</style>
</head>
<body>
<header>
  <div>
    <h1>Search</h1>
    <p>Looks all around, then flies into open space until it finds the object or the battery reaches 25%. <a href="/">Remote</a> · <a href="/room">Room</a></p>
  </div>
  <p class="device" id="device"><i></i><span>Device not connected</span></p>
</header>
<form class="search" id="form">
  <input id="q" type="search" placeholder="person in a red jacket, or a laptop" autocomplete="off">
  <button class="mic" id="mic" type="button">Voice</button>
  <button class="go" type="submit">Search and fly</button>
  <button class="stop" id="halt" type="button">Hover</button>
  <button class="stop" id="land" type="button">Force land</button>
</form>
<p class="alert" id="alert"></p>
<div class="stage">
  <canvas id="view" width="900" height="640"></canvas>
  <aside class="side">
    <img id="live" alt="drone camera">
    <img id="found" alt="match" hidden>
    <button id="again" type="button">Look again</button>
    <div class="quads" id="quads"></div>
    <p id="status">Waiting for a search.</p>
    <p>Green is open. Red is blocked. It keeps moving through green until the object is found or the battery reaches 25%.</p>
  </aside>
</div>
<script>
const canvas = document.getElementById("view");
const ctx = canvas.getContext("2d");
let state = { cells: [], pose: {yaw:0} };
const Speech = window.SpeechRecognition || window.webkitSpeechRecognition;
document.getElementById("mic").onclick = () => {
  if (!Speech) { document.getElementById("status").textContent = "This browser has no voice input. Type the search."; return; }
  const rec = new Speech();
  rec.lang = "en-US";
  rec.onresult = (e) => { document.getElementById("q").value = e.results[0][0].transcript; };
  rec.start();
  document.getElementById("status").textContent = "Listening…";
};
document.getElementById("form").onsubmit = async (e) => {
  e.preventDefault();
  const query = document.getElementById("q").value.trim();
  if (!query) return;
  const res = await fetch("/api/search", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({query})});
  const data = await res.json();
  document.getElementById("status").textContent = data.reply || "";
};
document.getElementById("halt").onclick = () => fetch("/api/search/stop", {method:"POST"});
document.getElementById("land").onclick = () => fetch("/api/search/land", {method:"POST"});
document.getElementById("again").onclick = async () => {
  const res = await fetch("/api/search/again", {method:"POST"});
  const data = await res.json();
  document.getElementById("status").textContent = data.reply || "";
};
function draw() {
  ctx.fillStyle = "#10140e";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  const cells = state.cells || [];
  const pose = state.pose || { x: 0, y: 0, yaw: 0 };
  let min = -2, max = 2;
  cells.forEach(c => { min = Math.min(min, c.i, c.j); max = Math.max(max, c.i + 1, c.j + 1); });
  min = Math.min(min, pose.x / 50, pose.y / 50);
  max = Math.max(max, pose.x / 50, pose.y / 50);
  const span = Math.max(4, max - min);
  const scale = Math.min(canvas.width, canvas.height) * 0.8 / (span * 50);
  const cx = canvas.width * 0.5, cy = canvas.height * 0.55;
  const to = (i, j) => [cx + (i - (min+max)/2) * 50 * scale, cy - (j - (min+max)/2) * 50 * scale];
  cells.forEach(c => {
    const p = to(c.i, c.j);
    const s = 50 * scale;
    ctx.fillStyle = c.open ? "#2f9e6b" : "#d94a32";
    ctx.fillRect(p[0], p[1] - s, s - 2, s - 2);
    if (!c.open) {
      ctx.fillStyle = "#8d2c22";
      ctx.beginPath();
      ctx.moveTo(p[0], p[1] - s);
      ctx.lineTo(p[0] + 8, p[1] - s - 8);
      ctx.lineTo(p[0] + s - 2 + 8, p[1] - s - 8);
      ctx.lineTo(p[0] + s - 2, p[1] - s);
      ctx.fill();
    }
  });
  const yaw = pose.yaw || 0;
  const here = to(pose.x / 50, pose.y / 50);
  ctx.strokeStyle = "#f3ead4";
  ctx.beginPath();
  ctx.arc(here[0], here[1], 7, 0, Math.PI * 2);
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(here[0], here[1]);
  ctx.lineTo(here[0] + 26 * Math.cos(yaw * Math.PI / 180), here[1] - 26 * Math.sin(yaw * Math.PI / 180));
  ctx.stroke();
  ctx.fillStyle = "#f3ead4";
  ctx.font = "13px Segoe UI";
  ctx.fillText("top view · 50 cm squares · the drone flies into green", 16, 24);
  requestAnimationFrame(draw);
}
draw();
async function poll() {
  try {
    state = await (await fetch("/api/search")).json();
    const device = document.getElementById("device");
    device.classList.toggle("on", !!state.connected);
    device.querySelector("span").textContent = state.connected
      ? "Device connected" + (state.drone_ip ? " · " + state.drone_ip : "")
      : "Device not connected";
    const alert = document.getElementById("alert");
    alert.textContent = state.alert || "";
    alert.className = "alert" + (state.found ? " found" : "");
    document.getElementById("status").textContent = state.status || "";
    const img = document.getElementById("found");
    if (state.found) { img.hidden = false; img.src = "/search/found.jpg?t=" + (state.found_at || 0); }
    else img.hidden = true;
    document.getElementById("quads").innerHTML = (state.quadrants || []).map(q =>
      `<div>Q${q.n}<br>${q.photos} photos<br>${q.blocked ? "blocked" : q.photos ? "clear" : "not scanned"}</div>`
    ).join("");
  } catch (e) {}
}
setInterval(poll, 700);
poll();
const live = document.getElementById("live");
setInterval(() => { live.src = "/camera.jpg?t=" + Date.now(); }, 250);
</script>
</body>
</html>
"""


class SearchMission:
    def __init__(self, link):
        self.link = link
        self.lock = threading.Lock()
        self.running = False
        self.stop = False
        self.landing = False
        self.land_until = 0.0
        self.query = ""
        self.status = "Waiting for a search."
        self.alert = ""
        self.found = False
        self.found_jpeg = None
        self.found_at = 0
        self.last_bucket = None
        self.last_quadrant = None
        self.cells = {}
        self.seen = set()
        self.visited = set()
        self.views = []
        self.px = 0.0
        self.py = 0.0
        self.last_move = None
        self.quadrants = [{"n": n, "photos": 0, "blocked": False} for n in range(1, 5)]

    def snapshot(self):
        with self.lock:
            return {
                "running": self.running,
                "query": self.query,
                "status": self.status,
                "alert": self.alert,
                "found": self.found,
                "found_at": self.found_at,
                "connected": self.link.device_connected(),
                "drone_ip": self.link.drone_ip,
                "pose": {
                    "yaw": self.link._yaw() or 0,
                    "x": round(self.px, 1),
                    "y": round(self.py, 1),
                },
                "cells": [
                    {"i": int(key.split(",")[0]), "j": int(key.split(",")[1]), "open": value == "green"}
                    for key, value in self.cells.items()
                ],
                "quadrants": self.quadrants,
            }

    def start(self, query):
        query = (query or "").strip()
        if not query:
            return "Type who or what to look for."
        if self.landing:
            return "Still landing."
        with self.lock:
            if self.running:
                return "Already searching."
            self.running = True
            self.stop = False
            self.query = query
            self.found = False
            self.found_jpeg = None
            self.alert = ""
            self.cells = {}
            self.seen = set()
            self.visited = set()
            self.views = []
            self.px = 0.0
            self.py = 0.0
            self.last_move = None
            self.quadrants = [{"n": n, "photos": 0, "blocked": False} for n in range(1, 5)]
            self.status = "Starting."
        threading.Thread(target=self._run, daemon=True).start()
        return f"Looking for {query}. Climbing to 1.6 m."

    def halt(self):
        self.stop = True
        self.link.set_sticks(0, 0, 0, 0)
        self.link.send_rc(0, 0, 0, 0)
        with self.lock:
            self.status = "Hovering."
            self.running = False
        return "hover"

    def look_again(self):
        """Drop the match photo and scan again, including the heading it came from."""
        if self.landing:
            return "Still landing."
        with self.lock:
            if self.running:
                return "Still searching."
            if not self.query:
                return "Search for something first."
            had_picture = self.found
            self.found = False
            self.found_jpeg = None
            self.alert = ""
            if had_picture and self.last_bucket is not None:
                self.seen.discard(self.last_bucket)
                quadrant = self.last_quadrant
                if quadrant is not None and self.quadrants[quadrant]["photos"] > 0:
                    self.quadrants[quadrant]["photos"] -= 1
            if all(item["photos"] >= 4 for item in self.quadrants):
                self.seen.clear()
                for item in self.quadrants:
                    item["photos"] = 0
                    item["blocked"] = False
            self.running = True
            self.stop = False
            self.status = "Looking again."
            query = self.query
        threading.Thread(target=self._run, daemon=True).start()
        return f"Looking again for {query}."

    def force_land(self):
        # Stick commands cancel a landing, so the search loop is told to
        # stop and the stick sender stays quiet until the drone is down.
        self.stop = True
        self.landing = True
        self.land_until = time.time() + 25
        self.link.set_sticks(0, 0, 0, 0)
        self.link.rc_pause_until = time.time() + 12
        self.link.quiet_until = time.time() + 12
        self.link.send_nowait("land")
        self.link.note("force land")
        with self.lock:
            self.status = "Force landing."
            self.alert = ""
            self.running = False
        return "landing"

    def _run(self):
        link = self.link
        try:
            self._fly_scan()
        except Exception as exc:
            with self.lock:
                self.status = str(exc)[:180]
        finally:
            if not self.landing:
                link.send_rc(0, 0, 0, 0)
                link.rc_pause_until = time.time() + 0.5
            with self.lock:
                self.running = False

    def _fly_scan(self):
        link = self.link
        bat = link._battery()
        temp = link._temp()
        if bat is not None and bat <= 25:
            self._say(f"Battery is {bat}%. Too low to start a search.")
            return
        if temp is not None and temp >= 90:
            self._say(f"Board is {temp}°. Too hot to take off.")
            return
        link.rc_pause_until = time.time() + 20
        if (link._height() or 0) < 20:
            self._say("Taking off.")
            ok, reply = link.action("takeoff")
            if not ok:
                self._say(reply)
                return
            self._wait_height(30, 12)
        if self.stop:
            return
        self._say("Climbing to 1.6 m.")
        self._climb()
        while not self.stop and not self.found:
            if self._battery_low():
                self._finish_battery()
                return
            self._scan_here()
            if self.stop or self.found:
                return
            if self._battery_low():
                self._finish_battery()
                return
            heading = self._best_heading()
            if heading is None:
                self._hold_for_battery("No open direction.")
                return
            self.last_move = heading
            if not self._move_forward(heading, 100):
                self._hold_for_battery("Could not move.")
                return
            if (link._height() or 0) < 140 and not self.stop:
                self._climb()

    def _battery_low(self):
        bat = self.link._battery()
        return bat is not None and bat <= 25

    def _finish_battery(self):
        bat = self.link._battery()
        if not self.landing:
            self.force_land()
        self._say(f"Battery is {bat}%. Mission finished.")

    def _hold_for_battery(self, reason):
        self._say(f"{reason} Holding until the battery reaches 25%.")
        while not self.stop and not self.found and not self._battery_low():
            time.sleep(2)
        if self._battery_low() and not self.stop and not self.landing:
            self._finish_battery()

    def _scan_here(self):
        link = self.link
        origin = link._yaw() or 0.0
        self.views = []
        with self.lock:
            self.seen.clear()
            for item in self.quadrants:
                item["photos"] = 0
                item["blocked"] = False
            self.visited.add(f"{math.floor(self.px / CELL_CM)},{math.floor(self.py / CELL_CM)}")
        from grok_scene import look_for

        offsets = (-34, -12, 12, 34)
        for quadrant in range(4):
            if self.stop or self.found or self._battery_low():
                if self._battery_low() and not self.found and not self.landing:
                    self._finish_battery()
                return
            center = origin + quadrant * 90
            for offset in offsets:
                if self.stop or self.found:
                    return
                if self._battery_low():
                    self._finish_battery()
                    return
                heading = center + offset
                bucket = int(round(heading / 20.0) * 20) % 360
                if bucket in self.seen:
                    continue
                self._say(f"Quadrant {quadrant + 1}, turning.")
                link.rc_pause_until = time.time() + 25
                self._turn_to(heading)
                if self.stop:
                    return
                frame = self._grab()
                if frame is None:
                    self._say("No camera frame.")
                    continue
                self.seen.add(bucket)
                self.last_bucket = bucket
                self.last_quadrant = quadrant
                bgr = self._decode(frame)
                link.rc_pause_until = time.time() + 25
                try:
                    verdict = look_for(bgr, self.query)
                except Exception as exc:
                    self._say(str(exc)[:160])
                    continue
                blocked = bool(verdict["obstacle"])
                self._save(frame, heading, verdict)
                self._paint(heading, blocked)
                self.views.append({"heading": heading, "blocked": blocked})
                with self.lock:
                    self.quadrants[quadrant]["photos"] += 1
                    self.quadrants[quadrant]["blocked"] = self.quadrants[quadrant]["blocked"] or blocked
                    self.status = verdict["detail"] or self.status
                if verdict["found"]:
                    with self.lock:
                        self.found = True
                        self.found_jpeg = frame
                        self.found_at = int(time.time())
                        self.alert = f"Found: {self.query}"
                        self.status = verdict["detail"] or "Holding this direction."
                    link.note(f"search found {self.query}")
                    link.send_rc(0, 0, 0, 0)
                    return

    def _best_heading(self):
        """Clearest forward heading with two green blocks that were not searched yet."""
        best = None
        best_run = 1
        for view in self.views:
            if view["blocked"]:
                continue
            heading = view["heading"]
            run = self._clear_run(heading)
            if run < 2:
                continue
            ahead = self._cell_at(heading, 100)
            if f"{ahead[0]},{ahead[1]}" in self.visited:
                continue
            if self.last_move is not None:
                turn = (heading - self.last_move + 540) % 360 - 180
                if abs(turn) > 135 and run < 6:
                    continue
            if run > best_run:
                best_run = run
                best = heading
        return best

    def _clear_run(self, heading):
        count = 0
        with self.lock:
            for dist in range(CELL_CM, CELL_CM * 11, CELL_CM):
                cell = self._cell_at(heading, dist)
                if self.cells.get(f"{cell[0]},{cell[1]}") != "green":
                    break
                count += 1
        return count

    def _move_forward(self, heading, distance_cm):
        """Fly forward along heading. Position comes from the drone's own speed."""
        link = self.link
        self._say("Moving two blocks into the open area.")
        self._turn_to(heading)
        if self.stop or self.landing:
            return False
        link.quiet_until = time.time() + 12
        link.rc_pause_until = time.time() + 12
        link.send_nowait(f"forward {int(distance_cm)}")
        link.note(f"forward {int(distance_cm)}")
        began = time.time()
        last = began
        dx = dy = 0.0
        saw_motion = False
        while time.time() - began < 9 and not self.stop:
            now = time.time()
            dt = min(0.4, now - last)
            last = now
            try:
                vgx = float(link.state.get("vgx") or 0)
                vgy = float(link.state.get("vgy") or 0)
            except (TypeError, ValueError):
                vgx = vgy = 0.0
            yaw = link._yaw() or heading
            rad = math.radians(yaw)
            dx += (vgx * 10.0 * math.cos(rad) - vgy * 10.0 * math.sin(rad)) * dt
            dy += (vgx * 10.0 * math.sin(rad) + vgy * 10.0 * math.cos(rad)) * dt
            if math.hypot(vgx, vgy) > 0.8:
                saw_motion = True
            if saw_motion and math.hypot(vgx, vgy) < 0.4 and time.time() - began > 1.5:
                break
            time.sleep(0.1)
        if math.hypot(dx, dy) < 30:
            self._say("The drone did not move. Hovering.")
            return False
        self.px += dx
        self.py += dy
        return True

    def _cell_at(self, heading, dist):
        rad = math.radians(heading)
        x = self.px + dist * math.cos(rad)
        y = self.py + dist * math.sin(rad)
        return math.floor(x / CELL_CM), math.floor(y / CELL_CM)

    def _say(self, text):
        self.link.note(text)
        with self.lock:
            self.status = text

    def _climb(self):
        link = self.link
        began = time.time()
        while time.time() - began < 28 and not self.stop:
            height = link._height() or 0
            link.rc_pause_until = time.time() + 4
            if height >= CEILING_CM - 5:
                link.send_rc(0, 0, 0, 0)
                return
            if height > CEILING_CM:
                link.send_rc(0, 0, -12, 0)
            else:
                link.send_rc(0, 0, 16, 0)
            time.sleep(0.15)
        link.send_rc(0, 0, 0, 0)

    def _wait_height(self, target, seconds):
        began = time.time()
        while time.time() - began < seconds and not self.stop:
            if (self.link._height() or 0) >= target:
                return
            time.sleep(0.3)

    def _turn_to(self, target):
        link = self.link
        began = time.time()
        while time.time() - began < 18 and not self.stop:
            yaw = link._yaw()
            link.rc_pause_until = time.time() + 3
            if yaw is None:
                time.sleep(0.2)
                continue
            error = (target - yaw + 540) % 360 - 180
            if abs(error) < 12:
                link.send_rc(0, 0, 0, 0)
                time.sleep(0.3)
                return
            link.send_rc(0, 0, 0, 16 if error > 0 else -16)
            time.sleep(0.12)
        link.send_rc(0, 0, 0, 0)

    def _grab(self):
        frame = self.link.jpeg
        if not frame:
            time.sleep(0.4)
            frame = self.link.jpeg
        return frame

    def _decode(self, frame):
        import numpy as np

        return cv2.imdecode(np.frombuffer(frame, dtype=np.uint8), cv2.IMREAD_COLOR)

    def _save(self, frame, heading, verdict):
        folder = ROOT / "captures" / "search"
        folder.mkdir(parents=True, exist_ok=True)
        stem = time.strftime("%Y%m%d_%H%M%S") + f"_{int(round(heading)) % 360:03d}"
        (folder / f"{stem}.jpg").write_bytes(frame)
        (folder / f"{stem}.json").write_text(
            json.dumps(
                {
                    "query": self.query,
                    "heading": round(heading, 1),
                    "found": bool(verdict["found"]),
                    "obstacle": bool(verdict["obstacle"]),
                    "detail": verdict["detail"],
                }
            ),
            encoding="utf-8",
        )

    def _paint(self, heading, blocked):
        # The first 2 m is open. A block, if any, is farther ahead and only
        # in the center of the camera, which is the drone's flight direction.
        with self.lock:
            added = 0
            for dist in range(CELL_CM, CELL_CM * 11, CELL_CM):
                for delta in (-24, -12, 0, 12, 24):
                    if added >= 50:
                        return
                    far = dist >= 250
                    centre = delta in (-12, 0, 12)
                    colour = "red" if blocked and far and centre else "green"
                    cell = self._cell_at(heading + delta, dist)
                    key = f"{cell[0]},{cell[1]}"
                    if self.cells.get(key) == "red" and colour == "green":
                        added += 1
                        continue
                    self.cells[key] = colour
                    added += 1
