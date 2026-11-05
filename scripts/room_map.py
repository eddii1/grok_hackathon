"""Room matrix from saved photos and a local depth model.

While mapping is on, each camera frame is written to captures/frames.
MiDaS small (models/midas_small.onnx) turns that photo into a depth map.
The depth is scaled with the drone's height, then written into 20 cm cells
that keep the colour of the pixels. The plan is captures/room_map.json.
A cell seen twice, or a person inside 70 cm, holds forward.
"""

import json
import math
import queue
import threading
import time
from pathlib import Path

CEILING_CM = 190
NEAR_CM = 70
CELL_CM = 20
HFOV = 69.0
VFOV = 52.0
KIND_TOP = {
    "ground": 0,
    "floor": 0,
    "wall": 160,
    "furniture": 90,
    "table": 75,
    "instrument": 40,
    "machine": 90,
    "person": 150,
}
KIND_RANK = {
    "ground": 0,
    "floor": 0,
    "wall": 1,
    "furniture": 2,
    "machine": 2,
    "table": 3,
    "instrument": 4,
    "person": 5,
}
FREE = {"ground", "floor", "empty"}


class RoomMap:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()
        self.points = []
        self.path_pts = []
        self.keyframes = []
        self.cells = {}
        self.view = []
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0
        self.yaw = 0.0
        self.localized = False
        self.obstacle_cm = None
        self.block_forward = False
        self.avoid = ""
        self.mapping = False
        self._live_cm = None
        self._last_sample = 0.0
        self._prev = None
        self._last_t = None
        self._last_snap = 0.0
        self._last_save = 0.0
        self._dirty = False
        self.frames = self.path.parent / "frames"
        self.saved = 0
        self.depth_done = 0
        self.depth_seq = 0
        self.depth_error = ""
        self.depth_jpeg = None
        self._queue = queue.Queue(maxsize=24)
        self.scene = {"summary": "", "file": "", "model": "", "cells": []}
        self.mesh = None
        self._seen = set()
        self._last_preview = 0.0
        self.load()
        threading.Thread(target=self._depth_loop, daemon=True).start()
        self._load_pending()
        self._queue_captures()
        self._best_scene()

    def load(self):
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self.points = data.get("points", [])[-5000:]
        self.path_pts = data.get("path", [])[-2000:]
        self.keyframes = data.get("keyframes", [])[-80:]
        self.cells = data.get("cells") or {}
        pose = data.get("pose") or {}
        self.x = float(pose.get("x", 0))
        self.y = float(pose.get("y", 0))
        self.z = float(pose.get("z", 0))
        self.yaw = float(pose.get("yaw", 0))
        if data.get("scene"):
            self.scene = data["scene"]

    def save(self):
        self.path.parent.mkdir(exist_ok=True)
        payload = {
            "ceiling_cm": CEILING_CM,
            "pose": self.snapshot()["pose"],
            "points": self.points[-5000:],
            "path": self.path_pts[-2000:],
            "keyframes": self.keyframes[-80:],
            "cells": self.cells,
            "scene": self.scene,
        }
        self.path.write_text(json.dumps(payload), encoding="utf-8")
        self._dirty = False
        self._last_save = time.time()

    def clear(self):
        with self.lock:
            self.points = []
            self.path_pts = []
            self.keyframes = []
            self.cells = {}
            self.view = []
            self.x = self.y = self.z = self.yaw = 0.0
            self.localized = False
            self._prev = None
            self._dirty = True
            self.save()

    def set_mapping(self, on):
        with self.lock:
            self.mapping = bool(on)
            self._last_sample = 0.0
            self._dirty = True
        return self.mapping

    def snapshot(self):
        return {
            "ceiling_cm": CEILING_CM,
            "pose": {
                "x": round(self.x, 1),
                "y": round(self.y, 1),
                "z": round(min(self.z, CEILING_CM), 1),
                "yaw": round(self.yaw, 1),
            },
            "localized": self.localized,
            "obstacle_cm": self.obstacle_cm,
            "block_forward": self.block_forward,
            "avoid": self.avoid,
            "mapping": self.mapping,
            "cell_cm": CELL_CM,
            "frames": self.saved,
            "depth_frames": self.depth_done,
            "depth_seq": self.depth_seq,
            "depth_ready": self.depth_jpeg is not None,
            "depth_model": "MiDaS small",
            "depth_error": self.depth_error,
            "scene": self.scene,
            "path": self.path_pts[-800:],
            "keyframes": len(self.keyframes),
            "cells": self._public_cells(),
            "counts": self._counts(),
            "view": self.view,
        }

    def tick(self, state):
        now = time.time()
        dt = 0.1 if self._last_t is None else min(0.4, now - self._last_t)
        self._last_t = now
        try:
            yaw = float(state.get("yaw", self.yaw))
            h = float(state.get("h", 0))
            vgx = float(state.get("vgx", 0))
            vgy = float(state.get("vgy", 0))
        except (TypeError, ValueError):
            return
        h = min(h, CEILING_CM)
        flying = h > 8
        with self.lock:
            self.yaw = yaw
            self.z = h
            if flying and self.mapping:
                rad = math.radians(yaw)
                c, s = math.cos(rad), math.sin(rad)
                fwd = vgx * 10.0 * dt
                left = vgy * 10.0 * dt
                self.x += fwd * c - left * s
                self.y += fwd * s + left * c
                if (
                    not self.path_pts
                    or _dist(self.path_pts[-1], self.x, self.y) > 8
                    or _yaw_delta(self.path_pts[-1].get("yaw", yaw), yaw) > 12
                ):
                    self.path_pts.append(
                        {
                            "x": round(self.x, 1),
                            "y": round(self.y, 1),
                            "z": round(h, 1),
                            "yaw": round(yaw, 1),
                        }
                    )
                    self._dirty = True
            self._apply_block()
            if self._dirty and now - self._last_save > 3:
                self.save()

    def see(self, bgr, state):
        try:
            import cv2
            import numpy as np
        except Exception:
            return
        small = cv2.cvtColor(cv2.resize(bgr, (80, 60)), cv2.COLOR_BGR2GRAY)
        thumb = cv2.resize(small, (16, 12)).astype(int).ravel().tolist()
        prev = self._prev
        self._prev = small
        dist = None
        if prev is not None:
            flow = cv2.calcOpticalFlowFarneback(prev, small, None, 0.5, 2, 12, 2, 5, 1.1, 0)
            ys, xs = np.mgrid[0:60, 0:80]
            dx = xs - 40
            dy = ys - 30
            radial = (flow[..., 0] * dx + flow[..., 1] * dy) / (np.sqrt(dx * dx + dy * dy) + 1)
            div = float(radial[18:42, 24:56].mean())
            try:
                speed = max(0.0, float(state.get("vgx", 0))) * 10.0
            except (TypeError, ValueError):
                speed = 0.0
            if div > 0.7:
                ttc = 14.0 / (div * 12.0)
                if speed >= 8:
                    dist = int(max(20, min(300, speed * ttc)))
                elif div > 1.6:
                    dist = 45
                else:
                    dist = 90
        now = time.time()
        pose = None
        live = False
        with self.lock:
            self._live_cm = dist
            if self.keyframes:
                self._match(thumb)
            if self.mapping and now - self._last_sample >= 0.8:
                self._last_sample = now
                pose = self._capture_pose(state)
                self._maybe_keyframe(thumb)
            elif now - self._last_preview >= 1.5:
                self._last_preview = now
                live = True
                pose = self._capture_pose(state)
            self._apply_block()
        if pose is None:
            return
        if live:
            pose["fuse"] = False
            pose["file"] = "live.jpg"
            self._write_photo(bgr, self.frames / "live.jpg", pose, counted=False)
        else:
            pose["fuse"] = float(pose["z"]) >= 30
            self._save_frame(bgr, pose)

    def _match(self, thumb):
        if len(self.keyframes) < 3:
            self.localized = False
            return
        if time.time() - self._last_snap < 2:
            return
        scored = []
        for frame in self.keyframes:
            sad = sum(abs(a - b) for a, b in zip(thumb, frame["thumb"]))
            scored.append((sad, frame))
        scored.sort(key=lambda item: item[0])
        best, winner = scored[0]
        second = scored[1][0]
        if best < 3200 and best < second * 0.85:
            self.x = float(winner["x"])
            self.y = float(winner["y"])
            self.yaw = float(winner["yaw"])
            self.localized = True
            self._last_snap = time.time()
            self._dirty = True
        else:
            self.localized = False

    def _capture_pose(self, state):
        def num(key, default):
            try:
                return float(state.get(key, default))
            except (TypeError, ValueError):
                return float(default)

        return {
            "x": round(self.x, 1),
            "y": round(self.y, 1),
            "z": round(min(max(num("h", self.z), 0), CEILING_CM), 1),
            "yaw": round(num("yaw", self.yaw), 1),
            "pitch": round(num("pitch", 0), 1),
            "fuse": True,
        }

    def _save_frame(self, bgr, pose):
        self.frames.mkdir(parents=True, exist_ok=True)
        name = time.strftime("%H%M%S") + f"_{int((time.time() % 1) * 1000):03d}.jpg"
        pose = dict(pose)
        pose["file"] = name
        self._write_photo(bgr, self.frames / name, pose, counted=True)
        with (self.frames / "index.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(pose) + "\n")

    def _write_photo(self, bgr, path, pose, counted):
        import cv2

        path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(path), bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        if counted:
            with self.lock:
                self.saved += 1
        try:
            self._queue.put_nowait((str(path), pose))
        except queue.Full:
            with self.lock:
                self.depth_error = "depth model is still on the previous photo"

    def _load_pending(self):
        index = self.frames / "index.jsonl"
        done_path = self.frames / "depth_done.txt"
        done = set(done_path.read_text(encoding="utf-8").split()) if done_path.exists() else set()
        self.depth_done = len(done)
        if not index.exists():
            return
        for line in index.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            self.saved += 1
            if item.get("file") in done:
                continue
            self._offer(item)

    def _best_scene(self):
        folder = self.path.parent / "labels"
        if not folder.exists():
            return
        best = None
        best_score = -1
        for path in folder.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            labels = [cell.get("label") for cell in data.get("cells") or []]
            if labels.count("person") > 28:
                continue
            score = sum(label in ("table", "furniture", "instrument") for label in labels)
            if score > best_score:
                best, best_score = data, score
        if best:
            self.scene = best

    def _queue_captures(self):
        # Photos already taken, before mapping stored a pose. Place them at
        # takeoff with the camera at 1.2 m so the lab picture becomes blocks.
        done_path = self.frames / "depth_done.txt"
        done = set(done_path.read_text(encoding="utf-8").split()) if done_path.exists() else set()
        photos = sorted(p for p in self.path.parent.glob("*.jpg") if p.is_file())
        for photo in photos:
            if photo.name in done or photo.name in self._seen:
                continue
            pose = {
                "x": 0,
                "y": 0,
                "z": 120,
                "yaw": 0,
                "pitch": 8,
                "fuse": True,
                "file": photo.name,
            }
            self._seen.add(photo.name)
            try:
                self._queue.put_nowait((str(photo), pose))
            except queue.Full:
                self._seen.discard(photo.name)
                break

    def _offer(self, item):
        name = item.get("file")
        if not name or name in self._seen:
            return
        path = self.frames / name
        if not path.exists():
            return
        self._seen.add(name)
        try:
            self._queue.put_nowait((str(path), item))
        except queue.Full:
            self._seen.discard(name)

    def _mark_done(self, name):
        if not name or name == "live.jpg":
            return
        self.frames.mkdir(parents=True, exist_ok=True)
        with (self.frames / "depth_done.txt").open("a", encoding="utf-8") as handle:
            handle.write(name + "\n")
        self.depth_done += 1

    def _depth_loop(self):
        import cv2

        from depth_model import infer
        from grok_scene import classify_bgr

        self._ensure_mesh()
        while True:
            path, pose = self._queue.get()
            try:
                bgr = cv2.imread(path)
                if bgr is None:
                    continue
                inv, preview = infer(bgr)
                scene = classify_bgr(bgr, Path(path).name) if pose.get("fuse") else None
                with self.lock:
                    self.depth_jpeg = preview
                    self.depth_seq += 1
                    if scene is not None:
                        err = self._fuse(bgr, inv, pose, scene)
                        if "left out" not in (err or ""):
                            self.scene = scene
                        self._mark_done(pose.get("file", ""))
                        self.depth_error = err
                        self._dirty = True
            except Exception as exc:
                with self.lock:
                    self.depth_error = str(exc)[:180]

    def _mesh_photo(self):
        folder = self.path.parent
        best, score = None, -1
        label_dir = folder / "labels"
        if label_dir.exists():
            for path in label_dir.glob("*.json"):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                name = data.get("file") or ""
                if not name or name == "remote_live.jpg" or not (folder / name).exists():
                    continue
                labels = [cell.get("label") for cell in data.get("cells") or []]
                if labels.count("person") > 28:
                    continue
                value = sum(label in ("table", "furniture", "instrument") for label in labels)
                if value > score:
                    best, score = folder / name, value
        if best:
            return best
        photos = [p for p in sorted(folder.glob("*.jpg")) if p.name != "remote_live.jpg"]
        return photos[-1] if photos else None

    def _ensure_mesh(self):
        cache = self.path.parent / "room_mesh.json"
        if cache.exists():
            try:
                data = json.loads(cache.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = None
            if data and data.get("source") == "video" and data.get("xyz"):
                with self.lock:
                    self.mesh = data
                    self.depth_error = data.get("note") or ""
                return
        try:
            from photogram import build

            mesh = build()
        except Exception as exc:
            with self.lock:
                self.depth_error = str(exc)[:180]
            return
        cache.write_text(json.dumps(mesh), encoding="utf-8")
        with self.lock:
            self.mesh = mesh
            self.depth_error = mesh.get("note") or ""

    def _build_mesh(self, bgr, inv, name):
        import cv2
        import numpy as np

        cols, rows = 64, 48
        small = cv2.resize(bgr, (cols, rows))
        rel = cv2.resize((1.0 / np.maximum(inv, 1e-3)).astype("float32"), (cols, rows))
        near, far = np.percentile(rel, [8, 92])
        span = float(far - near) if far > near else 1e-6
        tan_h = math.tan(math.radians(HFOV / 2))
        tan_v = math.tan(math.radians(VFOV / 2))
        dist = np.empty((rows, cols), dtype="float32")
        xyz = []
        rgb = []
        for v in range(rows):
            for u in range(cols):
                depth = 40 + (float(rel[v, u]) - float(near)) / span * 240
                depth = min(320.0, max(30.0, depth))
                dist[v, u] = depth
                x = ((u + 0.5) / cols - 0.5) * 2 * depth * tan_h
                y = (0.5 - (v + 0.5) / rows) * 2 * depth * tan_v
                blue, green, red = (int(ch) for ch in small[v, u])
                xyz.extend((round(x, 1), round(y, 1), round(depth, 1)))
                rgb.extend((red, green, blue))
        faces = []
        for v in range(rows - 1):
            for u in range(cols - 1):
                quad = (dist[v, u], dist[v, u + 1], dist[v + 1, u], dist[v + 1, u + 1])
                if max(quad) / max(min(quad), 1) > 1.35:
                    continue
                a = v * cols + u
                faces.extend((a, a + 1, a + cols, a + 1, a + cols + 1, a + cols))
        return {"file": name, "xyz": xyz, "rgb": rgb, "faces": faces}

    def _fuse(self, bgr, inv, pose, scene=None):
        import cv2
        import numpy as np

        height = float(pose["z"])
        pitch = float(pose["pitch"])
        down = 0.32 * VFOV - pitch
        if height < 30 or down < 5:
            return "photo saved; the depth map needs the drone above 30 cm"
        small = cv2.resize(bgr, (96, 72))
        rel = cv2.resize((1.0 / np.maximum(inv, 1e-3)).astype("float32"), (96, 72))
        labels = {(int(cell["c"]), int(cell["r"])): cell["label"] for cell in (scene or {}).get("cells", [])}
        named = list(labels.values())
        if named.count("person") > 28 and sum(label in ("ground", "wall", "table", "furniture", "instrument") for label in named) < 12:
            return "close photo labeled, left out of the room blocks"
        # MiDaS is relative. Stretch the near and far parts of this photo
        # across 0.4 m to 2.8 m. A floor-plane scale blows up when the
        # bottom of the picture is a table or a person, not the ground.
        near, far = np.percentile(rel, [8, 92])
        if far <= near:
            far = near + 1e-6
        span = float(far - near)
        yaw = math.radians(float(pose["yaw"]))
        c, s = math.cos(yaw), math.sin(yaw)
        tan_h = math.tan(math.radians(HFOV / 2))
        tan_v = math.tan(math.radians(VFOV / 2))
        for v in range(0, 72, 3):
            for u in range(0, 96, 3):
                dist = 40 + (float(rel[v, u]) - near) / span * 240
                dist = min(320, max(30, dist))
                x_cam = ((u + 0.5) / 96 - 0.5) * 2 * dist * tan_h
                y_cam = ((v + 0.5) / 72 - 0.5) * 2 * dist * tan_v
                wz = height - y_cam
                wx = float(pose["x"]) + dist * c + x_cam * s
                wy = float(pose["y"]) + dist * s - x_cam * c
                blue, green, red = (int(ch) for ch in small[v, u])
                label = labels.get((min(7, u * 8 // 96), min(5, v * 6 // 72)), "empty")
                if label == "empty":
                    label = "ground" if wz < 22 else ""
                if not label:
                    continue
                if label in FREE:
                    self._paint(wx, wy, "ground", (red, green, blue), False)
                    continue
                cap = {"wall": 190, "table": 100, "furniture": 130, "instrument": 90, "person": 175}.get(label, 120)
                top = min(cap, max(KIND_TOP.get(label, 40), wz))
                self._paint(wx, wy, label, (red, green, blue), True, top=top)
        return ""

    def _paint(self, x, y, kind, rgb, occupied, top=None):
        i = math.floor(x / CELL_CM)
        j = math.floor(y / CELL_CM)
        if abs(i) > 300 or abs(j) > 300:
            return
        if len(self.cells) > 4000 and f"{i},{j}" not in self.cells:
            return
        key = f"{i},{j}"
        cell = self.cells.get(key)
        if cell is None:
            cell = {"i": i, "j": j, "occ": 0, "free": 0, "r": rgb[0], "g": rgb[1], "b": rgb[2], "kind": "floor", "top": 0}
            self.cells[key] = cell
        if occupied:
            cell["occ"] = min(8, cell["occ"] + 1)
            n = cell["occ"]
            cell["r"] = int((cell["r"] * (n - 1) + rgb[0]) / n)
            cell["g"] = int((cell["g"] * (n - 1) + rgb[1]) / n)
            cell["b"] = int((cell["b"] * (n - 1) + rgb[2]) / n)
            if KIND_RANK[kind] >= KIND_RANK.get(cell["kind"], 0):
                cell["kind"] = kind
            cell["top"] = min(CEILING_CM, max(cell["top"], int(top if top is not None else KIND_TOP[kind])))
        else:
            cell["free"] = min(8, cell["free"] + 1)
            if cell["occ"] < 1:
                cell["kind"] = "ground"
                cell["top"] = 0
                n = cell["free"]
                cell["r"] = int((cell["r"] * (n - 1) + rgb[0]) / n)
                cell["g"] = int((cell["g"] * (n - 1) + rgb[1]) / n)
                cell["b"] = int((cell["b"] * (n - 1) + rgb[2]) / n)
        self._dirty = True

    def _occupied(self, cell):
        return cell["kind"] not in FREE and cell["occ"] >= 1 and cell["occ"] >= cell["free"]

    def _apply_block(self):
        hits_l = hits_r = 0
        nearest = None
        for dist in (30, 50, 70, 90):
            for off, bucket in ((-24, "l"), (0, "c"), (24, "r")):
                rad = math.radians(self.yaw + off)
                cell = self.cells.get(
                    f"{math.floor((self.x + dist * math.cos(rad)) / CELL_CM)},"
                    f"{math.floor((self.y + dist * math.sin(rad)) / CELL_CM)}"
                )
                if not cell or not self._occupied(cell):
                    continue
                trusted = cell["occ"] >= 2 or (cell["kind"] == "person" and dist <= NEAR_CM)
                if bucket == "l":
                    hits_l += 1
                elif bucket == "r":
                    hits_r += 1
                if trusted and dist <= NEAR_CM and nearest is None:
                    nearest = dist
        live = self._live_cm is not None and self._live_cm < NEAR_CM
        self.block_forward = live or nearest is not None
        if nearest is not None and (self._live_cm is None or nearest < self._live_cm):
            self.obstacle_cm = nearest
        else:
            self.obstacle_cm = self._live_cm
        if hits_l > hits_r:
            self.avoid = "right"
        elif hits_r > hits_l:
            self.avoid = "left"
        else:
            self.avoid = ""

    def _public_cells(self):
        out = []
        for cell in self.cells.values():
            occupied = self._occupied(cell)
            if not occupied and cell["free"] < 1:
                continue
            out.append(
                {
                    "i": cell["i"],
                    "j": cell["j"],
                    "kind": cell["kind"] if occupied else "ground",
                    "top": cell["top"] if occupied else 0,
                    "r": cell["r"],
                    "g": cell["g"],
                    "b": cell["b"],
                    "n": cell["occ"],
                }
            )
        return out

    def _counts(self):
        counts = {"ground": 0, "wall": 0, "furniture": 0, "table": 0, "instrument": 0, "person": 0}
        for cell in self._public_cells():
            counts[cell["kind"]] = counts.get(cell["kind"], 0) + 1
        return counts

    def _maybe_keyframe(self, thumb):
        if self.keyframes:
            last = self.keyframes[-1]
            moved = _dist(last, self.x, self.y)
            turned = abs(float(last["yaw"]) - self.yaw) % 360
            turned = min(turned, 360 - turned)
            if moved < 25 and turned < 18:
                return
        self.keyframes.append(
            {
                "x": round(self.x, 1),
                "y": round(self.y, 1),
                "z": round(self.z, 1),
                "yaw": round(self.yaw, 1),
                "thumb": thumb,
            }
        )
        if len(self.keyframes) > 80:
            del self.keyframes[:20]
        self._dirty = True


def _dist(point, x, y):
    return math.hypot(float(point["x"]) - x, float(point["y"]) - y)


def _yaw_delta(a, b):
    gap = abs(float(a) - float(b)) % 360
    return min(gap, 360 - gap)


ROOM_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Room map</title>
<style>
  :root { --ink:#14201c; --paper:#f4efe4; --line:#d9d0c0; --leaf:#1f6b4a; --clay:#c4552a; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--paper); color:var(--ink); font-family: "Segoe UI", sans-serif; }
  header { display:flex; justify-content:space-between; gap:16px; align-items:flex-end; padding:18px 22px 10px; }
  h1 { margin:0; font-size:28px; letter-spacing:-0.03em; }
  a { color:var(--leaf); }
  .read { display:flex; gap:18px; font-variant-numeric: tabular-nums; }
  .read b { display:block; font-size:22px; font-weight:650; }
  .read span { color:#5c675f; font-size:13px; }
  .device { margin:6px 0 0; font-weight:750; display:flex; align-items:center; gap:8px; color:#9a3b28; }
  .device i { width:12px; height:12px; border-radius:50%; background:#c4552a; display:block; }
  .device.on { color:#1f6b4a; }
  .device.on i { background:#1f6b4a; }
  .warn { margin:0 22px; min-height:1.4em; color:var(--clay); font-weight:650; }
  .stage { display:grid; grid-template-columns: 1fr 300px; gap:12px; padding:8px 22px 22px; align-items:stretch; }
  canvas { width:100%; height:74vh; background:#1c2822; border-radius:16px; display:block; cursor:grab; }
  .side { background:#1c2822; color:var(--paper); border-radius:16px; padding:12px; display:flex; flex-direction:column; gap:8px; }
  .side .cam { width:100%; height:120px; object-fit:cover; border-radius:10px; background:#10140e; }
  .row { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
  button { font:inherit; font-weight:650; border:0; background:var(--ink); color:var(--paper); border-radius:10px; padding:10px 12px; cursor:pointer; }
  .side button { width:100%; }
  button.ghost { background:transparent; color:var(--paper); box-shadow:inset 0 0 0 1px rgba(244,239,228,.28); }
  button.go { background:var(--leaf); }
  button.stop { background:var(--clay); }
  .speed { display:flex; align-items:center; gap:8px; font-size:14px; }
  .speed input { flex:1; accent-color:#e2b656; }
  .sticks { display:flex; justify-content:space-between; }
  .pad { touch-action:none; width:112px; height:112px; border-radius:50%; background:#10140e; position:relative; border:8px solid #141910; }
  .pad i { width:36px; height:36px; border-radius:50%; background:var(--paper); position:absolute; left:50%; top:50%; transform:translate(-50%,-50%); pointer-events:none; }
  p.note { margin:0; color:#5c675f; }
  .side p.note { color:rgba(244,239,228,.62); }
  .grid { display:grid; grid-template-columns:repeat(8, 1fr); gap:2px; }
  .grid i { display:block; height:14px; border-radius:2px; }
  @media (max-width: 900px) { .stage { grid-template-columns: 1fr; } canvas { height:52vh; } }
</style>
</head>
<body>
<header>
  <div>
    <h1>Room from saved photos</h1>
    <p class="note">Drag to turn the cloud, scroll to zoom. It is built from the flight video: frames are matched and the shared points are triangulated. <a href="/">Remote</a></p>
    <p class="device" id="device"><i></i><span>Device not connected</span></p>
  </div>
  <div class="read">
    <div><span>place</span><b id="place">–</b></div>
    <div><span>height</span><b id="alt">–</b></div>
    <div><span>ahead</span><b id="ahead">clear</b></div>
    <div><span>photos / depth</span><b id="mem">–</b></div>
  </div>
</header>
<p class="warn" id="warn"></p>
<div class="stage">
<canvas id="view" width="1100" height="640"></canvas>
<aside class="side">
  <img id="cam" class="cam" alt="drone camera">
  <img id="depth" class="cam" alt="depth map">
  <div id="grid" class="grid" title="Grok labels"></div>
  <div class="row">
    <button id="takeoff" type="button">Take off</button>
    <button id="land" class="ghost" type="button">Land</button>
  </div>
  <button id="hover" class="ghost" type="button">Hover</button>
  <button id="spin" class="ghost" type="button">Turn 360</button>
  <label class="speed">Speed <b id="speedLabel">30</b>
    <input id="speed" type="range" min="10" max="60" value="30" step="5">
  </label>
  <div class="sticks">
    <div class="pad" id="padL" data-x="yaw" data-y="throttle"><i></i></div>
    <div class="pad" id="padR" data-x="roll" data-y="pitch"><i></i></div>
  </div>
  <button id="map" class="go" type="button">Start mapping</button>
  <button id="clear" class="ghost" type="button">Forget this room</button>
  <button id="cut" class="stop" type="button">Cut motors</button>
  <p class="note" id="hint">Start mapping in the air. Grok labels each saved photo, then the blocks are filled.</p>
  <p class="note" id="msg"></p>
</aside>
</div>
<script>
const canvas = document.getElementById("view");
const ctx = canvas.getContext("2d");
let map = { points: [], path: [], pose: {x:0,y:0,z:0,yaw:0}, ceiling_cm: 190 };
const axes = { roll: 0, pitch: 0, throttle: 0, yaw: 0 };
let CAP = 30;
const pads = {};
function setAxis(name, v) { axes[name] = Math.max(-CAP, Math.min(CAP, Math.round(v))); }
function bindPad(el) {
  const knob = el.querySelector("i");
  const xName = el.dataset.x, yName = el.dataset.y;
  pads[el.id] = {x:0, y:0};
  function place(px, py) {
    const r = el.getBoundingClientRect();
    const max = r.width / 2 - 22;
    let dx = px - (r.left + r.width / 2);
    let dy = py - (r.top + r.height / 2);
    const mag = Math.hypot(dx, dy) || 1;
    if (mag > max) { dx = dx / mag * max; dy = dy / mag * max; }
    knob.style.transform = `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px))`;
    pads[el.id] = {x: dx / max, y: -dy / max};
    setAxis(xName, pads[el.id].x * CAP);
    setAxis(yName, pads[el.id].y * CAP);
  }
  function reset() {
    knob.style.transform = "translate(-50%, -50%)";
    pads[el.id] = {x:0, y:0};
    setAxis(xName, 0); setAxis(yName, 0);
  }
  el.addEventListener("pointerdown", (e) => { el.setPointerCapture(e.pointerId); place(e.clientX, e.clientY); });
  el.addEventListener("pointermove", (e) => { if (el.hasPointerCapture(e.pointerId)) place(e.clientX, e.clientY); });
  el.addEventListener("pointerup", reset);
  el.addEventListener("pointercancel", reset);
}
bindPad(document.getElementById("padL"));
bindPad(document.getElementById("padR"));
const keys = {};
addEventListener("keydown", (e) => {
  if (["Space","KeyW","KeyA","KeyS","KeyD","KeyQ","KeyE","KeyR","KeyF"].includes(e.code)) e.preventDefault();
  keys[e.code] = true;
  if (e.code === "Space") act("stop");
});
addEventListener("keyup", (e) => { keys[e.code] = false; });
function fromKeys() {
  if (Object.values(pads).some(p => p.x || p.y)) return;
  setAxis("pitch", (keys.KeyW ? CAP : 0) + (keys.KeyS ? -CAP : 0));
  setAxis("roll", (keys.KeyD ? CAP : 0) + (keys.KeyA ? -CAP : 0));
  setAxis("yaw", (keys.KeyE ? CAP : 0) + (keys.KeyQ ? -CAP : 0));
  setAxis("throttle", (keys.KeyR ? CAP : 0) + (keys.KeyF ? -CAP : 0));
}
async function post(url, body) {
  const res = await fetch(url, {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify(body || {})});
  return res.json();
}
async function act(name) {
  const res = await post("/api/action", {name});
  document.getElementById("msg").textContent = res.reply || "";
}
document.getElementById("takeoff").onclick = () => act("takeoff");
document.getElementById("land").onclick = () => act("land");
document.getElementById("hover").onclick = () => act("stop");
document.getElementById("spin").onclick = () => act("spin");
document.getElementById("cut").onclick = () => { if (confirm("Cut the motors? The drone will drop.")) act("emergency"); };
const speedInput = document.getElementById("speed");
speedInput.oninput = () => { CAP = Number(speedInput.value); document.getElementById("speedLabel").textContent = CAP; };
speedInput.onchange = () => post("/api/speed", {value: CAP});
setInterval(() => { fromKeys(); post("/api/stick", axes).catch(() => {}); }, 80);
const cam = document.getElementById("cam");
cam.src = "/video?t=" + Date.now();

let mesh = null;
let yaw = 0.4, pitch = -0.25, zoom = 1.2;
let center = [0, 0, 80];
let dirty = true;
let drag = null;
function paintMesh() {
  ctx.fillStyle = "#1c2822";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.font = "13px Segoe UI";
  ctx.fillStyle = "#f4efe4";
  if (!mesh || !(mesh.xyz || []).length) {
    ctx.fillText("Building the cloud from the video…", 16, 28);
    return;
  }
  const xyz = mesh.xyz, rgb = mesh.rgb, faces = mesh.faces || [];
  const cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
  const proj = new Float32Array(xyz.length);
  const count = xyz.length / 3;
  for (let i = 0; i < count; i++) {
    const x = xyz[i * 3] - center[0];
    const y = xyz[i * 3 + 1] - center[1];
    const z = xyz[i * 3 + 2] - center[2];
    const x1 = x * cy + z * sy;
    const z1 = -x * sy + z * cy;
    const y2 = y * cp - z1 * sp;
    const z2 = y * sp + z1 * cp;
    const f = canvas.height * 0.85 * zoom / (z2 + 560);
    proj[i * 3] = canvas.width * 0.5 + x1 * f;
    proj[i * 3 + 1] = canvas.height * 0.5 - y2 * f;
    proj[i * 3 + 2] = z2;
  }
  const order = [];
  for (let t = 0; t < faces.length; t += 3) order.push([proj[faces[t] * 3 + 2] + proj[faces[t + 1] * 3 + 2] + proj[faces[t + 2] * 3 + 2], t]);
  order.sort((a, b) => b[0] - a[0]);
  for (let n = 0; n < order.length; n++) {
    const t = order[n][1];
    const i0 = faces[t], i1 = faces[t + 1], i2 = faces[t + 2];
    ctx.beginPath();
    ctx.moveTo(proj[i0 * 3], proj[i0 * 3 + 1]);
    ctx.lineTo(proj[i1 * 3], proj[i1 * 3 + 1]);
    ctx.lineTo(proj[i2 * 3], proj[i2 * 3 + 1]);
    ctx.closePath();
    ctx.fillStyle = "rgb(" + ((rgb[i0 * 3] + rgb[i1 * 3] + rgb[i2 * 3]) / 3 | 0) + "," + ((rgb[i0 * 3 + 1] + rgb[i1 * 3 + 1] + rgb[i2 * 3 + 1]) / 3 | 0) + "," + ((rgb[i0 * 3 + 2] + rgb[i1 * 3 + 2] + rgb[i2 * 3 + 2]) / 3 | 0) + ")";
    ctx.fill();
  }
  const dots = [];
  for (let i = 0; i < count; i++) dots.push([proj[i * 3 + 2], i]);
  dots.sort((a, b) => b[0] - a[0]);
  for (let n = 0; n < dots.length; n++) {
    const i = dots[n][1];
    const size = Math.max(3, Math.min(10, 420 * zoom / (proj[i * 3 + 2] + 560)));
    ctx.fillStyle = "rgb(" + rgb[i * 3] + "," + rgb[i * 3 + 1] + "," + rgb[i * 3 + 2] + ")";
    ctx.fillRect(proj[i * 3] - size / 2, proj[i * 3 + 1] - size / 2, size, size);
  }
  ctx.fillStyle = "#f4efe4";
  ctx.fillText("drag to turn, scroll to zoom  ·  " + (mesh.note || "video cloud"), 16, 26);
}
function frame() {
  if (dirty) { dirty = false; paintMesh(); }
  requestAnimationFrame(frame);
}
frame();
function takeMesh(data) {
  if (!data || !(data.xyz || []).length) return;
  mesh = data;
  let x = 0, y = 0, z = 0, n = data.xyz.length / 3;
  for (let i = 0; i < n; i++) { x += data.xyz[i * 3]; y += data.xyz[i * 3 + 1]; z += data.xyz[i * 3 + 2]; }
  center = [x / n, y / n, z / n];
  dirty = true;
}
async function pullMesh() {
  try { takeMesh(await (await fetch("/api/mesh")).json()); } catch (e) {}
}
pullMesh();
setInterval(() => { if (!mesh) pullMesh(); }, 1000);
canvas.addEventListener("pointerdown", (e) => {
  drag = {x: e.clientX, y: e.clientY, yaw, pitch};
  canvas.setPointerCapture(e.pointerId);
});
canvas.addEventListener("pointermove", (e) => {
  if (!drag) return;
  yaw = drag.yaw + (e.clientX - drag.x) * 0.008;
  pitch = Math.max(-1.1, Math.min(1.1, drag.pitch + (e.clientY - drag.y) * 0.008));
  dirty = true;
});
canvas.addEventListener("pointerup", () => { drag = null; });
canvas.addEventListener("pointercancel", () => { drag = null; });
canvas.addEventListener("wheel", (e) => {
  e.preventDefault();
  zoom = Math.max(0.45, Math.min(3.2, zoom * (e.deltaY > 0 ? 0.92 : 1.08)));
  dirty = true;
}, {passive: false});

async function poll() {
  try {
    map = await (await fetch("/api/map")).json();
    const device = document.getElementById("device");
    device.classList.toggle("on", !!map.connected);
    device.querySelector("span").textContent = map.connected
      ? "Device connected" + (map.drone_ip ? " · " + map.drone_ip : "")
      : "Device not connected";
    const p = map.pose || {};
    document.getElementById("place").textContent = (p.x || 0) + ", " + (p.y || 0);
    document.getElementById("alt").textContent = (p.z || 0) + " / " + (map.ceiling_cm || 190);
    document.getElementById("ahead").textContent = map.obstacle_cm == null ? "clear" : map.obstacle_cm + " cm";
    document.getElementById("mem").textContent = (map.depth_frames || 0) + " / " + (map.frames || 0);
    const depth = document.getElementById("depth");
    if (map.depth_ready && depth.dataset.seq !== String(map.depth_seq)) {
      depth.dataset.seq = String(map.depth_seq);
      depth.src = "/depth.jpg?t=" + map.depth_seq;
    }
    const btn = document.getElementById("map");
    btn.textContent = map.mapping ? "Stop mapping" : "Start mapping";
    btn.className = map.mapping ? "stop" : "go";
    const counts = map.counts || {};
    const summary = (counts.wall || 0) + " wall, " + (counts.table || 0) + " table, " + (counts.furniture || 0) + " furniture, " + (counts.instrument || 0) + " instrument, " + (counts.person || 0) + " person";
    const said = (map.scene && map.scene.summary) ? map.scene.summary + " " : "";
    document.getElementById("hint").textContent = map.depth_error
      ? map.depth_error
      : said + summary;
    const colors = {ground:"#8d7b62", wall:"#d7d0c4", furniture:"#c47a3a", table:"#e2b656", instrument:"#3d7ea6", person:"#c4552a", empty:"#2a332c"};
    const grid = document.getElementById("grid");
    const cells = (map.scene && map.scene.cells) || [];
    if (grid.dataset.file !== ((map.scene && map.scene.file) || "")) {
      grid.dataset.file = (map.scene && map.scene.file) || "";
      grid.innerHTML = cells.map(c => `<i title="${c.label}" style="background:${colors[c.label] || colors.empty}"></i>`).join("");
    }
    const bits = [];
    if (map.block_forward) bits.push(map.avoid ? "Obstacle ahead. Clearer side is " + map.avoid + ". Forward is held." : "Obstacle ahead. Forward is held.");
    if ((p.z || 0) >= (map.ceiling_cm || 190) - 5) bits.push("At the 1.9 m ceiling.");
    document.getElementById("warn").textContent = bits.join(" ");
  } catch (e) {}
}
setInterval(poll, 400);
poll();
document.getElementById("map").onclick = async () => {
  const on = !map.mapping;
  await fetch("/api/map/start", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({on})});
  poll();
};
document.getElementById("clear").onclick = () => fetch("/api/map/clear", {method:"POST"});
</script>
</body>
</html>
"""
