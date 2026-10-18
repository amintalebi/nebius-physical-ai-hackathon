#!/usr/bin/env python3
"""Live camera alignment against a sim reference frame (run in Terminal.app: it needs camera access).

Shows the live 640x480 feed with the sim frame blended on top. Move the physical camera until the robot
base, the arm and the table area line up with the sim ghost. Keys: [ / ] blend less / more, s save a
snapshot to station_cams/, q quit.

    ../lerobot/.venv/bin/python scripts/camera_align.py --index 1 --ref ../sim_reference/sim_front_start.jpg
"""

import argparse
import time
from pathlib import Path

import cv2

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--index", type=int, default=1)
ap.add_argument("--ref", type=Path, required=True)
ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[2] / "station_cams")
args = ap.parse_args()

ref = cv2.resize(cv2.imread(str(args.ref)), (640, 480))
cap = cv2.VideoCapture(args.index)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
alpha = 0.5
while True:
    ok, frame = cap.read()
    if not ok:
        raise SystemExit(f"camera {args.index} gave no frame (camera permission? wrong index?)")
    h, w = frame.shape[:2]
    frame = cv2.resize(frame, (640, 480))
    view = cv2.addWeighted(frame, 1 - alpha, ref, alpha, 0)
    for x in (213, 427):
        cv2.line(view, (x, 0), (x, 479), (0, 255, 255), 1)
    for y in (160, 320):
        cv2.line(view, (0, y), (639, y), (0, 255, 255), 1)
    cv2.putText(view, f"live {w}x{h} | sim ghost {alpha:.1f} | [ ] blend  s save  q quit", (8, 470),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)
    cv2.imshow("camera align (sim ghost)", view)
    k = cv2.waitKey(30) & 0xFF
    if k == ord("q"):
        break
    if k == ord("["):
        alpha = max(0.0, alpha - 0.1)
    if k == ord("]"):
        alpha = min(1.0, alpha + 0.1)
    if k == ord("s"):
        args.out.mkdir(parents=True, exist_ok=True)
        p = args.out / f"align_{args.index}_{time.strftime('%H%M%S')}.png"
        cv2.imwrite(str(p), frame)
        print("saved", p)
cap.release()
cv2.destroyAllWindows()
