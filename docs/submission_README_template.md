# Sim to Table · <team> · submission README (template)

Copy to `submission/README.md`, fill every `<TBD>`, delete rows we did not run (say "not run", never guess).
Every number links to the file in this folder that produced it. Paths are relative to `s3://s2t-group02-a66c17/<team>/`.

**What we built:** an ACT policy for SO-101 cube pick-and-place, trained **sim-first** (no arm access until a sim
policy worked), on **one Nebius GPU VM** (RTX PRO 6000 Blackwell, `gpu-rtx6000-a`, uk-south2) that ran Isaac Sim
data collection, Cosmos Transfer 2.5 augmentation and LeRobot 0.6.2 ACT training. Episode curation used
**Cosmos3-Super-Reasoner on a Nebius Token Factory dedicated endpoint**.

| Main checkpoint | `checkpoints/main/pretrained_model` · sha256 `<TBD>` · ACT (resnet18, chunk 100), `<TBD>` steps, batch `<TBD>`, LeRobot 0.6.2 |
|---|---|
| Data (`manifest.json`) | sim `<TBD>` + Cosmos `<TBD>` + real `<TBD>` = `<TBD>` episodes, after curation |
| Run it | `<TBD: rollout command for the judges' station>` |

## Rubric → claim → evidence

| Rubric line (pts) | Claim | Evidence file(s) |
|---|---|---|
| **Accuracy (30)** | Pre-eval of the main checkpoint: sim `<TBD>`/`<TBD>` over the 9 grid spots; real arm `<TBD>`/18 blind trials, 95 % CI [`<TBD>`, `<TBD>`] | `eval/sim_eval_summary.md` + `eval/sim_eval_*.jsonl` + `eval/videos/`; `eval/trials.csv`, `eval/eval_summary.md` (per-spot matrix) |
| **Cosmos Reason (10)** | Every sim, Cosmos and real episode scored by Cosmos3-Super-Reasoner (Token Factory dedicated endpoint, ~`<TBD>` s/episode). **Decision:** keep iff `task_success and not visual_defect and motion_quality >= 3`; dropped sim `<TBD>`, Cosmos `<TBD>`, real `<TBD>`; agreement with our hand labels κ = `<TBD>` | `curation/reason_*.jsonl` (raw JSON per episode), `curation/decisions.json` (rule + per-source drops), `curation/agreement.json`, `curation/hand_labels.csv` |
| **Cosmos Transfer (10)** | Cosmos Transfer 2.5 (edge control w=1.0, distilled, style frame from the station camera) restyles `<TBD>` sim episodes toward the real look without moving the arm/cube/pad: edge F1 sim→Cosmos `<TBD>`; look gap to real frames `<TBD>` → `<TBD>`. Ablation without Cosmos: `<TBD>` vs `<TBD>` | `cosmos/specs/*.jsonl` (exact settings), `cosmos/metrics.json`, `cosmos/side_by_side/*.mp4`, `cosmos/prompts.txt`; ablation rows in `eval/eval_summary.md` |
| **Nebius (20)** | All training on Nebius Cloud: VM `computeinstance-e05kmxe3mvhpg3waqf` (`gpu-rtx6000-a` / `1gpu-24vcpu-218gb`, 1x RTX PRO 6000 96 GB, uk-south2) ran sim collection, Cosmos Transfer and ACT training (`<TBD>` steps/s, `<TBD>` min for main); datasets, checkpoints and logs live in this bucket | `nebius/usage.md` (VM, bucket, wall-clock per stage), `nebius/evidence/<ts>/` (nvidia-smi, pip lists, git commits, log summaries), `nebius/loss_curves/*.png`, `nebius/logs/train_*.log`, `checkpoints/*/sha256.txt` |
| **Technical (15)** | The sim-trained policy runs on the real SO-101: `<TBD>` real trials logged; joint units verified by open-loop replay of a sim episode (`use_degrees=false`) | `eval/videos/*.mp4` (rollouts), `eval/trials.csv`, `alignment/` (replay video + notes, overlay.png + edge F1) |
| **Creativity (15)** | Ensemble: 2 ACT actors (main + seed 2 / temporal ensembling) + Cosmos Reason as verifier that triggers a retry within the 2-min cap: `<TBD>`/9 vs single checkpoint `<TBD>`/9 | `ensemble/README.md` (design), `eval/watchdog.jsonl` (every attempt + verdict), ensemble rows in `eval/eval_summary.md` |

## Pipeline (one line each)

1. **Sim data:** Isaac Sim 6.1 + Isaac Lab 3.0, starter SO-101 scene = judging station; scripted expert over a 3x3 grid
   of cube spots (sets A and B, expert success `<TBD>` %); LeRobot v2.1 → v3.0.
2. **Cosmos Transfer 2.5** on set B (edge control) → `<TBD>` restyled episodes, frame count unchanged.
3. **Cosmos Reason curation** with the rule above, applied to every source before mixing.
4. **ACT** (LeRobot 0.6.2) on the curated mix, main + no-Cosmos ablation trained concurrently on the one GPU.
5. **Eval:** closed-loop sim eval on all 9 spots, then blind real-arm trials; checkpoint chosen by eval, not loss.

## Honest limits

- `<TBD>`: e.g. real-arm data count, spots with low success, what was not run (ablation / ensemble).
