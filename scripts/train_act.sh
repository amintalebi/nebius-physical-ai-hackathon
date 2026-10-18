#!/bin/bash
# Train ACT on a merged mix, on the Nebius GPU VM. Refuses to start if the manifest breaks a rule.
#   MIX=main     ./scripts/train_act.sh
#   MIX=ablation ./scripts/train_act.sh          # run both at once on a 2-GPU VM: GPU=0 / GPU=1
#   MIX=main SEED=2 OUT_SUFFIX=_s2 ./scripts/train_act.sh   # extra seed for the ensemble
# Flags from lerobot @146d847 configs/train.py, configs/default.py, policies/act/configuration_act.py.
# Both runs MUST use identical settings except the dataset; that is what makes the ablation valid.
set -euo pipefail
cd "$(dirname "$0")/.."
MIX="${MIX:?main|ablation}"
STEPS="${STEPS:-40000}"          # ACT default is 100k; ~300 eps x ~300 frames rarely needs it. Check the loss curve.
BATCH="${BATCH:-32}"
SEED="${SEED:-1000}"
GPU="${GPU:-0}"
OUT="outputs/act_${MIX}${OUT_SUFFIX:-}"

python3 scripts/validate_manifest.py --out "submission/manifest.json"

CUDA_VISIBLE_DEVICES="$GPU" lerobot-train \
  --dataset.repo_id="local/mix_${MIX}" --dataset.root="data/mix/${MIX}" \
  --dataset.image_transforms.enable=true \
  --policy.type=act --policy.device=cuda --policy.push_to_hub=false \
  --policy.chunk_size=100 --policy.n_action_steps=100 \
  --output_dir="$OUT" --job_name="act_${MIX}${OUT_SUFFIX:-}" \
  --steps="$STEPS" --batch_size="$BATCH" --save_freq=10000 --log_freq=200 --seed="$SEED" \
  --wandb.enable="${WANDB:-false}" 2>&1 | tee "logs/train_${MIX}${OUT_SUFFIX:-}.log"
