"""OpenCV-based symbol counter for cross-checking the vision model.

Reads an electrical SLD image and reports counts of:
- circular blobs (likely generators / motors / TX windings)
- rectangular blobs (likely VFD / breaker / title block boxes)
- approximate horizontal and vertical line counts (busbars / cables)

These counts are NOT a substitute for the vision pass - they are a
sanity check.  If Claude says "4 generators" and OpenCV finds only 3
circles in the upper half of the image, you know to look again.

Output is JSON on stdout so the skill can parse it programmatically:

    python cv_count.py source.png

Returns non-zero on read failure.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import cv2
    import numpy as np
    HAS_CV = True
except ImportError:
    HAS_CV = False


def count_symbols(img_path: Path) -> dict:
    if not HAS_CV:
        return {"error": "opencv-python-headless not installed"}

    img = cv2.imread(str(img_path))
    if img is None:
        return {"error": f"could not read image: {img_path}"}

    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # ----- Circles (HoughCircles) ----------------------------------------
    # Tuned for typical SLD circle sizes (G/M symbols ~ 30-60 px radius
    # on a 2000x1500 image; transformer winding circles ~ 15-30 px).
    circles = cv2.HoughCircles(
        blurred, cv2.HOUGH_GRADIENT,
        dp=1.0, minDist=int(min(w, h) * 0.02),
        param1=80, param2=28,
        minRadius=int(min(w, h) * 0.008),
        maxRadius=int(min(w, h) * 0.05),
    )
    n_circles = 0 if circles is None else int(circles.shape[1])

    # ----- Rectangles (contour quad approximation) -----------------------
    edges = cv2.Canny(blurred, 50, 150)
    contours, _ = cv2.findContours(
        edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE,
    )
    n_rects = 0
    min_area = max(200, w * h * 0.0005)
    max_area = w * h * 0.2
    for c in contours:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        area = cv2.contourArea(c)
        if len(approx) == 4 and min_area < area < max_area:
            x, y, rw, rh = cv2.boundingRect(approx)
            aspect = rw / rh if rh > 0 else 0
            if 0.2 < aspect < 5.0:
                n_rects += 1

    # ----- Long lines via probabilistic Hough ----------------------------
    lines = cv2.HoughLinesP(
        edges, rho=1, theta=np.pi / 180, threshold=80,
        minLineLength=int(w * 0.15), maxLineGap=15,
    )
    n_horiz = 0
    n_vert = 0
    if lines is not None:
        for x1, y1, x2, y2 in lines[:, 0]:
            dx, dy = abs(x2 - x1), abs(y2 - y1)
            if dy < 5 and dx > 50:
                n_horiz += 1
            elif dx < 5 and dy > 50:
                n_vert += 1

    return {
        "image_size_px": [w, h],
        "circles": n_circles,
        "rectangles": n_rects,
        "long_horizontal_lines": n_horiz,
        "long_vertical_lines":   n_vert,
        "_doc": (
            "circles ~= total rotating-machine + TX-winding symbols; "
            "rectangles ~= VFD/breaker/title-block boxes; "
            "horizontal_lines ~= busbar segments; "
            "vertical_lines ~= feeder cable runs."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    result = count_symbols(args.input)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    raise SystemExit(main())
