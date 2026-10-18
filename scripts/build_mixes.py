#!/usr/bin/env python3
"""Apply curation + size limits to each source, keep Cosmos/raw twins identical, merge the mixes.

Reads configs/data_mix.yaml and data/curation/decisions.json. Prints the LeRobot commands; runs them
with --execute. Flags from lerobot @146d847 scripts/lerobot_edit_dataset.py (delete_episodes with
--root/--new_root; merge with --operation.roots).

Order matters: curation drop lists use each source's own episode indices, so drops are applied per
source BEFORE merging (merge renumbers episodes).

    python scripts/build_mixes.py              # dry run: show the plan and commands
    python scripts/build_mixes.py --execute
    python scripts/validate_manifest.py        # then check the result
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]


def total_episodes(p: Path) -> int:
    return int(json.loads((p / "meta/info.json").read_text())["total_episodes"])


def even_subset(kept: list[int], k: int) -> list[int]:
    """k indices spread evenly over `kept` (collection is spot by spot, so this keeps spots balanced)."""
    if k >= len(kept):
        return kept
    step = len(kept) / k
    return [kept[int(i * step)] for i in range(k)]


def plan(cfg: dict, root: Path) -> tuple[dict[str, list[int]], dict[str, list[int]]]:
    """Returns (episodes to remove, episodes kept) per source, in each source's own indices."""
    cur_file = root / cfg["curation_file"]
    dec = json.loads(cur_file.read_text())["datasets"] if cur_file.exists() else {}
    if not dec:
        print("WARN no curation decisions found: nothing dropped by Cosmos Reason")
    srcs = cfg["sources"]
    drops = {}
    for name, s in srcs.items():
        d = set(dec.get(name, {}).get("drop", []))
        if s.get("extra_drops") and (root / s["extra_drops"]).exists():
            d |= set(json.loads((root / s["extra_drops"]).read_text())["drop"])
        drops[name] = d
    # twins: one drop list for both
    for name, s in srcs.items():
        if "twin" in s:
            u = drops[name] | drops[s["twin"]]
            drops[name] = drops[s["twin"]] = u
    keep = {}
    for name, s in srcs.items():
        n = total_episodes(root / s["raw"])
        kept = [i for i in range(n) if i not in drops[name]]
        if s.get("max_episodes"):
            kept = even_subset(kept, s["max_episodes"])
        keep[name] = kept
    for name, s in srcs.items():
        if "twin" in s:  # the twin keeps exactly the Cosmos episodes (same trajectories)
            keep[s["twin"]] = keep[name]
    return {name: sorted(set(range(total_episodes(root / s["raw"]))) - set(keep[name])) for name, s in srcs.items()}, keep


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, default=REPO / "configs/data_mix.yaml")
    ap.add_argument("--execute", action="store_true")
    a = ap.parse_args()
    cfg = yaml.safe_load(a.config.read_text())
    root = REPO
    remove, keep = plan(cfg, root)
    cmds = []
    for name, s in cfg["sources"].items():
        print(f"{name:14s} raw {total_episodes(root / s['raw']):4d}  keep {len(keep[name]):4d}  remove {len(remove[name]):3d}")
        out = root / s["path"]
        if remove[name]:
            cmds.append(["lerobot-edit-dataset", f"--repo_id=local/{name}_raw", f"--root={root / s['raw']}",
                         f"--new_repo_id=local/{name}", f"--new_root={out}", "--operation.type=delete_episodes",
                         f"--operation.episode_indices={json.dumps(remove[name])}"])
        else:
            cmds.append(["COPY", str(root / s["raw"]), str(out)])
    for mix, names in cfg["mixes"].items():
        tot = sum(len(keep[n]) for n in names)
        print(f"mix {mix:9s} total {tot}")
        cmds.append(["lerobot-edit-dataset", f"--new_repo_id=local/mix_{mix}", f"--new_root={root / 'data/mix' / mix}",
                     "--operation.type=merge",
                     f"--operation.repo_ids={json.dumps(['local/' + n for n in names])}",
                     f"--operation.roots={json.dumps([str(root / cfg['sources'][n]['path']) for n in names])}"])
        cmds.append(["lerobot-edit-dataset", f"--repo_id=local/mix_{mix}", f"--root={root / 'data/mix' / mix}",
                     "--operation.type=recompute_stats"])  # Cosmos videos changed image stats
    plan_out = root / "data/curation/mix_plan.json"
    plan_out.parent.mkdir(parents=True, exist_ok=True)
    plan_out.write_text(json.dumps({"remove": remove, "keep_counts": {k: len(v) for k, v in keep.items()}}, indent=2))
    for c in cmds:
        print("  " + " ".join(c))
        if not a.execute:
            continue
        if c[0] == "COPY":
            if Path(c[2]).exists():
                shutil.rmtree(c[2])
            shutil.copytree(c[1], c[2])
        else:
            new_root = next((x.split("=", 1)[1] for x in c if x.startswith("--new_root=")), None)
            if new_root and Path(new_root).exists():  # rebuilt from raw every run
                shutil.rmtree(new_root)
            if subprocess.run(c).returncode:
                sys.exit("command failed; fix and rerun (outputs are rebuilt from raw each time)")
    if not a.execute:
        print("dry run: add --execute")


if __name__ == "__main__":
    main()
