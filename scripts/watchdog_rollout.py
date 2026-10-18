#!/usr/bin/env python3
"""Ensemble at deployment: ACT checkpoints act, Cosmos Reason judges, retry inside the 2-minute cap.

One judged trial = 120 s. A single ACT attempt takes ~15-30 s. If an attempt fails (missed grasp,
cube knocked off the spot), the remaining time is usually enough for another attempt. This script:

  1. runs checkpoint k for one attempt (scripts/rollout.sh with a short --duration; LeRobot returns
     the arm to its initial pose at the end),
  2. grabs one frame from the station camera and asks Cosmos Reason whether the cube is released
     and resting on the green pad,
  3. stops on "yes", otherwise moves to the next checkpoint in the list and tries again,
     until the 120 s budget is used.

Different checkpoints (main seeds, or main + temporal-ensembling variant) fail differently, so
rotating through them is a cheap ensemble. Every decision is logged to data/eval/watchdog.jsonl.
CHECK WITH ORGANIZERS before using this for judged trials (docs/roadmap/open-questions.md).

    python scripts/watchdog_rollout.py --ckpts outputs/act_main/.../pretrained_model outputs/act_main_s2/.../pretrained_model \
        --reason-url http://<nebius-vm>:8000/v1 --attempt-seconds 40
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import time
from pathlib import Path

import cv2
import yaml

REPO = Path(__file__).resolve().parents[1]
ASK = ("Look at the table. Is the small cube released by the gripper and resting on top of the flat green pad? "
       'Answer only with JSON: {"cube_on_pad": true/false, "cube_visible": true/false}')


def grab_frame(index) -> bytes:
    cap = cv2.VideoCapture(index)
    for _ in range(5):  # let auto-exposure settle
        ok, f = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError("camera read failed")
    return cv2.imencode(".jpg", f)[1].tobytes()


def ask_reason(client, model, jpg: bytes) -> dict:
    url = "data:image/jpeg;base64," + base64.b64encode(jpg).decode()
    r = client.chat.completions.create(
        model=model, max_tokens=200, temperature=0.0,
        messages=[{"role": "user", "content": [{"type": "image_url", "image_url": {"url": url}},
                                               {"type": "text", "text": ASK}]}])
    m = re.search(r"\{.*\}", r.choices[0].message.content, re.S)
    return json.loads(m.group(0)) if m else {"cube_on_pad": False, "parse_error": r.choices[0].message.content}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ckpts", nargs="+", required=True, help="tried in order, cycling")
    ap.add_argument("--reason-url", required=True)
    ap.add_argument("--budget", type=float, default=115, help="seconds; 5 s margin under the 120 s cap")
    ap.add_argument("--attempt-seconds", type=float, default=40)
    ap.add_argument("--spot", default="")
    a = ap.parse_args()

    from openai import OpenAI

    client = OpenAI(api_key="EMPTY", base_url=a.reason_url)
    model = client.models.list().data[0].id
    cam_index = yaml.safe_load((REPO / "configs/station.yaml").read_text())["camera"]["index_or_path"]
    log = REPO / "data/eval/watchdog.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    t0, k, verdict = time.time(), 0, {}
    while True:
        left = a.budget - (time.time() - t0)
        if left < 15:  # not enough time for a meaningful attempt
            break
        ck = a.ckpts[k % len(a.ckpts)]
        dur = min(a.attempt_seconds, left - 5)
        subprocess.run([str(REPO / "scripts/rollout.sh")], env=dict(os.environ, CKPT=ck, DURATION=str(int(dur))), check=False)
        verdict = ask_reason(client, model, grab_frame(cam_index))
        rec = {"t": round(time.time() - t0, 1), "attempt": k + 1, "ckpt": ck, "spot": a.spot, "verdict": verdict}
        print(rec, flush=True)
        with open(log, "a") as f:
            f.write(json.dumps(rec) + "\n")
        if verdict.get("cube_on_pad"):
            break
        k += 1
    print("DONE", "success (per Reason)" if verdict.get("cube_on_pad") else "no success", f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
