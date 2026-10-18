#!/usr/bin/env python3
"""Count episodes per source from the datasets on disk, enforce the rules, write manifest.json.

Counts come from each dataset's meta/info.json (total_episodes), never from what we think we put
there. Exit code != 0 on any rule violation, so it can gate the training script.

Hard rules (hackathon brief):    real <= 50, total <= 300, main contains sim-derived data.
Our own rules (experiment design):
  - ablation has zero Cosmos episodes and the same total as main (controlled comparison)
  - every Cosmos source has its raw-sim twin in the ablation with the same episode count
  - all sources share fps, feature keys and shapes (otherwise lerobot-edit-dataset merge fails later)

    python scripts/validate_manifest.py                       # checks configs/data_mix.yaml
    python scripts/validate_manifest.py --out submission/manifest.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]


def load_info(path: Path) -> dict:
    f = path / "meta/info.json"
    if not f.exists():
        raise FileNotFoundError(f"{f} missing")
    return json.loads(f.read_text())


def signature(info: dict) -> dict:
    feats = {k: (v["dtype"], tuple(v["shape"])) for k, v in info["features"].items()
             if k.startswith("observation.") or k == "action"}
    return {"fps": info["fps"], "features": feats}


def check(cfg: dict, root: Path) -> tuple[dict, list[str], list[str]]:
    errors, warnings = [], []
    caps = cfg["caps"]
    manifest = {"rules": {"real_max": caps["real_max"], "total_max": caps["total_max"]}, "mixes": {}}
    sig_ref = None
    for mix, names in cfg["mixes"].items():
        counts = {"real": 0, "sim": 0, "cosmos": 0}
        rows = []
        for name in names:
            s = {"name": name, **cfg["sources"][name]}
            p = root / s["path"]
            try:
                info = load_info(p)
            except FileNotFoundError as e:
                errors.append(f"[{mix}] {s['name']}: {e}")
                continue
            n = int(info["total_episodes"])
            counts[s["kind"]] += n
            rows.append({"name": s["name"], "kind": s["kind"], "path": s["path"], "episodes": n,
                         "frames": int(info.get("total_frames", 0)), "codebase_version": info["codebase_version"],
                         **({"twin": s["twin"]} if "twin" in s else {})})
            sig = signature(info)
            if sig_ref is None:
                sig_ref = (s["name"], sig)
            elif sig != sig_ref[1]:
                errors.append(f"[{mix}] {s['name']} features/fps differ from {sig_ref[0]}: {sig} vs {sig_ref[1]}")
            if s["kind"] in ("sim", "cosmos") and "s2t_units" not in info:
                warnings.append(f"[{mix}] {s['name']}: no s2t_units marker in info.json; was it converted with "
                                "convert_sim_dataset.py? (the v3 converter may drop custom keys; check by hand)")
        total = sum(counts.values())
        manifest["mixes"][mix] = {"total": total, "per_kind": counts, "sources": rows}
        if counts["real"] > caps["real_max"]:
            errors.append(f"[{mix}] real episodes {counts['real']} > {caps['real_max']}")
        if total > caps["total_max"]:
            errors.append(f"[{mix}] total episodes {total} > {caps['total_max']}")
    m = manifest["mixes"]
    if "main" in m and m["main"]["per_kind"]["sim"] + m["main"]["per_kind"]["cosmos"] == 0:
        errors.append("[main] contains no sim-derived episodes (rule: main checkpoint must include sim data)")
    if "main" in m and "ablation" in m:
        if m["ablation"]["per_kind"]["cosmos"]:
            errors.append("[ablation] contains Cosmos episodes")
        if m["ablation"]["total"] != m["main"]["total"]:
            warnings.append(f"ablation total {m['ablation']['total']} != main total {m['main']['total']}: "
                            "the comparison is no longer controlled")
        abl = {r["name"]: r["episodes"] for r in m["ablation"]["sources"]}
        for r in m["main"]["sources"]:
            twin = r.get("twin")
            if twin and abl.get(twin) != r["episodes"]:
                warnings.append(f"{r['name']} has {r['episodes']} episodes but its raw twin {twin} has {abl.get(twin)} in ablation")
    cur = root / cfg.get("curation_file", "")
    if cfg.get("curation_file") and cur.exists():
        d = json.loads(cur.read_text())
        manifest["curation"] = {"rule": d.get("rule"),
                                "dropped": {k: len(v["drop"]) for k, v in d.get("datasets", {}).items()}}
    else:
        warnings.append("no Cosmos Reason curation file yet (Cosmos Reason rubric needs it)")
    return manifest, errors, warnings


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, default=REPO / "configs/data_mix.yaml")
    ap.add_argument("--root", type=Path, default=REPO)
    ap.add_argument("--out", type=Path, default=REPO / "submission/manifest.json")
    a = ap.parse_args()
    manifest, errors, warnings = check(yaml.safe_load(a.config.read_text()), a.root)
    for w in warnings:
        print("WARN ", w)
    for e in errors:
        print("ERROR", e)
    for mix, d in manifest["mixes"].items():
        print(f"{mix:9s} total {d['total']:4d}  {d['per_kind']}")
    if errors:
        sys.exit(1)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(manifest, indent=2))
    print("wrote", a.out)
