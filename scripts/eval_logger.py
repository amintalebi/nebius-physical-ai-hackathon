#!/usr/bin/env python3
"""Real-arm evaluation log: blind spot sequences, one row per trial, per-spot success matrix.

    # teammate generates a balanced, shuffled sequence and keeps it hidden from the policy operator
    python scripts/eval_logger.py sequence --per-spot 2 --seed 7 > /tmp/seq.txt
    # after each trial (same 2-min cap and success rule as the judges)
    python scripts/eval_logger.py log --ckpt main_40k --spot B2 --result success --seconds 31
    python scripts/eval_logger.py log --ckpt main_40k --spot A3 --result fail --failure missed_grasp --seconds 120
    # summary -> reports/eval_summary.md (+ .json)
    python scripts/eval_logger.py summary

Success (brief): cube released and at rest on the green pad, within 2 minutes.
Failure labels are fixed so they can be counted and acted on (docs/roadmap/09-eval-protocol.md).
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from s2t.stats import p_at_least_k_of_3, wilson_interval  # noqa: E402

LOG = REPO / "data/eval/trials.csv"
SPOTS = ["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3"]
FAILURES = ["missed_grasp", "dropped", "off_pad", "not_released", "timeout", "collision", "froze", "other"]
FIELDS = ["time", "ckpt", "spot", "result", "failure", "seconds", "operator", "blind", "note"]


def cmd_sequence(a):
    seq = SPOTS * a.per_spot
    random.Random(a.seed).shuffle(seq)
    print("\n".join(f"{i + 1:2d} {s}" for i, s in enumerate(seq)))


def cmd_log(a):
    if a.result == "fail" and not a.failure:
        sys.exit(f"--failure required for a fail; one of {FAILURES}")
    if a.seconds > 120 and a.result == "success":
        sys.exit("success after 120 s does not count: log it as fail --failure timeout")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    new = not LOG.exists()
    with open(LOG, "a", newline="") as f:
        w = csv.DictWriter(f, FIELDS)
        if new:
            w.writeheader()
        w.writerow({"time": dt.datetime.now().isoformat(timespec="seconds"), "ckpt": a.ckpt, "spot": a.spot,
                    "result": a.result, "failure": a.failure or "", "seconds": a.seconds, "operator": a.operator,
                    "blind": a.blind, "note": a.note})
    print("logged")


def cmd_summary(a):
    if not LOG.exists():
        sys.exit("no trials logged yet")
    rows = list(csv.DictReader(open(LOG)))
    by = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    fails = defaultdict(lambda: defaultdict(int))
    for r in rows:
        ok = r["result"] == "success"
        by[r["ckpt"]][r["spot"]][0] += ok
        by[r["ckpt"]][r["spot"]][1] += 1
        if not ok:
            fails[r["ckpt"]][r["failure"]] += 1
    out = {}
    lines = ["# Real-arm evaluation", "", f"Trials: {len(rows)} (log: data/eval/trials.csv)", "",
             "| ckpt | " + " | ".join(SPOTS) + " | total | 95% CI | P(>=2/3) |", "|---" * (len(SPOTS) + 4) + "|"]
    for ck, spots in sorted(by.items()):
        s = sum(v[0] for v in spots.values())
        n = sum(v[1] for v in spots.values())
        lo, hi = wilson_interval(s, n)
        p = s / n if n else 0.0
        cells = [f"{spots[sp][0]}/{spots[sp][1]}" if spots[sp][1] else "-" for sp in SPOTS]
        lines.append(f"| {ck} | " + " | ".join(cells) + f" | {s}/{n} | {lo:.2f}-{hi:.2f} | {p_at_least_k_of_3(p, 2):.2f} |")
        out[ck] = {"successes": s, "trials": n, "rate": p, "wilson95": [lo, hi],
                   "per_spot": {sp: spots[sp] for sp in SPOTS if spots[sp][1]}, "failures": dict(fails[ck])}
    lines += ["", "## Failure modes", ""]
    for ck, fm in sorted(fails.items()):
        lines.append(f"- **{ck}**: " + ", ".join(f"{k} {v}" for k, v in sorted(fm.items(), key=lambda x: -x[1])))
    rep = REPO / "reports"
    rep.mkdir(exist_ok=True)
    (rep / "eval_summary.md").write_text("\n".join(lines) + "\n")
    (rep / "eval_summary.json").write_text(json.dumps(out, indent=2))
    print("\n".join(lines))


ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
sub = ap.add_subparsers(dest="cmd", required=True)
p = sub.add_parser("sequence")
p.add_argument("--per-spot", type=int, default=2)
p.add_argument("--seed", type=int, required=True)
p.set_defaults(fn=cmd_sequence)
p = sub.add_parser("log")
p.add_argument("--ckpt", required=True)
p.add_argument("--spot", required=True, choices=SPOTS)
p.add_argument("--result", required=True, choices=["success", "fail"])
p.add_argument("--failure", choices=FAILURES)
p.add_argument("--seconds", type=float, required=True)
p.add_argument("--operator", default="")
p.add_argument("--blind", default="yes", choices=["yes", "no"], help="was the spot order hidden from the operator?")
p.add_argument("--note", default="")
p.set_defaults(fn=cmd_log)
p = sub.add_parser("summary")
p.set_defaults(fn=cmd_summary)

if __name__ == "__main__":
    a = ap.parse_args()
    a.fn(a)
