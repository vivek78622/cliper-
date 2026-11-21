"""Follow the player character so the 9:16 crop keeps them in the middle.

GTA's third-person camera does not keep the player at the exact centre of the 16:9 frame (over-the-shoulder,
aiming, cars, cutscenes), and a 9:16 crop shows only ~32% of the width, so a fixed crop loses them.
We sample frames, detect people with YOLOX-S (models/person_yolox_s_2022nov.onnx, OpenCV Zoo, Apache-2.0),
pick the player (the big person nearest the lower middle, continuing the previous pick), smooth the path,
and return keyframes (t, x_centre as a fraction of the frame width) for a panning crop.
"""
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(HERE, "models", "person_yolox_s_2022nov.onnx")
MODEL_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/object_detection_yolox/object_detection_yolox_2022nov.onnx"


def ensure_model():
    """Download the detector once (35 MB) on first use."""
    if not os.path.isfile(MODEL):
        import urllib.request
        os.makedirs(os.path.dirname(MODEL), exist_ok=True)
        tmp = MODEL + ".part"
        urllib.request.urlretrieve(MODEL_URL, tmp)
        os.replace(tmp, MODEL)
    return MODEL
_SESSION = None


def _session():
    global _SESSION
    if _SESSION is None:
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 2
        _SESSION = ort.InferenceSession(MODEL, opts, providers=["CPUExecutionProvider"])
    return _SESSION


def _grids():
    rows = []
    for stride in (8, 16, 32):
        n = 640 // stride
        ys, xs = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
        rows.append(np.stack([xs.ravel(), ys.ravel(), np.full(n * n, stride)], axis=1))
    return np.concatenate(rows).astype(np.float32)


_GRID = None


def detect_people(frame, conf=0.35):
    """Person boxes (x, y, w, h, score) in frame pixels."""
    import cv2
    global _GRID
    if _GRID is None:
        _GRID = _grids()
    h, w = frame.shape[:2]
    r = min(640 / w, 640 / h)
    img = np.full((640, 640, 3), 114, dtype=np.uint8)
    img[:round(h * r), :round(w * r)] = cv2.resize(frame, (round(w * r), round(h * r)))
    blob = img.transpose(2, 0, 1)[None].astype(np.float32)
    out = _session().run(None, {"images": blob})[0][0]
    xy = (out[:, :2] + _GRID[:, :2]) * _GRID[:, 2:3]
    wh = np.exp(out[:, 2:4]) * _GRID[:, 2:3]
    score = out[:, 4] * out[:, 5]                          # objectness * P(person)
    keep = score > conf
    if not keep.any():
        return []
    xy, wh, score = xy[keep] / r, wh[keep] / r, score[keep]
    boxes = [[float(x - bw / 2), float(y - bh / 2), float(bw), float(bh)] for (x, y), (bw, bh) in zip(xy, wh)]
    idx = cv2.dnn.NMSBoxes(boxes, score.tolist(), conf, 0.45)
    return [(*boxes[i], float(score[i])) for i in np.array(idx).ravel()]


def pick_player(people, frame_w, frame_h, prev_x=None):
    """The player: a large person in the lower-middle of the screen, close to the previous pick."""
    best, best_cost = None, None
    for x, y, w, h, s in people:
        if h < frame_h * 0.12:                             # far-away pedestrians
            continue
        cx, cy = (x + w / 2) / frame_w, (y + h / 2) / frame_h
        if cx < 0.12 or cx > 0.88:                         # edge people are rarely the player
            continue
        cost = abs(cx - 0.45) * 1.2 + abs(cy - 0.6) * 0.6 - (h / frame_h) * 1.5
        if prev_x is not None:
            cost += abs(cx - prev_x) * 1.5
        if best_cost is None or cost < best_cost:
            best, best_cost = cx, cost
    return best


def smooth_path(times, xs, default=0.5, max_speed=0.12):
    """Fill gaps (no player found) by holding the last position, then median + speed-limited easing."""
    filled, last = [], None
    for x in xs:
        if x is None:
            x = last
        filled.append(x)
        if x is not None:
            last = x
    first = next((x for x in filled if x is not None), default)
    filled = [first if x is None else x for x in filled]
    # 3-point median kills one-frame jumps to another person
    med = [float(np.median(filled[max(0, i - 1):i + 2])) for i in range(len(filled))]
    out = [med[0]]
    for i in range(1, len(med)):
        dt = max(1e-3, times[i] - times[i - 1])
        step = max(-max_speed * dt, min(max_speed * dt, med[i] - out[-1]))
        out.append(out[-1] + step)
    return out


def track_player(video_path, start, length, fps=1.0):
    """Keyframes [(t_from_clip_start, x_centre_fraction)], or None if tracking is unavailable."""
    try:
        ensure_model()
        import cv2
        _session()
    except Exception:
        return None
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    fw, fh = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if fw <= 0 or fh <= 0 or fw / fh < 1.2:                 # portrait sources: nothing to pan
        cap.release()
        return None
    times, xs, prev = [], [], None
    try:
        src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        every = max(1, round(src_fps / fps))
        cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)        # one seek, then read straight through (seeking .ts is slow)
        total = int(length * src_fps)
        for i in range(total + 1):
            if i % every:
                if not cap.grab():
                    break
                continue
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            x = pick_player(detect_people(frame), fw, fh, prev)
            if x is not None:
                prev = x
            times.append(i / src_fps)
            xs.append(x)
    finally:
        cap.release()
    if sum(x is not None for x in xs) < max(2, len(xs) // 5):
        return None                                        # no clear player (driving, cutscene): keep the static crop
    return list(zip(times, smooth_path(times, xs)))


def crop_x_expr(keys, out_w=1080):
    """ffmpeg expression for crop x (input already scaled to 1920 high): piecewise-linear pan through keys."""
    def at(x):
        return f"(iw*{x:.4f}-{out_w // 2})"
    expr = at(keys[-1][1])
    for (t0, x0), (t1, x1) in reversed(list(zip(keys, keys[1:]))):
        if t1 <= t0:
            continue
        seg = f"({at(x0)}+({at(x1)}-{at(x0)})*(t-{t0:.2f})/{t1 - t0:.2f})"
        expr = f"if(lt(t\\,{t1:.2f})\\,{seg}\\,{expr})"
    return f"max(0\\,min(iw-{out_w}\\,{expr}))"
