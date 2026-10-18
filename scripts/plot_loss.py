#!/usr/bin/env python3
"""Loss curve PNG from LeRobot train logs (the INFO lines `step:300 smpl:2K ep:8 epch:2.62 loss:2.962 ...`).

    python scripts/plot_loss.py ~/work/logs/train_act_main.log                      # -> train_act_main.loss.png
    python scripts/plot_loss.py logs/train_main.log logs/train_ablation.log -o nebius/loss_curves.png

Several logs go on one figure (one line each, labelled by file name). Needs only matplotlib. The log may be the
raw tqdm-interleaved output: lines are found by regex anywhere in the text, not at line starts. Step counts
written with K/M suffixes (LeRobot's format_big_number) are expanded. A log restarted with --resume can repeat
steps; the last value for a step wins.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

STEP_LINE = re.compile(r"\bstep:(?P<step>[0-9.]+)(?P<unit>[KMB]?)\s+smpl:\S+.*?\bloss:(?P<loss>[-+0-9.eE]+|nan|inf)")
UNITS = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}


def parse(text: str) -> tuple[list[int], list[float]]:
    points: dict[int, float] = {}
    for m in STEP_LINE.finditer(text.replace("\r", "\n")):
        step = int(round(float(m["step"]) * UNITS[m["unit"]]))
        points[step] = float(m["loss"])
    steps = sorted(points)
    return steps, [points[s] for s in steps]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("logs", nargs="+", type=Path)
    ap.add_argument("-o", "--out", type=Path, help="PNG path (default: <first log>.loss.png next to it)")
    ap.add_argument("--title", default=None)
    ap.add_argument("--linear", action="store_true", help="linear y axis instead of log")
    args = ap.parse_args(argv)

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4), dpi=150)
    plotted = 0
    for log in args.logs:
        steps, loss = parse(log.read_text(errors="replace"))
        if not steps:
            print(f"{log}: no 'step:... loss:...' lines", file=sys.stderr)
            continue
        finite = [x for x in loss if x == x and abs(x) != float("inf")]
        print(f"{log}: {len(steps)} points, step {steps[0]}..{steps[-1]}, "
              f"loss {loss[0]:.4g} -> {loss[-1]:.4g} (min {min(finite):.4g})" if finite else f"{log}: all loss NaN/inf")
        ax.plot(steps, loss, marker="o" if len(steps) <= 30 else None, markersize=3, linewidth=1.5,
                label=log.name.removesuffix(".log"))
        plotted += 1
    if not plotted:
        return 1

    if not args.linear:
        ax.set_yscale("log")
    ax.set_xlabel("training step")
    ax.set_ylabel("loss" + ("" if args.linear else " (log scale)"))
    ax.set_title(args.title or "LeRobot training loss")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(frameon=False)
    fig.tight_layout()
    out = args.out or args.logs[0].with_suffix(".loss.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
