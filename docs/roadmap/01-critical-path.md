# 01 · Critical path

**Points:** all of them. This file is the schedule; the stage files are the how.
**Assumption:** ~9 working hours before the cutoff (confirm exact cutoff: [open-questions](open-questions.md)).
Times are T+hours from start. Three people: **R** (robot/station), **S** (sim + Cosmos), **T** (training + Nebius + submission).

## Machines

| Box | GPU | Runs | Why this one |
|---|---|---|---|
| VM-sim | 1× RTX PRO 6000 (`gpu-rtx6000`, 96 GB, RT cores) or L40S (`gpu-l40s-d`) | Isaac Sim collection | Isaac Sim needs RT cores; H100/H200 cannot render it (starter README) |
| VM-gpu | 2-8× H100/H200 (or the RTX PRO 6000 box once collection is done) | Cosmos Transfer, Cosmos Reason (vLLM), ACT training | Transfer 2B needs 65.4 GB; parallel GPUs = parallel episodes |
| Station laptop | none needed | teleop, rollout, eval | ACT-resnet18 runs on CPU/MPS |

If quota allows only one VM: one RTX PRO 6000 does everything in sequence (sim → Transfer → train), and
the Cosmos episode count drops (see 04, budget formula).

## Timeline

| T+ | R (station) | S (sim + Cosmos) | T (train + Nebius) | Gate |
|---|---|---|---|---|
| 0:00-0:30 | Ask the [open questions](open-questions.md). Copy the calibration JSON. Measure grid spots, pad, camera pose → `configs/station.yaml` | Create VM-sim, run `nebius/setup_vm.sh` from the starter (long install, start it first) | Create VM-gpu + bucket. Install LeRobot. Start a `nebius/usage.md` log | — |
| 0:30-2:00 | **Smoke test**: record 3 real episodes, push to VM-gpu | Smoke: `NUM_EPISODES=3` on 1 spot, convert units, copy to VM-gpu | **Smoke**: merge 3 real + 3 sim, train 2k steps, copy checkpoint to the laptop, `rollout.sh` runs on the arm (moving at all, not succeeding) | **G1: end-to-end pipe works**. If not, fix this before anything else |
| 1:00-2:00 | **Open-loop replay test** of a converted sim episode on the real arm (02) | Overlay check, adjust sim camera (02) | Cosmos Transfer smoke on 1 episode, measure s/segment (04) | **G2: replay picks the cube** → units trusted |
| 2:00-4:00 | Teleop 45 demos, 5 per spot (06) | `collect_grid.py`: set A (12/spot) and set B (18/spot) | Start vLLM Reasoner; score real episodes as they land (05). Hand-label 20 | — |
| 3:00-5:30 | Hand-label Cosmos samples (visual QA) | Cosmos Transfer on set B (04), then metrics | Score sim A, sim B, Cosmos B. `decide`. `agree` | **G3: Reason agreement κ ≥ 0.6** or tighten the rule |
| 5:30-6:00 | — | — | Apply drops, convert v2.1→v3, merge `main` + `ablation`, `validate_manifest.py` | **G4: manifest passes** |
| 6:00-7:15 | Station free: re-record weakest spots if any slots are left | Ensemble prep (10) | Train main + ablation in parallel (2 GPUs) + 1 extra seed of main | — |
| 7:15-8:30 | **Eval**: ablation 9 trials, main 18 blind trials, ensemble 9 (09/10) | | Upload as results land | **G5: choose the checkpoint** (09 rule) |
| 8:30-9:00 | Freeze. Rollout command card for the judges | | `sync_to_nebius.sh`, verify the listing (11) | **G6: list-back shows everything** |

## Rules that keep the day on track

- **Nothing scales before its gate.** No 100-episode collection before G2. A unit bug found at T+6
  wastes every sim and Cosmos episode.
- **Station time is the scarcest resource.** One arm, shared by teleop, replay and eval. R owns its
  queue; sim and training never block on it.
- **Every long job writes its log to disk and its outputs to Object Storage as it goes** (preemptible
  VMs, laptop sleep). Re-running is cheap; reconstructing evidence is not.
