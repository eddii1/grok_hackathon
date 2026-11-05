"""MiDaS v2.1 small, run locally on a saved camera photo.

The network returns inverse depth (brighter means closer). Callers scale
it to centimetres with the drone's height. The weights live in
models/midas_small.onnx and are loaded once.
"""

from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "models" / "midas_small.onnx"
SIZE = 256

_net = None


def load():
    global _net
    if _net is not None:
        return _net
    if not MODEL.exists():
        raise FileNotFoundError(f"missing {MODEL}")
    net = cv2.dnn.readNet(str(MODEL))
    _net = net
    return net


def infer(bgr):
    """Return inverse depth at 256x256 and a colour JPEG of that map."""
    net = load()
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(rgb, (SIZE, SIZE), interpolation=cv2.INTER_CUBIC)
    mean = (0.485 * 255, 0.456 * 255, 0.406 * 255)
    blob = cv2.dnn.blobFromImage(resized, 1 / 255.0, (SIZE, SIZE), mean, swapRB=False, crop=False)
    blob /= np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(1, 3, 1, 1)
    net.setInput(blob)
    inv = net.forward().squeeze().astype(np.float32)
    if inv.ndim != 2:
        inv = inv.reshape(SIZE, SIZE)
    preview = _colour(inv)
    ok, buf = cv2.imencode(".jpg", preview, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
    if not ok:
        raise RuntimeError("depth preview encode failed")
    return inv, buf.tobytes()


def _colour(inv):
    lo, hi = np.percentile(inv, [2, 98])
    if hi <= lo:
        hi = lo + 1
    norm = np.clip((inv - lo) / (hi - lo), 0, 1)
    gray = (norm * 255).astype(np.uint8)
    return cv2.applyColorMap(gray, cv2.COLORMAP_MAGMA)
