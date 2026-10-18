#!/usr/bin/env python3
"""Is the sim camera where the real camera is? Overlay a sim frame on a real frame and score it.

Take both frames with the arm in the SAME pose (e.g. the sim reset pose, commanded on the real arm)
and nothing else moved. Output: a blend, an edge overlay (sim edges magenta, real edges green,
agreement white), and the edge F1 with a 4 px tolerance.
Iterate S2T_CAM_POS / S2T_CAM_LOOK_AT (configs/station.yaml) until the arm base, table edge and pad
line up; record the final F1 in reports/ as evidence.

    python scripts/overlay_check.py --sim logs/view/front.png --real station_front.jpg --out reports/overlay.png
(the starter's scripts/view_env.py dumps sim camera frames to logs/view/)
"""

import argparse
from pathlib import Path

import cv2
import numpy as np

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--sim", required=True)
ap.add_argument("--real", required=True)
ap.add_argument("--out", required=True, type=Path)
ap.add_argument("--tol", type=int, default=4)
a = ap.parse_args()

real = cv2.imread(a.real)
sim = cv2.imread(a.sim)
if real is None or sim is None:
    raise SystemExit("could not read one of the images")
sim = cv2.resize(sim, (real.shape[1], real.shape[0]))


def edges(img):
    return cv2.Canny(cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (5, 5), 0), 50, 150) > 0


es, er = edges(sim), edges(real)
k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * a.tol + 1, 2 * a.tol + 1))
ds, dr = cv2.dilate(es.astype(np.uint8), k) > 0, cv2.dilate(er.astype(np.uint8), k) > 0
prec = (es & dr).sum() / max(es.sum(), 1)
rec = (er & ds).sum() / max(er.sum(), 1)
f1 = 2 * prec * rec / max(prec + rec, 1e-9)

vis = np.zeros_like(real)
vis[es] = (255, 0, 255)
vis[er] = (0, 255, 0)
vis[es & dr] = (255, 255, 255)
blend = cv2.addWeighted(real, 0.5, sim, 0.5, 0)
a.out.parent.mkdir(parents=True, exist_ok=True)
cv2.imwrite(str(a.out), np.hstack([blend, vis]))
print(f"edge F1 (tol {a.tol}px): {f1:.3f}   precision {prec:.3f}  recall {rec:.3f}  -> {a.out}")
