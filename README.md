# Sim to Table: NVIDIA × Nebius AI Builders Hackathon (Berlin, 18 Oct 2026)

Pick a 30 mm cube from any of 9 taped grid spots and place it on a green pad with an SO-101 arm,
using one ACT policy trained on **Isaac Sim demos + Cosmos-Transfer re-renders + ≤50 real teleop demos**.

**Start here:** [`docs/roadmap/README.md`](docs/roadmap/README.md). It has the scoring map, the hour-by-hour
critical path, and one file per stage, each with an acceptance check that something other than us
confirms (the arm, a metric, a script, or the organizers).

## Layout

```
configs/            station.yaml (the single source of truth for our table), data_mix.yaml, cosmos prompts
configs/calibration/ the organizers' LeRobot calibration JSON for our follower arm (copy it here)
s2t/                tested helpers: sim->real joint units, eval statistics
scripts/            pipeline steps (each has --help and cites the source it was built from)
sim_patches/        patch for the starter repo: spawn on our 9 grid spots, pad + camera pinned
tests/              pytest (run: uv run --with pytest --with numpy --with pyarrow --with pyyaml --with opencv-python-headless pytest)
docs/sources.md     every upstream repo read, pinned commit, and the findings that changed the plan
docs/roadmap/       the plan
```

## Pipeline in one screen

| Step | Where | Command |
|---|---|---|
| Sim demos on the 9 spots | Nebius RTX PRO 6000 / L40S | `python scripts/collect_grid.py --starter <starter> --per-spot 12 --dataset-name sim_A` |
| Sim → real units, 1 camera | VM | `python scripts/convert_sim_dataset.py --src … --dst …` |
| Cosmos Transfer (edge + style frame) | Nebius H100/H200/RTX PRO 6000 | `python scripts/cosmos_transfer_batch.py prepare / run / assemble` |
| Cosmos metrics | VM | `python scripts/cosmos_metrics.py --sim … --cosmos … --real …` |
| Real teleop (≤50) | station laptop | `SPOT=B2 NUM=5 ./scripts/record_real.sh` |
| Cosmos Reason curation | VM (vLLM) | `python scripts/cosmos_reason_score.py score / decide / agree` |
| Curate + merge mixes | VM | `python scripts/build_mixes.py --execute` |
| Rules check + manifest | anywhere | `python scripts/validate_manifest.py` |
| Train main + ablation | Nebius GPU | `MIX=main ./scripts/train_act.sh` / `MIX=ablation …` |
| Real-arm eval | station | `./scripts/rollout.sh` + `python scripts/eval_logger.py log/summary` |
| Submit | anywhere | `BUCKET=s3://… ./scripts/sync_to_nebius.sh` |

Third-party code (starter, LeRobot, Isaac Lab, Cosmos) is not vendored; each runs in its own env on
the machine that needs it. See `docs/roadmap/01-critical-path.md` for which box runs what.
