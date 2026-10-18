# 08 · Training on Nebius

**Points:** Nebius 20 (training on Nebius Cloud), Accuracy via the checkpoint, Cosmos Transfer via the ablation.
**Time box:** smoke 2k steps at T+1:00; main + ablation T+6:00-7:15.

## Runs

| Run | Mix | GPU | Purpose |
|---|---|---|---|
| `act_main` | main | 0 | The submission |
| `act_ablation` | ablation | 1 | Same settings, no Cosmos → measures Cosmos |
| `act_main_s2` | main, seed 2 | 2 | Second member of the ensemble (10); free if a third GPU is idle |

Identical flags for all runs (`scripts/train_act.sh`); only `MIX`, `SEED`, `GPU` change.

```bash
MIX=main     GPU=0 ./scripts/train_act.sh &
MIX=ablation GPU=1 ./scripts/train_act.sh &
MIX=main GPU=2 SEED=2 OUT_SUFFIX=_s2 ./scripts/train_act.sh &
```

## Settings and why

| Setting | Value | Reason |
|---|---|---|
| policy | ACT, resnet18, `chunk_size=100`, `n_action_steps=100` | LeRobot defaults; proven on SO-101 pick-place |
| steps | 40k (default 100k) | ~300 episodes × ~300 frames ≈ 90k frames; batch 32 × 40k ≈ 14 epochs. Smoke run measures steps/s; set steps from the time left. |
| batch | 32 | Faster wall-clock on one H100 than the default 8 |
| image transforms | on | Colour/brightness jitter is cheap extra robustness to the lamp and the sim/Cosmos/real colour mix |
| checkpoints | every 10k | Choose by real-arm eval (09), not by loss |
| seed | 1000 (main, ablation), 2 (s2) | Same seed for the main-vs-ablation pair |

Temporal ensembling (`temporal_ensemble_coeff=0.01`, `n_action_steps=1`) is an **inference-time** choice: no
retraining needed (`TE=0.01 ./scripts/rollout.sh`). Compare it in eval (09).

## Nebius evidence (collect it as you go)

Keep `nebius/usage.md` in the submission, appended during the day:
- `nebius compute instance list` output (VM ids, platform `gpu-h100…`/`gpu-rtx6000`, preset) at creation
- `nvidia-smi` snapshot during training
- `logs/train_*.log` and the loss curves (W&B screenshots if `WANDB=true`, else the log)
- wall-clock per stage (sim collection, Cosmos per segment, training steps/s)
- Object Storage listing of datasets and checkpoints (`aws s3 ls --endpoint-url https://storage.<region>.nebius.cloud …`)

Preemptible VMs are cheaper but can stop; for the main run use a non-preemptible VM or sync checkpoints to
Object Storage every save (`aws s3 sync outputs/ s3://…/outputs`).

## Acceptance check

- Loss of main and ablation both converge (no NaN, steady decline); the curves go in the submission.
- **The smoke checkpoint (T+1:30) moves the real arm** via `rollout.sh`. A checkpoint that loads and drives
  the arm is the technical gate; success rate comes later.
- Checkpoint copied to the station laptop and its sha256 recorded next to the eval log, so eval rows map to a file.

## If it fails

- Out of time → train only `main`; ablation becomes "not run" in the report, not a guess.
- Dataloader-bound (GPU < 50 % busy) → raise `--num_workers`, or `--dataset.image_transforms.backend=gpu`.
