#!/usr/bin/env python3
"""Cosmos Reason as the curator: score every episode video, apply one stated rule, save JSON.

Talks to any OpenAI-compatible endpoint serving a Cosmos 3 Reasoner, e.g. on the Nebius VM
(NVIDIA/Cosmos @6e2c69a, cookbooks/cosmos3/README.md):
    vllm serve nvidia/Cosmos3-Nano --tensor-parallel-size 1 --mm-encoder-tp-mode data \
        --async-scheduling --allowed-local-media-path / --media-io-kwargs '{"video": {"num_frames": -1}}' --port 8000

    # score (sim = v2.1 per-episode mp4s; real/cosmos v3 datasets are cut into per-episode clips)
    python scripts/cosmos_reason_score.py score --name real --dataset data/real/station_v3
    python scripts/cosmos_reason_score.py score --name sim_raw_A --dataset data/sim/A_real_units
    python scripts/cosmos_reason_score.py score --name sim_cosmos_B --dataset data/cosmos/B_transfer
    # decide: applies the rule below to every scored dataset -> data/curation/decisions.json
    python scripts/cosmos_reason_score.py decide
    # validate the curator against hand labels before trusting it (CSV: name,episode,success)
    python scripts/cosmos_reason_score.py agree --labels data/curation/hand_labels.csv

THE CURATION RULE (one decision, stated up front, also written into decisions.json):
    keep an episode iff  task_success AND NOT visual_defect AND motion_quality >= 3
    - task_success: Reason says the cube ended released and at rest on the green pad
    - visual_defect: cube vanishes/duplicates/changes shape, or the arm warps (catches Cosmos
      hallucinations that would teach the policy wrong pixels)
    - motion_quality: 1-5, drops hesitant/jerky teleop demos that teach hesitation
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CUR = REPO / "data/curation"
RULE = "keep iff task_success and not visual_defect and motion_quality >= 3"

PROMPT = """You are checking one robot demonstration video for a training dataset.
Task shown: a robot arm should pick up a small cube and place it on a flat green pad, then release it.
Watch the whole video, then answer in JSON with exactly these keys:
{
  "grasped": true/false,            // the gripper closed on the cube and lifted it off the table
  "task_success": true/false,       // at the end the cube is released and resting on the green pad
  "visual_defect": true/false,      // cube disappears, duplicates, changes shape/colour, or the arm/gripper warps or melts
  "motion_quality": 1-5,            // 5 = smooth and direct, 1 = jerky, hesitant, many corrections
  "failure_mode": "none" | "missed_grasp" | "dropped" | "off_pad" | "not_released" | "incomplete" | "other",
  "notes": "one short sentence"
}
Answer the question using the following format:
<think>
Your reasoning.
</think>
Write your final answer immediately after the </think> tag."""


def video_clips(dataset: Path, camera: str, tmp: Path) -> dict[int, Path]:
    info = json.loads((dataset / "meta/info.json").read_text())
    key = f"observation.images.{camera}"
    if info["codebase_version"] == "v2.1":
        return {int(p.stem.split("_")[1]): p for p in sorted(dataset.glob(f"videos/chunk-*/{key}/episode_*.mp4"))}
    # v3.0: several episodes per mp4; cut by the episode's from/to timestamps
    import pyarrow.parquet as pq

    clips = {}
    for pf in sorted((dataset / "meta/episodes").rglob("*.parquet")):
        t = pq.read_table(pf).to_pylist()
        for ep in t:
            src = dataset / "videos" / key / f"chunk-{ep[f'videos/{key}/chunk_index']:03d}" / f"file-{ep[f'videos/{key}/file_index']:03d}.mp4"
            t0, t1 = ep[f"videos/{key}/from_timestamp"], ep[f"videos/{key}/to_timestamp"]
            out = tmp / f"episode_{ep['episode_index']:06d}.mp4"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t0:.3f}", "-to", f"{t1:.3f}", "-i", str(src),
                            "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)], check=True)
            clips[int(ep["episode_index"])] = out
    return clips


def parse_answer(text: str) -> dict:
    tail = text.split("</think>")[-1]
    m = re.search(r"\{.*\}", tail, re.S)
    if not m:
        raise ValueError("no JSON object in answer")
    return json.loads(re.sub(r"//[^\n]*", "", m.group(0)))


def cmd_score(a):
    from openai import OpenAI

    client = OpenAI(api_key=a.api_key, base_url=a.base_url)
    model = a.model or client.models.list().data[0].id
    CUR.mkdir(parents=True, exist_ok=True)
    out = CUR / f"reason_{a.name}.jsonl"
    done = set()
    if out.exists():
        done = {json.loads(l)["episode"] for l in out.read_text().splitlines() if l.strip()}
    with tempfile.TemporaryDirectory() as td, open(out, "a") as f:
        clips = video_clips(a.dataset, a.camera, Path(td))
        for ep, path in sorted(clips.items()):
            if ep in done:
                continue
            if a.inline:  # remote endpoint without access to our disk: send the video as a data URL
                url = "data:video/mp4;base64," + base64.b64encode(path.read_bytes()).decode()
            else:
                url = path.resolve().as_uri()
            row = {"name": a.name, "episode": ep, "video": str(path), "model": model, "prompt_version": 1}
            try:
                r = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": "You are a helpful assistant."},
                              {"role": "user", "content": [{"type": "video_url", "video_url": {"url": url}},
                                                           {"type": "text", "text": PROMPT}]}],
                    max_tokens=2048, temperature=0.6, top_p=0.95,
                    extra_body={"media_io_kwargs": {"video": {"num_frames": -1, "fps": a.fps}}},
                )
                row["raw"] = r.choices[0].message.content
                row["answer"] = parse_answer(row["raw"])
            except Exception as e:  # keep going; unparsed rows are dropped by `decide` and listed
                row["error"] = repr(e)
            f.write(json.dumps(row) + "\n")
            f.flush()
            print(ep, row.get("answer", row.get("error")), flush=True)


def keep(ans: dict) -> bool:
    return bool(ans.get("task_success")) and not bool(ans.get("visual_defect")) and int(ans.get("motion_quality", 0)) >= 3


def cmd_decide(a):
    decisions = {"rule": RULE, "datasets": {}}
    for p in sorted(CUR.glob("reason_*.jsonl")):
        rows = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
        name = rows[0]["name"] if rows else p.stem[7:]
        drop, errors, modes = [], [], {}
        for r in rows:
            if "answer" not in r:
                errors.append(r["episode"])
                drop.append(r["episode"])
                continue
            fm = r["answer"].get("failure_mode", "other")
            modes[fm] = modes.get(fm, 0) + 1
            if not keep(r["answer"]):
                drop.append(r["episode"])
        decisions["datasets"][name] = {"scored": len(rows), "drop": sorted(set(drop)), "unparsed": errors,
                                       "kept": len(rows) - len(set(drop)), "failure_modes": modes}
    (CUR / "decisions.json").write_text(json.dumps(decisions, indent=2))
    for n, d in decisions["datasets"].items():
        print(f"{n:16s} scored {d['scored']:4d}  keep {d['kept']:4d}  drop {len(d['drop']):3d}  modes {d['failure_modes']}")


def cmd_agree(a):
    sys.path.insert(0, str(REPO))
    from s2t.stats import cohen_kappa

    pred = {}
    for p in CUR.glob("reason_*.jsonl"):
        for l in p.read_text().splitlines():
            r = json.loads(l)
            if "answer" in r:
                pred[(r["name"], int(r["episode"]))] = keep(r["answer"])
    human, model = [], []
    with open(a.labels) as f:
        for row in csv.DictReader(f):
            k = (row["name"], int(row["episode"]))
            if k in pred:
                human.append(row["success"].strip().lower() in ("1", "true", "yes"))
                model.append(pred[k])
    if not human:
        sys.exit("no overlap between hand labels and scored episodes")
    acc = sum(h == m for h, m in zip(human, model)) / len(human)
    res = {"n": len(human), "accuracy": acc, "cohen_kappa": cohen_kappa(human, model),
           "false_keep": sum(m and not h for h, m in zip(human, model)),
           "false_drop": sum(h and not m for h, m in zip(human, model))}
    (CUR / "agreement.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))


ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
sub = ap.add_subparsers(dest="cmd", required=True)
p = sub.add_parser("score")
p.add_argument("--name", required=True, help="dataset name as used in configs/data_mix.yaml")
p.add_argument("--dataset", type=Path, required=True)
p.add_argument("--camera", default="front")
p.add_argument("--base-url", default="http://localhost:8000/v1")
p.add_argument("--api-key", default="EMPTY")
p.add_argument("--model", default=None, help="default: first model the server lists")
p.add_argument("--fps", type=int, default=4, help="frames/s sampled by the reasoner (cookbook default 4)")
p.add_argument("--inline", action="store_true", help="send video bytes instead of a file:// URL")
p.set_defaults(fn=cmd_score)
p = sub.add_parser("decide")
p.set_defaults(fn=cmd_decide)
p = sub.add_parser("agree")
p.add_argument("--labels", type=Path, required=True)
p.set_defaults(fn=cmd_agree)

if __name__ == "__main__":
    a = ap.parse_args()
    a.fn(a)
