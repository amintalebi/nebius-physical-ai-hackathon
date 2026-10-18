# 06 · Real teleop protocol

**Points:** Accuracy (real data is the only data with the real camera, real lighting and real physics).
**Cap:** 50 real episodes. Plan **45** (5 × 9 spots) and keep 5 in reserve for the weakest spots after the first eval.
**Time box:** T+2:00-4:00 at the station (smoke: 3 episodes at T+0:30).

## Inputs

- Leader/follower calibrated by the organizers (do not recalibrate: [calibration README](../../configs/calibration/README.md))
- `configs/station.yaml` filled in; the station camera's key must be the same as the sim camera key (`front`)

## Protocol

1. **Spot by spot.** `SPOT=A1 NUM=5 ./scripts/record_real.sh`, then A2 … C3. The script appends the spot
   to `data/real/spot_log.csv` and refuses to exceed 50.
2. **Same start pose every time**: the pose the judged trials will start from (02 §2.4). Return to it during reset.
3. **One operator for all 45** if possible. Two operators' styles look like noise to ACT.
4. **Move like the policy should**: direct, one approach, one grasp, place, open, retreat. No pauses
   mid-reach. Aim for 8-15 s per episode (the sim expert takes ~10 s).
5. **Vary what the judges vary**: cube yaw (rotate it 0-45° between takes), exact position within the tape mark (±1 cm).
   Do not vary what judges keep fixed: lamp, camera, pad.
6. **Bad take → re-record it immediately** and note the episode index; Cosmos Reason will flag it too,
   and both together justify the drop.
7. **Don't touch the camera mount or lamp, ever.** If someone bumps it, the overlay check (02 §2.3)
   becomes the first thing to redo.

## Acceptance check

- `data/real/spot_log.csv` shows 5 per spot.
- `lerobot-dataset-viz` (or the Rerun view during recording) on 3 random episodes: camera stream at 30 fps,
  joint traces smooth, gripper closes on the cube.
- `meta/info.json` of the real dataset: features `observation.images.front`, `observation.state` and
  `action` with 6 joints, `fps: 30`, exactly what `validate_manifest.py` expects to match the sim sources.
- Cosmos Reason drop rate on real < 30 % (05).

## If it fails

Arm or teleop flaky → record fewer, cleaner episodes. 30 clean demos spread over 9 spots beat 50 with gaps.
