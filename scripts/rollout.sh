#!/bin/bash
# Run a trained checkpoint on the real arm for one trial (2-min judge cap -> --duration=120).
#   CKPT=outputs/act_main/checkpoints/040000/pretrained_model ./scripts/rollout.sh
#   TE=0.01 CKPT=... ./scripts/rollout.sh     # ACT temporal ensembling (n_action_steps must be 1)
# Flags from lerobot @146d847 src/lerobot/scripts/lerobot_rollout.py and rollout/configs.py.
set -euo pipefail
cd "$(dirname "$0")/.."
eval "$(python3 scripts/station_env.py)"
CKPT="${CKPT:?path to pretrained_model dir}"
DURATION="${DURATION:-120}"
EXTRA=()
if [ -n "${TE:-}" ]; then
  # TODO(verify): overriding policy fields together with --policy.path on the station laptop
  EXTRA+=(--policy.temporal_ensemble_coeff="$TE" --policy.n_action_steps=1)
fi
lerobot-rollout --strategy.type=base \
  --policy.path="$CKPT" ${EXTRA[@]+"${EXTRA[@]}"} \
  --robot.type="$ROBOT_TYPE" --robot.port="$ROBOT_PORT" --robot.id="$ROBOT_ID" \
  --robot.calibration_dir="$ROBOT_CALIB_DIR" --robot.use_degrees="$ROBOT_USE_DEGREES" \
  --robot.cameras="$CAMERAS" \
  --task="$TASK" --duration="$DURATION" --device="${DEVICE:-mps}"
