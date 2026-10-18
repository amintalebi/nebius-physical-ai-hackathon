#!/usr/bin/env python3
"""Make a starter sim dataset (LeRobot v2.1) mergeable with real station recordings.

Three mismatches fixed, all found in the sources (see docs/sources.md):
  1. Joint units: sim writes USD-limit-normalised values; the real arm reports calibrated degrees.
     -> rewrite observation.state and action with s2t.units.sim_norm_to_real().
  2. Cameras: sim records `front` + `wrist`; the station has one mounted camera.
     -> keep only --keep-camera (renamed to the station camera key), delete the others.
  3. Per-episode stats are recomputed for the rewritten columns so merged stats are right.

Output is still v2.1. Then convert to v3.0 in place with LeRobot's own converter before merging
(lerobot @146d847, src/lerobot/scripts/convert_dataset_v21_to_v30.py docstring):
    python -m lerobot.scripts.convert_dataset_v21_to_v30 --repo-id=local/sim_A \
        --root=data/sim/A_real_units --push-to-hub=false

    python scripts/convert_sim_dataset.py --src data/sim/A --dst data/sim/A_real_units
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from s2t.units import JOINTS, load_calibration, sim_norm_to_real  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--src", required=True, type=Path)
ap.add_argument("--dst", required=True, type=Path)
ap.add_argument("--station", default=Path(__file__).resolve().parents[1] / "configs/station.yaml", type=Path)
ap.add_argument("--keep-camera", default="front", help="sim camera to keep")
ap.add_argument("--overwrite", action="store_true")
args = ap.parse_args()

st = yaml.safe_load(args.station.read_text())
repo = Path(__file__).resolve().parents[1]
cal = load_calibration(repo / st["robot"]["calibration_file"])
mode = "degrees" if st["robot"]["use_degrees"] else "range"
signs = st["joint_map"]["signs"]
offs = st["joint_map"]["offsets_deg"]
cam_out = st["camera"]["key"]

info = json.loads((args.src / "meta/info.json").read_text())
if info["codebase_version"] != "v2.1":
    sys.exit(f"expected a v2.1 starter dataset, got {info['codebase_version']}")
names = info["features"]["action"]["names"]
if [n.removesuffix(".pos") for n in names] != JOINTS:
    sys.exit(f"unexpected joint order {names}")
if info.get("s2t_units"):
    sys.exit("source already converted (meta/info.json has s2t_units); refusing to convert twice")

if args.dst.exists():
    if not args.overwrite:
        sys.exit(f"{args.dst} exists (use --overwrite)")
    shutil.rmtree(args.dst)
shutil.copytree(args.src / "meta", args.dst / "meta")
# GR00T's modality.json still lists the wrist camera and sim units; it does not apply after conversion.
(args.dst / "meta/modality.json").unlink(missing_ok=True)

# videos: keep one camera, rename its key
vid_keys = [k for k, f in info["features"].items() if f["dtype"] == "video"]
keep_in = f"observation.images.{args.keep_camera}"
keep_out = f"observation.images.{cam_out}"
if keep_in not in vid_keys:
    sys.exit(f"{keep_in} not in {vid_keys}")
for chunk in sorted((args.src / "videos").glob("chunk-*")):
    shutil.copytree(chunk / keep_in, args.dst / "videos" / chunk.name / keep_out)


def vec_stats(x: np.ndarray) -> dict:
    return {"min": x.min(0).tolist(), "max": x.max(0).tolist(), "mean": x.mean(0).tolist(),
            "std": x.std(0).tolist(), "count": [int(x.shape[0])]}


ep_stats = {}
for line in (args.src / "meta/episodes_stats.jsonl").read_text().splitlines():
    if line.strip():
        e = json.loads(line)
        ep_stats[e["episode_index"]] = e

n_files = 0
for pf in sorted((args.src / "data").rglob("*.parquet")):
    t = pq.read_table(pf)
    cols = {}
    for col in ("action", "observation.state"):
        v = np.stack(t[col].to_numpy(zero_copy_only=False)).astype(np.float64)
        cols[col] = sim_norm_to_real(v, cal, mode, signs, offs)
    for col, arr in cols.items():
        t = t.set_column(t.schema.get_field_index(col), col, pa.array(arr.tolist(), type=pa.list_(pa.float32())))
    out = args.dst / pf.relative_to(args.src)
    out.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(t, out)
    ep = int(t["episode_index"][0].as_py())
    s = ep_stats[ep]["stats"]
    for col, arr in cols.items():
        s[col] = vec_stats(arr)
    if keep_in in s:
        s[keep_out] = s.pop(keep_in)
    for k in vid_keys:
        if k != keep_out:
            s.pop(k, None)
    n_files += 1

with open(args.dst / "meta/episodes_stats.jsonl", "w") as f:
    for ep in sorted(ep_stats):
        f.write(json.dumps(ep_stats[ep]) + "\n")

feat = info["features"]
vid_feat = feat[keep_in]
for k in vid_keys:
    feat.pop(k)
feat[keep_out] = vid_feat
info["total_videos"] = info["total_episodes"]
info["s2t_units"] = {"mode": mode, "calibration": st["robot"]["calibration_file"], "signs": signs, "offsets_deg": offs}
(args.dst / "meta/info.json").write_text(json.dumps(info, indent=4))
print(f"converted {n_files} episodes -> {args.dst} (units={mode}, camera {keep_in} -> {keep_out})")
