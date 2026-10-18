#!/usr/bin/env python3
"""Collect scripted sim demos spread evenly over the 9 real grid spots.

Runs the starter's ./collect.sh once per spot with the s2t_station.patch env vars set, appending to
one dataset (--resume). Equal episodes per spot = the training data covers the judges' test set.

    python scripts/collect_grid.py --starter ~/work/so101_sim_pickplace --per-spot 12 \
        --dataset-name sim_A
Run on the Isaac Sim VM (L40S / RTX PRO 6000; not H100, Isaac Sim needs RT cores).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import yaml

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--starter", required=True, type=Path, help="checkout of so101-sim-pickplace-gr00t with the patch applied")
ap.add_argument("--station", default=Path(__file__).resolve().parents[1] / "configs/station.yaml", type=Path)
ap.add_argument("--per-spot", type=int, required=True)
ap.add_argument("--dataset-name", required=True)
ap.add_argument("--jitter", type=float, default=0.012, help="+- metres around each spot (tape is not exact)")
ap.add_argument("--spots", nargs="*", help="subset of spot names, default all")
ap.add_argument("--resume", action="store_true", help="dataset already exists (e.g. rerunning failed spots)")
ap.add_argument("--dry-run", action="store_true")
args = ap.parse_args()

st = yaml.safe_load(args.station.read_text())
g = st["geometry"]
spots = g["grid_spots_xy"]
names = args.spots or list(spots)
patched = (args.starter / "so101_pickplace/pickplace_env_cfg.py").read_text()
if "S2T_CUBE_XY" not in patched:
    sys.exit("starter is not patched: git apply sim_patches/s2t_station.patch inside the starter checkout")
if "base_mdp.image," in patched:
    sys.exit("starter uses mdp.image, removed in Isaac Lab release/3.0.0: "
             "git apply sim_patches/isaaclab_release30_compat.patch inside the starter checkout")

first = True
for name in names:
    x, y = spots[name]
    env = dict(os.environ)
    env.update(
        S2T_CUBE_XY=f"{x},{y}",
        S2T_PAD_XY="{},{}".format(*g["pad_center_xy"]),
        S2T_JITTER=str(args.jitter),
        S2T_CAM_POS=",".join(map(str, g["front_cam_pos"])),
        S2T_CAM_LOOK_AT=",".join(map(str, g["front_cam_look_at"])),
        CUBE_SIZE_MM=str(round(g["cube_size_m"] * 1000)),
        CUBE_COLOR=g["cube_color"],
        DATASET_NAME=args.dataset_name,
        NUM_EPISODES=str(args.per_spot),
        TASK=st["task"],
    )
    # collect.sh refuses a non-empty dataset dir without --resume; only a fresh first spot omits it.
    cmd = ["./collect.sh"] + ([] if first and not args.resume else ["--resume"])
    print(f"[collect_grid] spot {name} at ({x:+.3f},{y:+.3f}) x{args.per_spot}: {' '.join(cmd)}", flush=True)
    if not args.dry_run:
        r = subprocess.run(cmd, cwd=args.starter, env=env)
        if r.returncode != 0:
            rest = " ".join(names[names.index(name):])
            sys.exit(f"collect failed on spot {name}; rerun with --resume --spots {rest}")
    first = False
