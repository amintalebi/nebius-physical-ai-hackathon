# 02 · Station ↔ sim alignment

**Points:** Accuracy (30) and Technical (15) depend on it. If this stage is wrong, every sim and
Cosmos episode teaches the wrong action for the image, and more data makes the policy worse.
**Time box:** T+0:00-2:00, mostly in parallel with the smoke test.

Cosmos can change how pixels *look*. It cannot fix a camera in the wrong place, a cube in the wrong
spot, or an action in the wrong units. Those three are fixed here, by measurement.

## Inputs

- The organizers' calibration file for our follower → `configs/calibration/<robot.id>.json`
- Tape measure, a phone camera, one frame from the station camera
- The starter checkout on `s2t-rtx6000` with `sim_patches/s2t_station.patch` applied:
  `cd <starter> && git apply <this repo>/sim_patches/s2t_station.patch`

## 2.1 Measure the table into `configs/station.yaml`

Frame: robot base origin, +X straight out from the base, +Y to the robot's left, metres. This is the
sim env frame (starter `pickplace_env_cfg.py`: base at origin, arm faces +X).

- 9 grid spot centres → `geometry.grid_spots_xy` (name them A1…C3 row-major *as seen from the camera*,
  and write the naming on a sticky note at the station so judges' spot names map to ours).
- Pad centre and size → `pad_center_xy`, `pad_size_m`. Cube size and colour → `cube_size_m`, `cube_color`.
- Camera position and the table point it looks at → `front_cam_pos`, `front_cam_look_at`.

Check reachability: every spot must be inside the starter's tested workspace
(x 0.16-0.27, y 0.02-0.13) or close to it. If a spot is far outside, run 3 expert attempts there
first (`collect_grid.py --spots C3 --per-spot 3`) and watch the success line in the log; the
expert succeeds ~75 % in its native range and may do much worse outside.

## 2.2 Joint units: the critical fix

Sim stores joints mapped from the **USD joint limits** to [-100, 100]. The real arm (LeRobot
`use_degrees=True`, the default) reports `(raw − mid(calibrated range)) · 360/4095` degrees. These are
different numbers for the same pose. `s2t/units.py` converts, assuming the `so101_new_calib` USD zero
equals the LeRobot homing pose (tick 2047). That assumption is checked on hardware below, not trusted.

```bash
python scripts/convert_sim_dataset.py --src data/sim/smoke --dst data/sim/smoke_real_units
python -m lerobot.scripts.convert_dataset_v21_to_v30 --repo-id=local/smoke --root=data/sim/smoke_real_units --push-to-hub=false
```

### Acceptance check: open-loop replay on the real arm

The arm itself tells us if the units are right. Replay a converted sim episode's actions with the
cube placed where the sim cube was:

```bash
# 1. with NO cube, watch for table collisions; hand on the power switch.
#    max_relative_target clips per-step jumps (the first frame moves the arm from rest to the sim start pose)
lerobot-replay --robot.type=so101_follower --robot.port=$ROBOT_PORT --robot.id=$ROBOT_ID \
  --robot.calibration_dir=configs/calibration --robot.max_relative_target=10 \
  --dataset.repo_id=local/smoke --dataset.root=data/sim/smoke_real_units --dataset.episode=0
# 2. then with the cube on the same spot, yaw matched to the sim episode (collect log prints cube_b and yaw)
```

| Observation | Meaning | Fix |
|---|---|---|
| Grasps and lifts the cube, ≥2 of 3 replays, on a centre spot **and** a corner spot | Units right | Done. Write "replay: pass" with a video in `reports/` |
| One joint moves the wrong way | Sign flip | `joint_map.signs.<joint>: -1`, reconvert |
| Consistent miss by a fixed amount (too high, too far left) | Homing or offset | Tune `joint_map.offsets_deg` in small steps (2-3°), reconvert, replay |
| Gripper never closes / closes too early | Gripper range mismatch | Compare sim gripper column vs a real episode's; adjust `offsets_deg.gripper` |
| Wild motion | Wrong calibration file or `use_degrees` mismatch | Check `robot.id`, the file, and `use_degrees` in a real recording's `info.json` |

Open-loop replay ignores the camera, so this test isolates units and geometry from vision.
Also compare value ranges: `observation.state` min/max of a real episode next to a converted sim
episode should overlap for every joint.

## 2.3 Camera pose

```bash
# sim frame at reset (starter): $ISAACLAB_PY scripts/view_env.py  -> logs/view/*.png
python scripts/overlay_check.py --sim logs/view/front.png --real station_front.jpg --out reports/overlay.png
```

Put the real arm in the sim reset pose for the photo (replay frame 0 of any sim episode and stop).
Iterate `front_cam_pos` / `front_cam_look_at` until the arm base, table edge and pad outline coincide.
**Acceptance:** overlay image in `reports/` where the outlines visibly match, plus the edge F1
printed by the script (record it; higher is better, aim for the value to stop improving).
Field of view: the starter's front camera is `focal_length=18, horizontal_aperture=20.955`. If the
real camera is clearly wider or narrower, change the focal length in the env cfg as well.

## 2.4 Start pose

Sim episodes start with the gripper hovering, pointing down (`SO101_INIT_JOINT_POS`). Judged trials start
wherever the arm is when the policy launches (ask: [open-questions](open-questions.md)). Real teleop
demos must start from **the same pose the judged trials start from**, so the real data covers the part
of the motion the sim does not show.

## If it fails

Replay never succeeds after 30 min → train `main` with Cosmos/sim data anyway (rules require it), but
cut sim to the minimum and lean on real data. Record the failed replay in the report. An honest
negative result about sim-to-real units is still competent engineering.
