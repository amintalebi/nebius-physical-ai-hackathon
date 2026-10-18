#!/usr/bin/env python3
"""Negative control for the Cosmos Reason curator: does it actually say "drop" for bad episodes?

Scores a labelled list of clips (known-good expert episodes + known-bad clips) with exactly the same
request as scripts/cosmos_reason_score.py (inline base64 mp4, fps 4, temperature 0.6, top_p 0.95,
max_tokens 2048, same PROMPT / parse_answer / keep), then reports a confusion matrix of keep() vs the
expected decision, per-field agreement, Cohen's kappa and per-call latency.

    # 1. build clips + manifest (positives = untouched expert episodes, negatives = failed rollout +
    #    synthetic failures made with ffmpeg: truncated, reversed, frozen, visual defects)
    python scripts/reason_negative_control.py build --out ~/work/reason_check \
        --sim-dir ~/work/datasets/local/sim_A/videos/chunk-000/observation.images.front \
        --pos 0,5,10,15,20,25 --rollout ~/work/logs/eval_smoke/act_smoke_300_B2_0.mp4
    # 2. score (reads REASON_API_KEY / REASON_BASE_URL / REASON_MODEL from the environment)
    python scripts/reason_negative_control.py score --manifest ~/work/reason_check/manifest.json \
        --out ~/work/reports/reason_negative_control.jsonl
    #    optional one prompt revision (asks to inspect the final frame + impossible events), on a subset
    python scripts/reason_negative_control.py score ... --prompt-version 2 --select neg_,pos_sim_A_000000
    # 3. summary markdown (one section per prompt version)
    python scripts/reason_negative_control.py summary --jsonl ~/work/reports/reason_negative_control.jsonl \
        --out ~/work/reports/reason_negative_control.md

Scoring is resumable per (label, prompt_version). Unparsed answers count as "drop" (as in `decide`).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
_candidates = [HERE.parent, Path(os.environ.get("S2T_REPO", "~/work/s2t")).expanduser()]
REPO = next((c for c in _candidates if (c / "scripts/cosmos_reason_score.py").exists()), _candidates[0])
sys.path[:0] = [str(REPO), str(REPO / "scripts")]

from cosmos_reason_score import PROMPT, RULE, keep, parse_answer  # noqa: E402
from s2t.stats import cohen_kappa  # noqa: E402

# Prompt v2 = v1 plus an explicit end-state and physical-consistency check. Same JSON keys, same parser.
PROMPT_V2 = PROMPT.replace(
    "Watch the whole video, then answer in JSON with exactly these keys:",
    """Watch the whole video. Do not assume the task succeeded: judge only what is visible.
Before answering, check:
1. The LAST frame: where is the cube? It counts as success only if, in the last frame, the cube is resting
   on the green pad and the gripper has let go of it. If the video ends before the cube is on the pad, or the
   arm never picks it up, or the cube ends somewhere else, task_success is false.
2. Physical consistency across frames: the cube must never jump/teleport, appear twice, vanish, or change
   size/shape/colour, and the scene must not cut abruptly. Any of these means visual_defect is true.
Then answer in JSON with exactly these keys:""",
)
assert PROMPT_V2 != PROMPT
PROMPTS = {1: PROMPT, 2: PROMPT_V2}


# ----------------------------------------------------------------------------------------------- build
def ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def probe(path: Path) -> tuple[int, int, float, int]:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,nb_frames:format=duration", "-of", "json", str(path)],
                         check=True, capture_output=True, text=True).stdout
    j = json.loads(out)
    s = j["streams"][0]
    return int(s["width"]), int(s["height"]), float(j["format"]["duration"]), int(s.get("nb_frames", 0))


def cube_center(path: Path, w: int, h: int) -> tuple[int, int]:
    """Centroid of saturated-red pixels in frame 0 (the cube; arm is yellow, pad green, table grey)."""
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-frames:v", "1", "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], check=True, capture_output=True).stdout
    xs, ys = [], []
    for i in range(0, len(raw), 3):
        r, g, b = raw[i], raw[i + 1], raw[i + 2]
        if r > 140 and g < 90 and b < 90:
            p = i // 3
            xs.append(p % w)
            ys.append(p // w)
    if len(xs) < 10:
        raise RuntimeError(f"cube not found in {path}")
    return int(statistics.median(xs)), int(statistics.median(ys))


ENC = ["-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30"]


def cmd_build(a):
    out = a.out.expanduser()
    clips = out / "clips"
    clips.mkdir(parents=True, exist_ok=True)
    sim = a.sim_dir.expanduser()
    ep = lambda i: sim / f"episode_{i:06d}.mp4"  # noqa: E731
    items = []

    def add(label, path, keep_, ts, vd, how):
        items.append({"label": label, "path": str(path), "expected_keep": keep_, "expected_task_success": ts,
                      "expected_visual_defect": vd, "construction": how})

    for i in map(int, a.pos.split(",")):
        add(f"pos_sim_A_{i:06d}", ep(i), True, True, False, "untouched expert success episode")
    add("neg_rollout_act_smoke_300_B2_0", a.rollout.expanduser(), False, False, False,
        "real failed ACT policy rollout (arm moves, never completes the task)")

    n = dict(zip(["trunc", "trunc2", "rev", "rev2", "freeze", "freeze2", "redbox", "splice", "splice2", "dup"],
                 map(int, a.neg.split(","))))
    for key in ("trunc", "trunc2"):
        src = ep(n[key]); _, _, d, _ = probe(src); dst = clips / f"neg_{key}_{n[key]:06d}.mp4"
        ff("-i", str(src), "-t", f"{0.4 * d:.2f}", *ENC, str(dst))
        add(dst.stem, dst, False, False, False, f"first 40% ({0.4 * d:.1f}s) of episode {n[key]}: cube never reaches the pad")
    for key in ("rev", "rev2"):
        src = ep(n[key]); dst = clips / f"neg_{key}_{n[key]:06d}.mp4"
        ff("-i", str(src), "-vf", "reverse", *ENC, str(dst))
        add(dst.stem, dst, False, False, False, f"episode {n[key]} played backwards: cube ends at its start, off the pad")
    for key in ("freeze", "freeze2"):
        src = ep(n[key]); dst = clips / f"neg_{key}_{n[key]:06d}.mp4"
        ff("-i", str(src), "-vf", "trim=end_frame=1,loop=loop=-1:size=1,setpts=N/30/TB", "-t", "8", *ENC, str(dst))
        add(dst.stem, dst, False, False, False, f"frame 0 of episode {n[key]} held for 8 s: nothing happens")
    # visual defects: the task still ends on the pad, but the pixels are physically wrong
    src = ep(n["redbox"]); w, h, d, _ = probe(src); cx, cy = cube_center(src, w, h); s = 90
    dst = clips / f"neg_redbox_{n['redbox']:06d}.mp4"
    ff("-i", str(src), "-vf", f"drawbox=x={cx - s // 2}:y={cy - s // 2}:w={s}:h={s}:color=red@1:t=fill:"
       f"enable='lt(t,{d / 2:.2f})'", *ENC, str(dst))
    add(dst.stem, dst, False, True, True,
        f"episode {n['redbox']} with a {s}px solid red square over the cube's start position for the first half (giant cube)")
    for key, other in (("splice", "splice2"),):
        a1, a2 = ep(n[key]), ep(n[other]); _, _, d1, _ = probe(a1); _, _, d2, _ = probe(a2)
        dst = clips / f"neg_splice_{n[key]:06d}_{n[other]:06d}.mp4"
        ff("-i", str(a1), "-i", str(a2), "-filter_complex",
           f"[0:v]trim=0:{d1 / 2:.2f},setpts=PTS-STARTPTS[a];[1:v]trim={d2 / 2:.2f},setpts=PTS-STARTPTS[b];"
           "[a][b]concat=n=2:v=1[v]", "-map", "[v]", *ENC, str(dst))
        add(dst.stem, dst, False, True, True,
            f"first half of episode {n[key]} + second half of episode {n[other]}: cube/arm teleport at the cut")
    src = ep(n["dup"]); w, h, d, _ = probe(src); cx, cy = cube_center(src, w, h); c = 28; dx = 70 if cx < w - 120 else -70
    dst = clips / f"neg_dup_{n['dup']:06d}.mp4"
    ff("-i", str(src), "-filter_complex",
       f"[0:v]split[m][c];[c]trim=end_frame=1,crop={c}:{c}:{cx - c // 2}:{cy - c // 2},loop=loop=-1:size=1,"
       f"setpts=N/30/TB[p];[m][p]overlay=x={cx - c // 2 + dx}:y={cy - c // 2}:shortest=1", *ENC, str(dst))
    add(dst.stem, dst, False, True, True,
        f"episode {n['dup']} with a static copy of the cube pasted {dx:+d}px beside it for the whole clip (duplicate cube)")

    (out / "manifest.json").write_text(json.dumps(items, indent=2))
    for it in items:
        print(f"{it['label']:34s} keep={it['expected_keep']!s:5s} {it['construction']}")


# ----------------------------------------------------------------------------------------------- score
def cmd_score(a):
    from openai import OpenAI

    client = OpenAI(api_key=a.api_key, base_url=a.base_url)
    model = a.model or client.models.list().data[0].id
    items = json.loads(a.manifest.expanduser().read_text())
    if a.select:
        pre = a.select.split(",")
        items = [it for it in items if any(it["label"].startswith(p) for p in pre)]
    out = a.out.expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        done = {(r["label"], r["prompt_version"]) for r in map(json.loads, out.read_text().splitlines())}
    todo = [it for it in items if (it["label"], a.prompt_version) not in done]
    if len(todo) > a.max_calls:
        sys.exit(f"{len(todo)} calls > --max-calls {a.max_calls}; narrow with --select")
    with open(out, "a") as f:
        for it in todo:
            url = "data:video/mp4;base64," + base64.b64encode(Path(it["path"]).read_bytes()).decode()
            row = {**it, "model": model, "prompt_version": a.prompt_version, "fps": a.fps}
            t0 = time.time()
            try:
                r = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": "You are a helpful assistant."},
                              {"role": "user", "content": [{"type": "video_url", "video_url": {"url": url}},
                                                           {"type": "text", "text": PROMPTS[a.prompt_version]}]}],
                    max_tokens=2048, temperature=0.6, top_p=0.95,
                    extra_body={"media_io_kwargs": {"video": {"num_frames": -1, "fps": a.fps}}},
                )
                row["latency_s"] = round(time.time() - t0, 2)
                row["raw"] = r.choices[0].message.content
                row["answer"] = parse_answer(row["raw"])
            except Exception as e:
                row.setdefault("latency_s", round(time.time() - t0, 2))
                row["error"] = repr(e)
            row["pred_keep"] = keep(row["answer"]) if "answer" in row else False
            f.write(json.dumps(row) + "\n")
            f.flush()
            ans = row.get("answer", {})
            print(f"v{a.prompt_version} {it['label']:34s} exp={it['expected_keep']!s:5s} pred={row['pred_keep']!s:5s} "
                  f"{row['latency_s']:5.1f}s ts={ans.get('task_success')} vd={ans.get('visual_defect')} "
                  f"mq={ans.get('motion_quality')} fm={ans.get('failure_mode')} | {ans.get('notes', row.get('error'))}",
                  flush=True)


# --------------------------------------------------------------------------------------------- summary
def stats(rows: list[dict]) -> dict:
    exp = [r["expected_keep"] for r in rows]
    pred = [r["pred_keep"] for r in rows]
    cm = {"TP_keep": sum(e and p for e, p in zip(exp, pred)), "FN_false_drop": sum(e and not p for e, p in zip(exp, pred)),
          "FP_false_keep": sum(p and not e for e, p in zip(exp, pred)), "TN_drop": sum(not e and not p for e, p in zip(exp, pred))}
    parsed = [r for r in rows if "answer" in r]
    field = {}
    for k in ("task_success", "visual_defect"):
        field[k] = (sum(bool(r["answer"].get(k)) == r[f"expected_{k}"] for r in parsed), len(parsed))
    lat = [r["latency_s"] for r in rows]
    kappa = cohen_kappa(exp, pred) if len(set(exp)) > 1 else None
    return {"n": len(rows), "unparsed": len(rows) - len(parsed), "cm": cm,
            "accuracy": sum(e == p for e, p in zip(exp, pred)) / len(rows), "kappa": kappa, "field": field,
            "latency": {"mean": statistics.mean(lat), "median": statistics.median(lat), "min": min(lat), "max": max(lat)}}


def cmd_summary(a):
    rows = [json.loads(l) for l in a.jsonl.expanduser().read_text().splitlines() if l.strip()]
    md = ["# Cosmos Reason curator: negative control", "",
          f"Model `{rows[0]['model']}`, request identical to `scripts/cosmos_reason_score.py` "
          f"(inline mp4, fps {rows[0]['fps']}, temperature 0.6, top_p 0.95, max_tokens 2048).",
          f"Curation rule under test: `{RULE}`. Expected labels are known by construction (see table).", ""]
    for v in sorted({r["prompt_version"] for r in rows}):
        rs = [r for r in rows if r["prompt_version"] == v]
        s = stats(rs)
        cm = s["cm"]
        kap = "n/a (one class)" if s["kappa"] is None else f"{s['kappa']:.2f}"
        md += [f"## Prompt v{v} ({s['n']} clips, {sum(r['expected_keep'] for r in rs)} positive, "
               f"{sum(not r['expected_keep'] for r in rs)} negative)", "",
               "| | predicted keep | predicted drop |", "|---|---|---|",
               f"| expected keep | {cm['TP_keep']} | {cm['FN_false_drop']} |",
               f"| expected drop | {cm['FP_false_keep']} | {cm['TN_drop']} |", "",
               f"- accuracy {s['accuracy']:.2f}, Cohen's kappa {kap}, false keeps {cm['FP_false_keep']}, "
               f"false drops {cm['FN_false_drop']}, unparsed {s['unparsed']}",
               "- per-field agreement with construction labels: " + ", ".join(
                   f"`{k}` {c}/{n}" for k, (c, n) in s["field"].items()),
               f"- latency per call (s): mean {s['latency']['mean']:.1f}, median {s['latency']['median']:.1f}, "
               f"min {s['latency']['min']:.1f}, max {s['latency']['max']:.1f}", "",
               "| clip | expected | pred keep | task_success | visual_defect | motion | failure_mode | notes |",
               "|---|---|---|---|---|---|---|---|"]
        for r in rs:
            an = r.get("answer", {})
            mark = "" if r["pred_keep"] == r["expected_keep"] else " **WRONG**"
            notes = str(an.get("notes", r.get("error", ""))).replace("|", "/")
            md.append(f"| `{r['label']}` | {'keep' if r['expected_keep'] else 'drop'} | {r['pred_keep']}{mark} | "
                      f"{an.get('task_success')} | {an.get('visual_defect')} | {an.get('motion_quality')} | "
                      f"{an.get('failure_mode')} | {notes} |")
        md.append("")
    md += ["## How each clip was made", ""]
    seen = set()
    for r in rows:
        if r["label"] not in seen:
            seen.add(r["label"])
            md.append(f"- `{r['label']}`: {r['construction']}")
    a.out.expanduser().write_text("\n".join(md) + "\n")
    print("\n".join(md))


ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
sub = ap.add_subparsers(dest="cmd", required=True)
p = sub.add_parser("build")
p.add_argument("--out", type=Path, required=True)
p.add_argument("--sim-dir", type=Path, required=True, help="v2.1 per-episode mp4 dir of finished expert episodes")
p.add_argument("--pos", default="0,5,10,15,20,25", help="episode indices used untouched as positives")
p.add_argument("--neg", default="3,7,12,17,22,27,30,13,18,33",
               help="source episodes for trunc,trunc2,rev,rev2,freeze,freeze2,redbox,splice,splice2,dup")
p.add_argument("--rollout", type=Path, required=True, help="a real failed policy rollout mp4")
p.set_defaults(fn=cmd_build)
p = sub.add_parser("score")
p.add_argument("--manifest", type=Path, required=True)
p.add_argument("--out", type=Path, required=True)
p.add_argument("--prompt-version", type=int, choices=sorted(PROMPTS), default=1)
p.add_argument("--select", default="", help="comma-separated label prefixes to score (default: all)")
p.add_argument("--max-calls", type=int, default=20, help="refuse to run more requests than this (billed endpoint)")
p.add_argument("--base-url", default=os.environ.get("REASON_BASE_URL", "http://localhost:8000/v1"))
p.add_argument("--api-key", default=os.environ.get("REASON_API_KEY", "EMPTY"))
p.add_argument("--model", default=os.environ.get("REASON_MODEL"))
p.add_argument("--fps", type=int, default=4)
p.set_defaults(fn=cmd_score)
p = sub.add_parser("summary")
p.add_argument("--jsonl", type=Path, required=True)
p.add_argument("--out", type=Path, required=True)
p.set_defaults(fn=cmd_summary)

if __name__ == "__main__":
    a = ap.parse_args()
    a.fn(a)
