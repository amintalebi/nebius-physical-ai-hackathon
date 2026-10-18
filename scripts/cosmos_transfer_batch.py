#!/usr/bin/env python3
"""Re-render sim episodes toward the real station look with Cosmos Transfer 2.5 (edge control).

Actions stay valid only if every output frame lines up with its input frame, so this script
(a) never changes the frame count, (b) keeps the camera geometry (edge control, high weight), and
(c) checks both before writing a dataset.

    # 1. split episode videos into 93-frame segments + write spec shards (one per GPU)
    python scripts/cosmos_transfer_batch.py prepare --dataset data/sim/B_real_units \
        --work work/cosmos_B --style-image configs/cosmos/station_reference.jpg --gpus 8 --variants 1
    # 2. run Cosmos (inside the cosmos-transfer2.5 checkout, its venv active)
    python scripts/cosmos_transfer_batch.py run --work work/cosmos_B --cosmos-repo ~/cosmos-transfer2.5
    # 3. stitch, verify, and write a copy of the dataset whose videos are the Cosmos outputs
    python scripts/cosmos_transfer_batch.py assemble --dataset data/sim/B_real_units \
        --work work/cosmos_B --dst data/cosmos/B_transfer

Segments are generated independently (the distilled edge model is "strictly 93 frames", per
cosmos-transfer2.5 docs/inference.md), so the same style image + seed is used for every segment of an
episode to keep the look consistent across segment boundaries. Check boundaries in the QA sheet.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

SEG = 93  # Cosmos Transfer 2.5 chunk length (config.py: num_video_frames_per_chunk = 93)
REPO = Path(__file__).resolve().parents[1]


def read_frames(path: Path) -> np.ndarray:
    import cv2

    cap = cv2.VideoCapture(str(path))
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
    cap.release()
    if not frames:
        raise RuntimeError(f"no frames decoded from {path}")
    return np.stack(frames)


def write_frames(path: Path, frames: np.ndarray, fps: int) -> None:
    """h264/yuv420p like the starter writer, so LeRobot decodes it the same way as sim videos."""
    path.parent.mkdir(parents=True, exist_ok=True)
    n, h, w, _ = frames.shape
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
           "-r", str(fps), "-i", "-", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-g", "10", str(path)]
    p = subprocess.run(cmd, input=np.ascontiguousarray(frames, dtype=np.uint8).tobytes())
    if p.returncode:
        raise RuntimeError(f"ffmpeg failed writing {path}")


def episode_videos(dataset: Path, cam: str) -> dict[int, Path]:
    vids = sorted((dataset / "videos").glob(f"chunk-*/observation.images.{cam}/episode_*.mp4"))
    return {int(v.stem.split("_")[1]): v for v in vids}


def episode_lengths(dataset: Path) -> dict[int, int]:
    out = {}
    for line in (dataset / "meta/episodes.jsonl").read_text().splitlines():
        if line.strip():
            e = json.loads(line)
            out[e["episode_index"]] = e["length"]
    return out


def cmd_prepare(a):
    import yaml

    st = yaml.safe_load((REPO / "configs/station.yaml").read_text())
    cam = st["camera"]["key"]
    prompts = [p.strip() for p in (REPO / "configs/cosmos/station_prompts.txt").read_text().split("\n---\n") if p.strip()]
    if a.variants > len(prompts):
        sys.exit(f"--variants {a.variants} but only {len(prompts)} prompts in configs/cosmos/station_prompts.txt")
    style = None
    if a.style_image:  # optional: without it Cosmos picks a random frame of the input segment (prompt-only look)
        style = Path(a.style_image).resolve()
        if not style.exists():
            sys.exit(f"style image {style} missing: grab a frame from the station camera first (docs/roadmap/04)")
    else:
        print("[warn] no --style-image: prompt-only transfer (Cosmos uses a frame of the sim input as image context)")
    vids = episode_videos(a.dataset, cam)
    lens = episode_lengths(a.dataset)
    eps = sorted(vids)[: a.limit] if a.limit else sorted(vids)
    work = a.work.resolve()
    specs = []
    for ep in eps:
        frames = read_frames(vids[ep])
        if len(frames) != lens[ep]:
            sys.exit(f"episode {ep}: video has {len(frames)} frames, parquet says {lens[ep]}")
        for s0 in range(0, len(frames), SEG):
            seg = frames[s0 : s0 + SEG]
            if len(seg) < SEG:  # pad the tail by repeating the last frame; trimmed again in assemble
                seg = np.concatenate([seg, np.repeat(seg[-1:], SEG - len(seg), 0)])
            seg_path = work / "segments" / f"ep{ep:06d}_s{s0:04d}.mp4"
            write_frames(seg_path, seg, a.fps_in)
            for v in range(a.variants):
                spec = {
                    "name": f"ep{ep:06d}_v{v}_s{s0:04d}",
                    "prompt": prompts[v],
                    "video_path": str(seg_path),
                    "guidance": a.guidance,
                    "seed": 1000 + ep * 10 + v,  # same seed for all segments of one episode-variant
                    "num_steps": a.num_steps,
                    "edge": {"control_weight": a.edge_weight, "preset_edge_threshold": a.edge_threshold},
                }
                if style is not None:
                    spec["image_context_path"] = str(style)
                if a.resolution:
                    spec["resolution"] = a.resolution
                specs.append(spec)
    (work / "shards").mkdir(parents=True, exist_ok=True)
    for g in range(a.gpus):
        with open(work / "shards" / f"shard_{g}.jsonl", "w") as f:
            for s in specs[g :: a.gpus]:
                f.write(json.dumps(s) + "\n")
    meta = {"episodes": eps, "variants": a.variants, "lengths": {str(e): lens[e] for e in eps}, "camera": cam,
            "model": a.model, "gpus": a.gpus, "edge_weight": a.edge_weight, "num_steps": a.num_steps}
    (work / "job.json").write_text(json.dumps(meta, indent=2))
    print(f"{len(eps)} episodes -> {len(specs)} segment jobs in {a.gpus} shards under {work}/shards")


def cmd_run(a):
    work = a.work.resolve()
    job = json.loads((work / "job.json").read_text())
    procs = []
    for g in range(job["gpus"]):
        shard = work / "shards" / f"shard_{g}.jsonl"
        if not shard.read_text().strip():
            continue
        out = work / "out"
        cmd = [a.python, "examples/inference.py", "-i", str(shard), "-o", str(out), f"--model={job['model']}"]
        if not a.guardrails:  # guardrails need meta-llama/Llama-Guard-3-8B (gated, our token can't access it)
            cmd.append("--disable-guardrails")
        cmd += [x for x in a.extra if x != "--"]  # argparse keeps the "--" separator in REMAINDER
        env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(g))
        # Cosmos downloads weights via `uvx hf download`; uvx lives in the Cosmos venv, not on a bare PATH
        venv_bin = (Path(a.cosmos_repo) / a.python).parent.resolve()
        env["PATH"] = f"{venv_bin}{os.pathsep}{env.get('PATH', '')}"
        if job["model"].endswith("/distilled"):  # edge/distilled is only registered with this flag (config.py)
            env["COSMOS_EXPERIMENTAL_CHECKPOINTS"] = "1"
        log = open(work / f"run_gpu{g}.log", "w")
        print("GPU", g, ":", " ".join(cmd))
        procs.append(subprocess.Popen(cmd, cwd=a.cosmos_repo, env=env, stdout=log, stderr=subprocess.STDOUT))
    rc = [p.wait() for p in procs]
    print("exit codes:", rc)
    sys.exit(max(rc) if rc else 0)


def cmd_assemble(a):
    work = a.work.resolve()
    job = json.loads((work / "job.json").read_text())
    cam = job["camera"]
    report = []
    for v in range(job["variants"]):
        dst = Path(f"{a.dst}_v{v}") if job["variants"] > 1 else a.dst
        if dst.exists():
            sys.exit(f"{dst} exists")
        # copy meta + data; videos come from Cosmos
        shutil.copytree(a.dataset / "meta", dst / "meta")
        shutil.copytree(a.dataset / "data", dst / "data")
        # other cameras (e.g. wrist) are not transferred: keep their raw sim videos so the dataset stays loadable
        for d in (a.dataset / "videos").glob("chunk-*/observation.images.*"):
            if d.name != f"observation.images.{cam}":
                shutil.copytree(d, dst / d.relative_to(a.dataset))
        kept = []
        for ep in job["episodes"]:
            n = job["lengths"][str(ep)]
            parts = []
            for s0 in range(0, n, SEG):
                f = work / "out" / f"ep{ep:06d}_v{v}_s{s0:04d}.mp4"
                if not f.exists():
                    parts = None
                    break
                fr = read_frames(f)
                if len(fr) != SEG:
                    parts = None
                    report.append({"episode": ep, "variant": v, "status": f"segment {s0} has {len(fr)} frames"})
                    break
                parts.append(fr)
            if parts is None:
                # keep the dataset structurally complete (every parquet episode needs a video) with the raw
                # sim video, and list the episode so build_mixes.py removes it (and its raw twin)
                raw = episode_videos(a.dataset, cam)[ep]
                out = dst / raw.relative_to(a.dataset)
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(raw, out)
                report.append({"episode": ep, "variant": v, "status": "missing or bad segment: raw video kept, must drop"})
                continue
            frames = np.concatenate(parts)[:n]
            if frames.shape[1:3] != (480, 640):
                import cv2

                frames = np.stack([cv2.resize(x, (640, 480), interpolation=cv2.INTER_AREA) for x in frames])
            chunk = ep // 1000
            write_frames(dst / "videos" / f"chunk-{chunk:03d}" / f"observation.images.{cam}" / f"episode_{ep:06d}.mp4", frames, 30)
            kept.append(ep)
            report.append({"episode": ep, "variant": v, "status": "ok", "frames": int(len(frames))})
        # episodes never sent to Cosmos (--limit) or whose output failed are not Cosmos data
        all_eps = sorted(episode_lengths(a.dataset))
        missing = sorted(set(all_eps) - set(kept))
        for ep in sorted(set(all_eps) - set(job["episodes"])):
            raw = episode_videos(a.dataset, cam)[ep]
            out = dst / raw.relative_to(a.dataset)
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(raw, out)
        info = json.loads((dst / "meta/info.json").read_text())
        info["s2t_cosmos"] = {"variant": v, "source": str(a.dataset), "work": str(work), "not_cosmos": missing}
        (dst / "meta/info.json").write_text(json.dumps(info, indent=4))
        # the v3 converter may not keep custom info keys, so the drop list also lives in data/curation/
        drop_file = REPO / "data/curation" / f"cosmos_not_transferred_{dst.name}.json"
        drop_file.parent.mkdir(parents=True, exist_ok=True)
        drop_file.write_text(json.dumps({"dataset": str(dst), "drop": missing}, indent=2))
        if missing:
            print(f"[warn] {dst}: {len(missing)} episodes are not Cosmos output (raw video kept): listed in {drop_file}")
        print(f"{dst}: {len(kept)} episodes assembled. Image stats are stale: recompute after merge.")
    (work / "assemble_report.json").write_text(json.dumps(report, indent=2))


ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
sub = ap.add_subparsers(dest="cmd", required=True)
p = sub.add_parser("prepare")
p.add_argument("--dataset", type=Path, required=True)
p.add_argument("--work", type=Path, required=True)
p.add_argument("--style-image", default=None,
               help="a real frame from the station camera (image_context_path); omit for prompt-only transfer")
p.add_argument("--resolution", default=None, help='Cosmos generation resolution, e.g. "480" (default: model default 720)')
p.add_argument("--gpus", type=int, default=1)
p.add_argument("--variants", type=int, default=1, help="appearance variants per episode (each counts toward 300)")
p.add_argument("--limit", type=int, default=0, help="only the first N episodes (smoke test)")
p.add_argument("--model", default="edge/distilled", help="edge/distilled (4 steps, ~8x faster) or the base edge model")
p.add_argument("--num-steps", type=int, default=4, help="4 for edge/distilled, 35 for base")
p.add_argument("--guidance", type=float, default=3)
p.add_argument("--edge-weight", type=float, default=1.0)
p.add_argument("--edge-threshold", default="medium", choices=["very_low", "low", "medium", "high", "very_high"])
p.add_argument("--fps-in", type=int, default=30)
p.set_defaults(fn=cmd_prepare)
p = sub.add_parser("run")
p.add_argument("--work", type=Path, required=True)
p.add_argument("--cosmos-repo", type=Path, required=True)
p.add_argument("--python", default=".venv/bin/python", help="Cosmos venv python, relative to --cosmos-repo")
p.add_argument("--guardrails", action="store_true", help="keep Cosmos guardrails on (default: --disable-guardrails)")
p.add_argument("extra", nargs=argparse.REMAINDER, help="extra args passed to examples/inference.py")
p.set_defaults(fn=cmd_run)
p = sub.add_parser("assemble")
p.add_argument("--dataset", type=Path, required=True)
p.add_argument("--work", type=Path, required=True)
p.add_argument("--dst", type=Path, required=True)
p.set_defaults(fn=cmd_assemble)

if __name__ == "__main__":
    a = ap.parse_args()
    a.fn(a)
