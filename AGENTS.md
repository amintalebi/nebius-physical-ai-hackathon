# AGENTS.md

Sim→Real pick-and-place hackathon (NVIDIA × Nebius, 30 mm cube on a 9-spot grid, SO-101 arm).
This repo is the **plan + pipeline glue + tested helpers** only. It is NOT a Python app: the
heavy frameworks it orchestrates (LeRobot, Isaac Sim, Cosmos) are never installed or imported here.
Each runs in its own env on the machine that needs it. See `docs/roadmap/README.md` (read it first)
and `docs/sources.md` (pinned upstream commits).

## Mental model

- `configs/station.yaml` is the **single source of truth** for our physical station. Many values are
  `MEASURE` placeholders to fill in on arrival; scripts read this file (via `scripts/station_env.py`,
  which prints shell exports) rather than hardcoding.
- `scripts/*.py` are the pipeline steps. Each has `--help` and its docstring cites the upstream repo +
  pinned commit it was built from. Docs are prose; treat scripts and `s2t/` as the executable truth.
- `s2t/` is a small importable package (`units.py`, `stats.py`) with no third-party deps beyond numpy.
- Data lives in `data/`, `outputs/`, `logos/`, `work/`, `submission/` — all **gitignored**; big datasets
  and checkpoints go to Nebius Object Storage, not git.

## The one thing that bit everyone: sim vs real joint units

Sim episodes are written in starter "USD-limit [-100,100]" units; the real arm reports calibrated
**degrees** (LeRobot `use_degrees=True`). The numbers differ for the same physical pose, so raw sim
actions would crash the arm and mixing units teaches contradictory targets. Handled by
`s2t/units.py` + `scripts/convert_sim_dataset.py`, verified on hardware by the open-loop replay test
(`docs/roadmap/02`). Related dataset quirks enforced in conversion:
- Keep only the `front` camera, named exactly like the station camera key (`configs/station.yaml`).
  The sim also records `wrist`; merging needs identical features across sources.
- Starter writes **LeRobot v2.1**; current LeRobot reads/merges **v3.0**. Convert v2.1→v3.0 in place
  with LeRobot's `convert_dataset_v21_to_v30` before any `build_mixes.py` / merge.

## Running tests

Dependencies are NOT in the project env. Run with `uv`, passing the runtime deps explicitly:

```bash
uv run --with pytest --with numpy --with pyarrow --with pyyaml --with opencv-python-headless pytest
```

- `pyproject.toml` `[tool.pytest]` sets `pythonpath=[".]` and `testpaths=["tests"]`.
- Test files import pipeline code straight from `scripts/` via a `sys.path.insert(..., "scripts")`
  shim (see `tests/test_manifest.py`). Don't move/repackage scripts into a package; that breaks them.
- `convert_sim_dataset.py` needs opencv (not a project dep) — that's why the `uv` command carries
  `opencv-python-headless`.

## Conventions in scripts and shell wrappers

- Shell wrappers (`record_real.sh`, `train_act.sh`, `rollout.sh`, `sync_to_nebius.sh`) configure via
  **environment variables, not args** (e.g. `NUM=5 SPOT=B2`), `cd` to repo root, and source `station_env.py`.
  `train_act.sh` refuses to train unless `validate_manifest.py` passes. Many are Mac/Linux bash with
  `set -euo pipefail`.
- All paths in scripts are relative to the repo root, resolved via `REPO = Path(__file__).parents[1]` —
  always invoke them from the repo root.
- Dataset mixes and caps (real ≤ 50, total ≤ 300) are declared in `configs/data_mix.yaml` and enforced
  by `validate_manifest.py`, which recounts from each dataset's `meta/info.json` (not the config).
  `build_mixes.py apply curation` drops; Cosmos episodes and their raw-sim twins are ALWAYS dropped
  together (the controlled ablation). Re-running `build_mixes.py` is safe — mixes rebuild from `raw:`.
- No CI, no pre-commit, no formatter config. Keep scripts' docstring-cite-source convention when editing.