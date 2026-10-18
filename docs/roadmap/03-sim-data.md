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
- **Two disjoint sets.** **A** stays raw in both mixes; **B** is the set Cosmos re-renders. Raw B is
  kept for the controlled ablation (07).

| Set | Per spot | Total target | Use |
|---|---|---|---|
| A | 12 | 108 | raw sim in `main` and `ablation` |
| B | 18 | 162 | Cosmos-transferred in `main`, raw in `ablation` (curation trims to fit 300) |

Attempts ≈ episodes / 0.75. At ~25 s per attempt: A ≈ 1 h, B ≈ 1.5 h on one VM. Run A and B as two
processes if the GPU has headroom (watch `nvidia-smi`), or start B first because Cosmos waits on it.

## Commands

```bash
# smoke (one spot, 3 episodes) -> then 02's replay test
python scripts/collect_grid.py --starter ~/work/so101_sim_pickplace --per-spot 3 --spots B2 --dataset-name sim_smoke
# bulk, after G2
python scripts/collect_grid.py --starter ~/work/so101_sim_pickplace --per-spot 18 --dataset-name sim_B
python scripts/collect_grid.py --starter ~/work/so101_sim_pickplace --per-spot 12 --dataset-name sim_A
# convert each (units + single camera), then to v3 for merging
python scripts/convert_sim_dataset.py --src $DATASETS_DIR/local/sim_A --dst data/sim/A_real_units
```

Keep the v2.1 converted copy of B: Cosmos (04) works on per-episode mp4s, which v2.1 has and v3 does not.

## Acceptance check

- `collect.log` shows per-spot success lines for all 9 spots (the expert's own success check:
  cube on pad, at rest, jaw open, gripper clear; `mdp.cube_placed`).
- Episode count per spot in the dataset: equal within ±1 (count from the log's `cube_b=(x,y)` field).
- 5 random episodes watched at 2× speed: cube visibly in a grid-spot position, pad in its taped place.
- Cosmos Reason later scores these too (05). Sim episodes failing its rule are a signal of an expert bug.

## If it fails

- Expert success < 50 % on some spot → that spot is at the edge of the reachable workspace for the
  scripted IK. Keep what it produces; real teleop (06) gives that spot extra demos.
- Isaac install on `s2t-rtx6000` not done by T+1:30 → do the Transfer smoke (04) on the same GPU while you wait.
