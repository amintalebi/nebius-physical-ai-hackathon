# 03 · Sim data

**Points:** Accuracy (sim covers the spots), required by the rules (main must include sim-derived data),
and the raw material for Cosmos Transfer (04).
**Time box:** smoke T+0:30-1:30; bulk T+2:00-4:00 on `s2t-rtx6000` (~25 s per attempt, ~75 % expert success).

## Inputs

- `s2t-rtx6000` with the starter installed (`nebius/setup_vm.sh`), `env.sh` edited, patch applied (02)
- `configs/station.yaml` filled in (02)

## Design

- **Spawn on the test distribution.** Judges place the cube only on the 9 taped spots. Uniform spawns over
  half the table (the starter default) spend most demos on places the judges never use. We spawn at
  each spot ± 12 mm (tape placement is approximate) with yaw ± 0.8 rad, the pad fixed where it is taped.
- **Equal episodes per spot.** One spot without data is one judged trial lost.
- **Cube size varies: blue in 20/25/30/40 mm.** The event cubes are blue and may be any of **four**
  sizes across judged trials, so the sim must cover **all four** for every spot. `collect_grid.py` loops
  over `geometry.cube_sizes_mm` (`[20, 25, 30, 40]`, `cube_color: blue` in `configs/station.yaml`) and
  writes every (spot × size) into one dataset. Do not oversample one size — the policy must grasp
  all four.
  - **20 mm asset:** the starter ships 25/30/40 mm only. `sim_patches/make_cube_20mm.py <starter>/assets/cube_blocks/usd`
    writes exact 20 mm twins (same 1 mm chamfer, mass 4.4 g fitted from the starter's own 25/30/40 mm
    estimates). Already generated on `s2t-rtx6000`. We collect 20 **and** 25 mm because the small event
    cube's size is unconfirmed.
- **Two disjoint sets.** **A** stays raw in both mixes; **B** is the set Cosmos re-renders. Raw B is
  kept for the controlled ablation (07).

| Set | `--per-spot` (total, split over sizes) | Per size per spot | Total | Use |
|---|---|---|---|---|
| A | 12 | 3 | 108 | raw sim in `main` and `ablation` |
| B | 18 | 4-5 (remainder rotates by spot) | 162 | Cosmos-transferred in `main`, raw in `ablation` (curation trims to fit 300) |

`--per-spot` is the **total per spot**; `collect_grid.py` splits it over the sizes (`s2t/sampling.py`) and prints
the per-size totals before starting. Each (set, size, spot) gets its own `--seed`: the starter defaults to
seed 0, so without it every spot replays the same yaw sequence and set B duplicates set A.

Attempts ≈ episodes / 0.8 (measured 83 % expert success on red 30 mm). One Isaac launch per (size, spot)
costs ~1 min of startup, i.e. 36 launches per set. **Fast path: one process per size in parallel**, each
its own dataset, merged after the v3 conversion (`lerobot-edit-dataset … merge`):

```bash
for s in 20 25 30 40; do
  python scripts/collect_grid.py --starter ~/work/so101_sim_pickplace --per-spot 3 --sizes $s --dataset-name sim_A_$s &
done
```

## Cube-size grasp calibration (do before bulk, once per size)

The starter's scripted grasp is tuned for **30 mm**; `GRASP_POINT_OFFSET` scales its horizontal centre
with `CUBE_SIZE/2`, but the empirical constants (−0.008, +0.0125, 0.005, −0.062) were calibrated on the
30 mm cube. Validate 20/25/40 before spending the episode budget:

- **Smoke per size:** `collect_grid.py --sizes 20 --spots B2 --per-spot 5` (then `25`, `30`, `40`) and watch
  the `collect.log` success lines. **Pass:** ≥ 3/5 episodes per size lift and place the cube
  (`mdp.cube_placed`), not just "touched". If the 30 mm pass rate is high but 20, 25 or 40 is clearly worse,
  re-run the starter's `scripts/calibrate_grasp.py` for that size and update the env cfg before bulk.
- **Watch at 2× speed:** for each size, confirm the grasp visually closes on the cube (not in front of
  or through it). A consistent miss on one size = a grasp-offset or waypoint issue for that size.
- **Record per-size success** next to the dataset; curation (05) will treat a low per-size pass rate as
  an expert issue, not sim aliasing.

## Commands

```bash
# smoke (one spot, all 4 sizes) -> boot check + per-size grasp validation above
python scripts/collect_grid.py --starter ~/work/so101_sim_pickplace --per-spot 3 --spots B2 --dataset-name sim_smoke
# bulk, after gate: collects every spot x every size (from station.yaml cube_sizes_mm)
python scripts/collect_grid.py --starter ~/work/so101_sim_pickplace --per-spot 18 --dataset-name sim_B
python scripts/collect_grid.py --starter ~/work/so101_sim_pickplace --per-spot 12 --dataset-name sim_A
# narrow to one size (e.g. re-sampling a failed size)
python scripts/collect_grid.py --starter ~/work/so101_sim_pickplace --per-spot 3 --sizes 40 --dataset-name sim_A_40 --resume
# convert each (units + single camera), then to v3 for merging
python scripts/convert_sim_dataset.py --src $DATASETS_DIR/local/sim_A --dst data/sim/A_real_units
```

Keep the v2.1 converted copy of B: Cosmos (04) works on per-episode mp4s, which v2.1 has and v3 does not.

## Acceptance check

- `collect.log` shows per-spot success lines for all 9 spots (the expert's own success check:
  cube on pad, at rest, jaw open, gripper clear; `mdp.cube_placed`).
- Episode count per spot in the dataset: equal within ±1 (count from the log's `cube_b=(x,y)` field).
  `cube_b` is in the robot's URDF base frame, which the starter seats rotated 90° from the scene frame that
  `configs/station.yaml` uses: `cube_b = (y, -x)` of the station coordinates. Smoke run at B2 (0.215, 0.075) logged
  `cube_b ≈ (0.075, -0.215) ± 12 mm`, as expected.

**Smoke result (2026-10-18, `s2t-rtx6000`):** 3/3 expert successes at B2, ~20 s per attempt (faster than the
~25 s the starter README quotes), 915 frames, v2.1 with `front` + `wrist` 640x480 @ 30 fps. Uploaded to
`s3://s2t-group02-a66c17/data/sim/sim_smoke_v21`.
- Episode count per size (20/25/30/40) within each spot: roughly balanced; no size undersampled and no
  whole size missing from a spot.
- 5 random episodes watched at 2× speed: cube visibly in a grid-spot position, pad in place, and the
  grasp closes correctly for that episode's cube size.
- Cosmos Reason later scores these too (05). Sim episodes failing its rule are a signal of an expert bug.

## If it fails

- Expert success < 50 % on some spot → that spot is at the edge of the reachable workspace for the
  scripted IK. Keep what it produces; real teleop (06) gives that spot extra demos.
- Isaac install on `s2t-rtx6000` not done by T+1:30 → do the Transfer smoke (04) on the same GPU while you wait.
