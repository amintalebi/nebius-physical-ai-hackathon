#!/usr/bin/env python3
"""Collect scripted sim demos spread evenly over the 9 real grid spots, across the event cube sizes.

Runs the starter's ./collect.sh once per spot (and per cube size) with the s2t_station.patch env vars
set, appending to one dataset (--resume). Equal episodes per (spot, size) = the training data covers the
judges' test set and the 30|40 mm event cube sizes.

    python scripts/collect_grid.py --starter ~/work/so101_sim_pickplace --per-spot 12 \
        --dataset-name sim_A
    python scripts/collect_grid.py --starter ... --per-spot 4 --sizes 40 --dataset-name sim_A_40   # one size

Cube sizes default to `geometry.cube_sizes_mm` in configs/station.yaml (fallback: a single
`cube_size_m`). Both sizes (30/40) ship as USD twins in the starter, so no grasp patch is needed.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import zlib
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from s2t.sampling import split_per_size  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--starter", required=True, type=Path, help="checkout of so101-sim-pickplace-gr00t with the patch applied")
ap.add_argument("--station", default=Path(__file__).resolve().parents[1] / "configs/station.yaml", type=Path)
ap.add_argument("--per-spot", type=int, required=True,
                help="episodes per spot in TOTAL, split evenly over --sizes (s2t/sampling.py)")
ap.add_argument("--dataset-name", required=True)
ap.add_argument("--jitter", type=float, default=0.012, help="+- metres around each spot (tape is not exact)")
ap.add_argument("--spots", nargs="*", help="subset of spot names, default all")
ap.add_argument("--sizes", nargs="*", type=int,
                help="cube sizes in mm to collect (default: geometry.cube_sizes_mm from station.yaml)")
ap.add_argument("--resume", action="store_true", help="dataset already exists (e.g. rerunning failed spots)")
ap.add_argument("--dry-run", action="store_true")
args = ap.parse_args()

st = yaml.safe_load(args.station.read_text())
g = st["geometry"]
spots = g["grid_spots_xy"]
names = args.spots or list(spots)
sizes = args.sizes or [int(s) for s in g.get("cube_sizes_mm", [round(g["cube_size_m"] * 1000)])]
patched = (args.starter / "so101_pickplace/pickplace_env_cfg.py").read_text()
if "S2T_CUBE_XY" not in patched:
    sys.exit("starter is not patched: git apply sim_patches/s2t_station.patch inside the starter checkout")
if "base_mdp.image," in patched:
    sys.exit("starter uses mdp.image, removed in Isaac Lab release/3.0.0: "
             "git apply sim_patches/isaaclab_release30_compat.patch inside the starter checkout")

plan = {name: dict(zip(sizes, split_per_size(args.per_spot, len(sizes), list(spots).index(name)))) for name in names}
print(f"[collect_grid] {args.per_spot}/spot over sizes {sizes} mm: "
      f"{ {s: sum(plan[n][s] for n in names) for s in sizes} } episodes per size, {args.per_spot * len(names)} total", flush=True)
first_collect = True
for size in sizes:
    for name in names:
        x, y = spots[name]
        n_eps = plan[name][size]
        if n_eps == 0:
            continue
        env = dict(os.environ)
        env.update(
            S2T_CUBE_XY=f"{x},{y}",
            S2T_PAD_XY="{},{}".format(*g["pad_center_xy"]),
            S2T_JITTER=str(args.jitter),
            S2T_CAM_POS=",".join(map(str, g["front_cam_pos"])),
            S2T_CAM_LOOK_AT=",".join(map(str, g["front_cam_look_at"])),
            CUBE_SIZE_MM=str(size),
            CUBE_COLOR=g["cube_color"],
            DATASET_NAME=args.dataset_name,
            NUM_EPISODES=str(n_eps),
            TASK=st["task"],
        )
        # collect.sh refuses a non-empty dataset dir without --resume; only the very first collect omits it.
        # Distinct seed per (dataset, size, spot, resume pass): the starter defaults to --seed 0, which makes every
        # spot replay the same yaw sequence and set B duplicate set A episode for episode.
        seed = zlib.crc32(f"{args.dataset_name}/{size}/{name}/{int(args.resume)}".encode()) % 2**31
        cmd = ["./collect.sh"] + ([] if first_collect and not args.resume else ["--resume"]) + ["--seed", str(seed)]
        print(f"[collect_grid] size {size:>2}mm spot {name} at ({x:+.3f},{y:+.3f}) x{n_eps}: {' '.join(cmd)}", flush=True)
        if not args.dry_run:
            r = subprocess.run(cmd, cwd=args.starter, env=env)
            if r.returncode != 0:
                rest = " ".join(names[names.index(name):])
                sys.exit(f"collect failed on size {size}mm spot {name}: rerun this size with --resume --sizes {size} "
                         f"--spots {rest}, then the remaining sizes {sizes[sizes.index(size) + 1:]} on all spots")
        first_collect = False
