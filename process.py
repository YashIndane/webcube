import cv2
import numpy as np
from dataclasses import dataclass
from typing import Optional, List, Tuple

grid_size: int = 3


def read_faces():
    for i in range(6):
        image = cv2.imread(f"face{i}.png")
        h, w = image.shape[:2]
        cell_h = h // grid_size
        cell_w = w // grid_size

        yield(
            [image, cell_h, cell_w]
        )

@dataclass
class ColorDef:
    name: str
    bgr: tuple          # for visualization
    hsv_ranges: list    # list of ((hlo,slo,vlo),(hhi,shi,vhi)) pairs


CUBE_COLORS: List[ColorDef] = [
    ColorDef("White",  (255, 255, 255), [
        ((0, 0, 170), (180, 80, 255)),
    ]),
    ColorDef("Yellow", (0, 230, 230), [
        ((18,  80, 130), (38,  255, 255)),
    ]),
    ColorDef("Orange", (0, 120, 255), [
        ((6,   130, 130), (18,  255, 255)),
    ]),
    ColorDef("Red",    (0,   0, 210), [
        ((0,   130, 100), (6,   255, 255)),   # low-hue red
        ((170, 130, 100), (180, 255, 255)),   # high-hue red (wrap)
    ]),
    ColorDef("Blue",   (210, 80, 0), [
        ((100, 100,  80), (125, 255, 255)),
    ]),
    ColorDef("Green",  (0, 160,  30), [
        ((38,  60,  40), (95,  255, 255)),
    ]),
]

def classify_color_hsv(roi_bgr: np.ndarray) -> Tuple[str, float]:
    """
    Classify a BGR image patch into one of the 6 Rubik's colors.

    Strategy:
      1. Convert to HSV.
      2. For each ColorDef, count pixels that fall within its HSV range(s).
      3. Apply a confidence boost for saturation/value consistency.
      4. Return the best match and its confidence (0–1).
    """
    # Slight blur to reduce noise
    roi = cv2.GaussianBlur(roi_bgr, (5, 5), 0)
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    total_pixels = hsv.shape[0] * hsv.shape[1]

    scores = {}
    for cdef in CUBE_COLORS:
        mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
        for (lo, hi) in cdef.hsv_ranges:
            lo_arr = np.array(lo, dtype=np.uint8)
            hi_arr = np.array(hi, dtype=np.uint8)
            mask |= cv2.inRange(hsv, lo_arr, hi_arr)
        scores[cdef.name] = np.count_nonzero(mask) / total_pixels

    best_name = max(scores, key=scores.get)
    confidence = scores[best_name]
    return best_name, confidence


def classify_color_lab_fallback(roi_bgr: np.ndarray) -> str:
    """
    Fallback: compute the mean L*a*b* color of the ROI and return
    the nearest Rubik's color by Euclidean distance in Lab space.
    Used when HSV confidence is low (e.g. under mixed lighting).
    """
    # Reference Lab values for each color (computed from sRGB)
    REFERENCE_LAB = {
        "White":  (97.0,   0.0,   0.0),
        "Yellow": (87.0,  -8.0,  82.0),
        "Orange": (60.0,  40.0,  60.0),
        "Red":    (42.0,  60.0,  40.0),
        "Blue":   (35.0,  15.0, -55.0),
        "Green":  (45.0, -45.0,  35.0),
    }

    lab = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2Lab).astype(np.float32)
    mean_lab = lab.mean(axis=(0, 1))  # (L, a, b)

    best, best_dist = None, float("inf")
    for name, ref in REFERENCE_LAB.items():
        dist = np.linalg.norm(mean_lab - np.array(ref))
        if dist < best_dist:
            best_dist = dist
            best = name
    return best


def detect_tile_color(
    roi_bgr: np.ndarray,
    center_crop: float = 0.6,
) -> dict:
    """
    Detect the color of a single tile.

    Parameters
    ----------
    roi_bgr     : BGR crop of the tile (any size, will be resized internally)
    center_crop : fraction of tile area to sample from center (avoids edge shadows)

    Returns
    -------
    dict with keys:
        "color"      : str  – detected color name
        "confidence" : float – 0–1 score from primary HSV method
        "method"     : str  – "hsv" or "lab_fallback"
    """
    CONFIDENCE_THRESHOLD = 0.35   # min HSV coverage to trust the result

    if roi_bgr is None or roi_bgr.size == 0:
        return {"color": "Unknown", "confidence": 0.0, "method": "none"}

    # Resize for consistent processing
    tile = cv2.resize(roi_bgr, (64, 64))

    # Center crop to avoid plastic border / shadows
    if 0 < center_crop < 1.0:
        margin = int((1 - center_crop) / 2 * 64)
        tile = tile[margin:64-margin, margin:64-margin]

    color_hsv, confidence = classify_color_hsv(tile)

    if confidence >= CONFIDENCE_THRESHOLD:
        return {"color": color_hsv, "confidence": round(confidence, 3), "method": "hsv"}
    else:
        color_lab = classify_color_lab_fallback(tile)
        return {"color": color_lab, "confidence": round(confidence, 3), "method": "lab_fallback"}

def getcols() -> List:
  faces, res = read_faces(), []
  for j in range(6):
      face, cell_h, cell_w = next(faces)

      for row in range(grid_size):
         for col in range(grid_size):
            y0, y1 = row * cell_h, (row + 1) * cell_h
            x0, x1 = col * cell_w, (col + 1) * cell_w
            roi = face[y0:y1, x0:x1]
            result = detect_tile_color(roi)
            res.append(result)
  print(f"RESPONSE: {res}", '\n', sep='\n')
  return res


