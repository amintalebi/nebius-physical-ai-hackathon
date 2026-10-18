#!/bin/bash
# Record real teleop demos at the station (laptop next to the arm). Cap: 50 episodes total.
#   NUM=5 SPOT=B2 ./scripts/record_real.sh          # 5 demos with the cube on spot B2
# Record spot by spot (5-6 per spot) so the 9 grid spots are covered evenly; the spot is written
# to data/real/spot_log.csv so per-spot counts can be checked later.
# Flags from lerobot @146d847 src/lerobot/scripts/lerobot_record.py and configs/dataset.py.
set -euo pipefail
cd "$(dirname "$0")/.."
eval "$(python3 scripts/station_env.py)"
NUM="${NUM:-5}"
SPOT="${SPOT:?set SPOT=A1..C3}"
ROOT="${ROOT:-data/real/station_v3}"
RESUME=false; [ -d "$ROOT/meta" ] && RESUME=true

before=$( [ -f "$ROOT/meta/info.json" ] && python3 -c "import json;print(json.load(open('$ROOT/meta/info.json'))['total_episodes'])" || echo 0 )
if [ $((before + NUM)) -gt 50 ]; then echo "would exceed the 50 real-episode cap ($before + $NUM)"; exit 1; fi

lerobot-record \
  --robot.type="$ROBOT_TYPE" --robot.port="$ROBOT_PORT" --robot.id="$ROBOT_ID" \
  --robot.calibration_dir="$ROBOT_CALIB_DIR" --robot.use_degrees="$ROBOT_USE_DEGREES" \
  --robot.cameras="$CAMERAS" \
  --teleop.type="$TELEOP_TYPE" --teleop.port="$TELEOP_PORT" --teleop.id="$TELEOP_ID" \
  --teleop.calibration_dir="$ROBOT_CALIB_DIR" --teleop.use_degrees="$TELEOP_USE_DEGREES" \
  --dataset.repo_id=local/station --dataset.root="$ROOT" --dataset.push_to_hub=false \
  --dataset.single_task="$TASK" --dataset.num_episodes="$NUM" \
  --dataset.episode_time_s="${EP_TIME:-45}" --dataset.reset_time_s="${RESET_TIME:-15}" \
  --resume="$RESUME" --display_data=true

after=$(python3 -c "import json;print(json.load(open('$ROOT/meta/info.json'))['total_episodes'])")
mkdir -p data/real
for ((e=before; e<after; e++)); do echo "$e,$SPOT" >> data/real/spot_log.csv; done
echo "real episodes: $after / 50 (spot log: data/real/spot_log.csv)"
