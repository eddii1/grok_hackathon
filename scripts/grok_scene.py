"""Ask Grok to label a saved drone photo.

Labels are ground, wall, furniture, table, instrument, person, or empty.
The key is read from credential.txt at the repo root and is never written
into the code. Results are cached in captures/labels so a restart does
not send the same photo again.
"""

import base64
import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
LABELS = ("ground", "wall", "furniture", "table", "instrument", "person", "empty")
MODELS = (
    "grok-4-fast-non-reasoning",
    "grok-4-1-fast-non-reasoning",
    "grok-4-fast",
    "grok-2-vision-1212",
    "grok-4",
)
PROMPT = """You label one indoor photo for a drone map.
Split the image into 8 columns and 6 rows. Column 0 is the left edge. Row 0 is the top edge.
Use exactly one label per cell:
- ground: floor that can be flown over
- wall: wall, window, door, or a screen mounted on the wall
- table: table or desk
- furniture: chair, shelf, bench, cabinet
- instrument: laptop, tool, machine, musical instrument, drone, or other device
- person: a person
- empty: too dark or too blurred to tell
Return JSON only, with all 48 cells:
{"summary":"one short sentence","cells":[{"c":0,"r":0,"label":"wall"}]}"""

_model = None


def _key():
    raw = (ROOT / "credential.txt").read_text(encoding="utf-8")
    for part in raw.replace(":", " ").split():
        if part.startswith("xai-"):
            return part
    raise RuntimeError("credential.txt has no xai key")


def _cache_path(digest):
    folder = ROOT / "captures" / "labels"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{digest}.json"


def classify_bgr(bgr, name=""):
    ok, buf = cv2.imencode(".jpg", _fit(bgr), [int(cv2.IMWRITE_JPEG_QUALITY), 70])
    if not ok:
        raise RuntimeError("could not encode the photo")
    payload = buf.tobytes()
    digest = hashlib.sha256(payload).hexdigest()[:20]
    cached = _cache_path(digest)
    if cached.exists():
        data = json.loads(cached.read_text(encoding="utf-8"))
        data["file"] = name or data.get("file", "")
        return _clean(data)
    data = _ask(payload)
    data["file"] = name
    data["id"] = digest
    cached.write_text(json.dumps(data), encoding="utf-8")
    return data


def _fit(bgr):
    height, width = bgr.shape[:2]
    if width <= 640:
        return bgr
    return cv2.resize(bgr, (640, int(height * 640 / width)))


def look_for(bgr, query):
    """Ask Grok if this frame shows the query, and if the way ahead is blocked."""
    ok, buf = cv2.imencode(".jpg", _fit(bgr), [int(cv2.IMWRITE_JPEG_QUALITY), 70])
    if not ok:
        raise RuntimeError("could not encode the photo")
    prompt = (
        "This photo is from a small indoor drone with a small wide-angle camera. "
        "It is hovering at about 1.6 m, chest height. The lens makes nearby things look large, "
        "so the edges of the frame are not the flight path.\n"
        "The operator asked for: " + str(query)[:200] + "\n"
        "The drone flies straight ahead at its own height. Judge only the center of the photo: "
        "a vertical band about one fifth of the width, through the middle. Those center pixels are its direction.\n"
        "found: true only if the requested person or object is clearly visible and every detail matches. "
        "A different hat, shirt, or a similar person is not a match. If you are unsure, found is false.\n"
        "obstacle: true only if that center band shows a wall, person, furniture, or other solid object "
        "at the drone's height, farther ahead, that it would hit by flying forward. "
        "There is no obstacle right in front of the camera. Floor, ceiling, and the left and right edges do not count.\n"
        'Return JSON only: {"found":false,"obstacle":false,"detail":"one short sentence"}'
    )
    text = _chat(buf.tobytes(), prompt)
    data = json.loads(_json_text(text))
    return {
        "found": bool(data.get("found")),
        "obstacle": bool(data.get("obstacle")),
        "detail": str(data.get("detail", ""))[:240],
    }


def _chat(jpeg, prompt):
    global _model
    body_models = [_model] if _model else list(MODELS)
    encoded = base64.b64encode(jpeg).decode("ascii")
    last_error = "Grok did not answer"
    for model in body_models:
        if not model:
            continue
        request = {
            "model": model,
            "temperature": 0,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + encoded}},
                    ],
                }
            ],
        }
        raw = json.dumps(request).encode("utf-8")
        req = urllib.request.Request(
            "https://api.x.ai/v1/chat/completions",
            data=raw,
            headers={"Authorization": "Bearer " + _key(), "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                reply = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:180]
            last_error = f"{model}: {exc.code} {detail}"
            continue
        text = reply["choices"][0]["message"]["content"]
        _model = model
        return text
    raise RuntimeError(last_error)


def _ask(jpeg):
    parsed = _clean(json.loads(_json_text(_chat(jpeg, PROMPT))))
    parsed["model"] = _model or ""
    return parsed


def _json_text(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0]
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text


def _clean(data):
    cells = []
    seen = set()
    for cell in data.get("cells") or []:
        try:
            col, row = int(cell["c"]), int(cell["r"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (0 <= col < 8 and 0 <= row < 6) or (col, row) in seen:
            continue
        label = str(cell.get("label", "empty")).lower().strip()
        if label == "floor":
            label = "ground"
        if label not in LABELS:
            label = "empty"
        cells.append({"c": col, "r": row, "label": label})
        seen.add((col, row))
    for row in range(6):
        for col in range(8):
            if (col, row) not in seen:
                cells.append({"c": col, "r": row, "label": "empty"})
    return {
        "summary": str(data.get("summary", ""))[:240],
        "file": data.get("file", ""),
        "model": data.get("model", ""),
        "cells": cells,
    }
