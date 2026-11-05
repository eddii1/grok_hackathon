"""Point cloud from a flight video, in the Metashape sense.

Frames are taken along the clip. Neighbouring frames are matched on
their own features, the camera step between them is recovered, and the
shared pixels are triangulated into one coloured cloud.
"""

import math
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
CAPTURES = ROOT / "captures"


def build():
    videos = sorted(CAPTURES.glob("*.mp4"), key=lambda p: p.stat().st_size, reverse=True)
    if not videos:
        raise RuntimeError("no flight video to build from")
    cloud = _from_video(videos[0])
    if cloud is None:
        raise RuntimeError("the video frames did not share enough points")
    return cloud


def _from_video(path):
    cap = cv2.VideoCapture(str(path))
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    sift = cv2.SIFT_create(nfeatures=1800)
    step = 3
    prev = None
    pose = (np.eye(3), np.zeros((3, 1)))
    points, colours = [], []
    linked = 0
    index = 0
    while index < count and linked < 12:
        cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = cap.read()
        index += step
        if not ok or frame is None:
            continue
        view = _view(frame, f"{path.name}#{index}")
        if view is None:
            continue
        view["kp"], view["des"] = sift.detectAndCompute(view["gray"], None)
        if prev is None:
            prev, prev_pose = view, pose
            continue
        pairs = _match(prev, view)
        if len(pairs) < 30:
            continue
        made = _pose(prev, view, pairs, prev_pose)
        if made is None:
            continue
        prev, prev_pose = view, made[0]
        points.extend(made[1])
        colours.extend(made[2])
        linked += 1
    cap.release()
    if len(points) < 60:
        return None
    xyz = np.array(points, dtype=np.float64)
    rgb = np.array(colours, dtype=np.int32)
    keep = _inliers(xyz)
    xyz, rgb = xyz[keep], rgb[keep]
    median = float(np.median(np.abs(xyz[:, 2])))
    if median > 1:
        xyz *= 150.0 / median
    return {
        "file": path.name,
        "source": "video",
        "note": f"{len(xyz)} points from {linked} frames of {path.name}",
        "count": int(len(xyz)),
        "xyz": [round(float(v), 2) for v in xyz.reshape(-1)],
        "rgb": [int(v) for v in rgb.reshape(-1)],
        "faces": _surface(xyz),
    }


def _video_frames():
    videos = sorted(CAPTURES.glob("*.mp4"), key=lambda p: p.stat().st_size, reverse=True)
    if not videos:
        return []
    cap = cv2.VideoCapture(str(videos[0]))
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    folder = CAPTURES / "frames"
    folder.mkdir(exist_ok=True)
    # About one frame a second, capped, so neighbours still overlap.
    step = max(8, count // 14)
    paths = []
    index = 0
    while index < count and len(paths) < 14:
        cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = cap.read()
        index += step
        if not ok or frame is None:
            continue
        path = folder / f"video_{len(paths):02d}.jpg"
        cv2.imwrite(str(path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        paths.append(path)
    cap.release()
    return paths


def _view(bgr, name):
    if bgr is None:
        return None
    height, width = bgr.shape[:2]
    scale = 800 / max(width, height)
    if scale < 1:
        bgr = cv2.resize(bgr, (int(width * scale), int(height * scale)))
        height, width = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    fx = (width / 2) / math.tan(math.radians(69 / 2))
    fy = (height / 2) / math.tan(math.radians(52 / 2))
    matrix = np.array([[fx, 0, width / 2], [0, fy, height / 2], [0, 0, 1]], dtype=np.float64)
    return {"name": name, "bgr": bgr, "gray": gray, "K": matrix}


def _sequence(views):
    poses = {0: (np.eye(3), np.zeros((3, 1)))}
    points, colours = [], []
    linked = 1
    for index in range(len(views) - 1):
        if index not in poses:
            poses[index] = (np.eye(3), np.zeros((3, 1)))
        pairs = _match(views[index], views[index + 1])
        if len(pairs) < 35:
            continue
        made = _pose(views[index], views[index + 1], pairs, poses[index])
        if made is None:
            continue
        poses[index + 1] = made[0]
        points.extend(made[1])
        colours.extend(made[2])
        linked += 1
    if len(points) < 80:
        return None
    xyz = np.array(points, dtype=np.float64)
    rgb = np.array(colours, dtype=np.int32)
    keep = _inliers(xyz)
    xyz, rgb = xyz[keep], rgb[keep]
    median = float(np.median(np.abs(xyz[:, 2])))
    if median > 1:
        xyz *= 150.0 / median
    faces = _surface(xyz)
    return {
        "file": views[0]["name"].split("_")[0] + " video",
        "source": "video",
        "note": f"{len(xyz)} points from {linked} video frames",
        "count": int(len(xyz)),
        "xyz": [round(float(v), 2) for v in xyz.reshape(-1)],
        "rgb": [int(v) for v in rgb.reshape(-1)],
        "faces": faces,
    }


def _match(a, b):
    if a["des"] is None or b["des"] is None or len(a["kp"]) < 8 or len(b["kp"]) < 8:
        return []
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    pairs = matcher.knnMatch(a["des"], b["des"], k=2)
    good = []
    for pair in pairs:
        if len(pair) < 2:
            continue
        first, second = pair
        if first.distance < 0.75 * second.distance:
            good.append((a["kp"][first.queryIdx].pt, b["kp"][second.trainIdx].pt))
    return good


def _pose(src, dst, pairs, src_pose):
    pts1 = np.array([a for a, _ in pairs], dtype=np.float64)
    pts2 = np.array([b for _, b in pairs], dtype=np.float64)
    essential, mask = cv2.findEssentialMat(pts1, pts2, src["K"], method=cv2.RANSAC, prob=0.999, threshold=1.2)
    if essential is None or mask is None:
        return None
    _, rotation, trans, mask = cv2.recoverPose(essential, pts1, pts2, src["K"], mask=mask)
    trans = trans * 20.0
    mask = mask.ravel().astype(bool)
    pts1, pts2 = pts1[mask], pts2[mask]
    if len(pts1) < 18:
        return None
    k = src["K"]
    proj_a = k @ np.hstack([np.eye(3), np.zeros((3, 1))])
    proj_b = k @ np.hstack([rotation, trans])
    hom = cv2.triangulatePoints(proj_a, proj_b, pts1.T, pts2.T)
    local = (hom[:3] / np.where(np.abs(hom[3]) < 1e-8, 1e-8, hom[3])).T
    finite = np.isfinite(local).all(axis=1) & (local[:, 2] > 5) & (local[:, 2] < 900)
    local, pts1 = local[finite], pts1[finite]
    if len(local) < 18:
        return None
    r_src, t_src = src_pose
    world = (r_src @ local.T).T + t_src.ravel()
    # Camera that saw the second frame, in the same world.
    r_dst = r_src @ rotation.T
    t_dst = t_src - r_dst @ trans
    colours = []
    for u, v in pts1:
        x = int(np.clip(u, 0, src["bgr"].shape[1] - 1))
        y = int(np.clip(v, 0, src["bgr"].shape[0] - 1))
        blue, green, red = (int(c) for c in src["bgr"][y, x])
        colours.append((red, green, blue))
    return (r_dst, t_dst), world.tolist(), colours


def _inliers(xyz):
    center = np.median(xyz, axis=0)
    dist = np.linalg.norm(xyz - center, axis=1)
    limit = float(np.percentile(dist, 90)) * 1.5
    return dist < max(limit, 1.0)


def _surface(xyz):
    pts = xyz[:, :2].astype(np.float32)
    sample = xyz[:: max(1, len(xyz) // 60)]
    gaps = []
    for point in sample:
        dist = np.linalg.norm(xyz - point, axis=1)
        dist = dist[dist > 0]
        if len(dist):
            gaps.append(dist.min())
    limit = float(np.median(gaps)) * 2.4 if gaps else 40.0
    span = pts.max(axis=0) - pts.min(axis=0)
    if min(float(span[0]), float(span[1])) < 2:
        return []
    rect = (
        int(pts[:, 0].min()) - 5,
        int(pts[:, 1].min()) - 5,
        int(span[0]) + 20,
        int(span[1]) + 20,
    )
    try:
        subdiv = cv2.Subdiv2D(rect)
        for point in pts:
            subdiv.insert((float(point[0]), float(point[1])))
    except cv2.error:
        return []
    nearest = {}
    for index, point in enumerate(pts):
        nearest[(round(float(point[0]), 1), round(float(point[1]), 1))] = index
    faces = []
    for tri in subdiv.getTriangleList():
        corners = [(tri[0], tri[1]), (tri[2], tri[3]), (tri[4], tri[5])]
        ids = []
        for corner in corners:
            key = (round(corner[0], 1), round(corner[1], 1))
            if key not in nearest:
                ids = []
                break
            ids.append(nearest[key])
        if len(set(ids)) < 3:
            continue
        edge = max(
            np.linalg.norm(xyz[ids[0]] - xyz[ids[1]]),
            np.linalg.norm(xyz[ids[1]] - xyz[ids[2]]),
            np.linalg.norm(xyz[ids[2]] - xyz[ids[0]]),
        )
        if edge > limit:
            continue
        faces.extend(int(i) for i in ids)
    return faces
