#!/usr/bin/env python3
"""Measure what Cosmos Transfer did, instead of eyeballing it.

Two numbers per episode, both needed for the Cosmos rubric claim "structure-preserving, toward the
real look":

  edge_f1    structure kept? Canny edges of the sim frame vs the Cosmos frame, F1 with a 2 px
             tolerance. Low = geometry moved = recorded actions no longer match the pixels.
  look_gap   closer to the real station? Distance from the frame to the mean of real station frames,
             for sim and for Cosmos. look_gap_cosmos < look_gap_sim is the claim.
             Uses DINOv2 (transformers) if installed, else a Lab colour-histogram distance.

    python scripts/cosmos_metrics.py --sim data/sim/B_real_units --cosmos data/cosmos/B_transfer \
        --real data/real/station_v21_or_frames_dir --out reports/cosmos_metrics.json
`--real` can be a folder of .jpg/.png station frames or any folder containing .mp4 files.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--sim", type=Path, required=True)
ap.add_argument("--cosmos", type=Path, required=True)
ap.add_argument("--real", type=Path, required=True)
ap.add_argument("--camera", default="front")
ap.add_argument("--stride", type=int, default=15, help="evaluate every Nth frame")
ap.add_argument("--edge-min", type=float, default=0.5, help="flag episodes below this edge F1")
ap.add_argument("--out", type=Path, required=True)
args = ap.parse_args()


def frames(path: Path, stride: int) -> list[np.ndarray]:
    cap, out, i = cv2.VideoCapture(str(path)), [], 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if i % stride == 0:
            out.append(f)
        i += 1
    cap.release()
    return out


def edges(f: np.ndarray) -> np.ndarray:
    g = cv2.GaussianBlur(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    return cv2.Canny(g, 50, 150) > 0


def edge_f1(a: np.ndarray, b: np.ndarray, tol: int = 2) -> float:
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * tol + 1, 2 * tol + 1))
    ea, eb = edges(a), edges(b)
    da, db = cv2.dilate(ea.astype(np.uint8), k) > 0, cv2.dilate(eb.astype(np.uint8), k) > 0
    prec = (eb & da).sum() / max(eb.sum(), 1)
    rec = (ea & db).sum() / max(ea.sum(), 1)
    return float(2 * prec * rec / max(prec + rec, 1e-9))


class Embedder:
    def __init__(self):
        try:
            import torch
            from transformers import AutoImageProcessor, AutoModel

            self.torch = torch
            self.proc = AutoImageProcessor.from_pretrained("facebook/dinov2-small")
            self.model = AutoModel.from_pretrained("facebook/dinov2-small").eval()
            self.kind = "dinov2-small"
        except Exception:  # no torch/transformers on this box: fall back, and say so in the report
            self.kind = "lab-histogram"

    def __call__(self, f: np.ndarray) -> np.ndarray:
        if self.kind == "lab-histogram":
            lab = cv2.cvtColor(cv2.resize(f, (160, 120)), cv2.COLOR_BGR2LAB)
            h = cv2.calcHist([lab], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256]).ravel()
            return h / max(h.sum(), 1)
        with self.torch.no_grad():
            x = self.proc(images=cv2.cvtColor(f, cv2.COLOR_BGR2RGB), return_tensors="pt")
            e = self.model(**x).pooler_output[0].numpy()
        return e / np.linalg.norm(e)


def real_frames(root: Path) -> list[np.ndarray]:
    imgs = [cv2.imread(str(p)) for p in sorted(root.rglob("*")) if p.suffix.lower() in (".jpg", ".jpeg", ".png")]
    if imgs:
        return imgs
    out = []
    for v in sorted(root.rglob("*.mp4"))[:50]:
        out += frames(v, 30)
    return out


emb = Embedder()
real = real_frames(args.real)
if not real:
    raise SystemExit(f"no real frames found under {args.real}")
centroid = np.mean([emb(f) for f in real], axis=0)


def gap(f):
    e = emb(f)
    return float(np.linalg.norm(e - centroid))


pat = f"videos/chunk-*/observation.images.{args.camera}/episode_*.mp4"
sim_v = {p.name: p for p in args.sim.glob(pat)}
cos_v = {p.name: p for p in args.cosmos.glob(pat)}
rows = []
for name in sorted(set(sim_v) & set(cos_v)):
    fs, fc = frames(sim_v[name], args.stride), frames(cos_v[name], args.stride)
    n = min(len(fs), len(fc))
    if n == 0:
        continue
    rows.append({
        "episode": name,
        "edge_f1": float(np.mean([edge_f1(fs[i], fc[i]) for i in range(n)])),
        "look_gap_sim": float(np.mean([gap(fs[i]) for i in range(n)])),
        "look_gap_cosmos": float(np.mean([gap(fc[i]) for i in range(n)])),
    })

summary = {
    "embedder": emb.kind,
    "n_episodes": len(rows),
    "n_real_frames": len(real),
    "edge_f1_mean": float(np.mean([r["edge_f1"] for r in rows])) if rows else None,
    "look_gap_sim_mean": float(np.mean([r["look_gap_sim"] for r in rows])) if rows else None,
    "look_gap_cosmos_mean": float(np.mean([r["look_gap_cosmos"] for r in rows])) if rows else None,
    "episodes_closer_to_real": sum(r["look_gap_cosmos"] < r["look_gap_sim"] for r in rows),
    "flag_low_edge_f1": [r["episode"] for r in rows if r["edge_f1"] < args.edge_min],
}
args.out.parent.mkdir(parents=True, exist_ok=True)
args.out.write_text(json.dumps({"summary": summary, "episodes": rows}, indent=2))
print(json.dumps(summary, indent=2))
