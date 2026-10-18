# Sim to Table: NVIDIA × Nebius AI Builders Hackathon (Berlin, 18 Oct 2026) — team group02

## Highlights

**▶ Video:** [https://drive.google.com/file/d/1CR6DgpyHQQngK3mWgzbhxxhQz2_zHT_I/view?usp=sharing](https://drive.google.com/file/d/1CR6DgpyHQQngK3mWgzbhxxhQz2_zHT_I/view?usp=sharing)

- **What:** an SO-101 arm picks up a blue cube and places it on a target square. One ACT policy, trained on
  **Isaac Sim demos + NVIDIA Cosmos re-renders + real teleop demos**, entirely on **Nebius AI Cloud**.
- **Result:** our submitted model **v06 picks and places the cube on the real robot** (it retries after a miss;
  video `eval/real_videos/v06_success_late.mp4` in the submission). In simulation our policy succeeds **56–70 %**
  over 9 spots × 3 cube sizes, including a cube size it never trained on.
- **Submission:** Nebius Object Storage **`s3://s2t-group02-a66c17/submission/`** (`README.md` = claim → evidence,
  `sim_to_table_2min.mp4` = 2-minute overview, `checkpoints/main` = v06). Plain-language summary: [`docs/what_we_did.md`](docs/what_we_did.md).
- **Data:** 156 sim demos · 28 Cosmos-repainted episodes · ~210 videos reviewed by Cosmos Reason · 48 real demos (45 kept).
  The submitted model trained on **124 episodes = 72 sim + 22 Cosmos + 30 real**.
- **How:** (1) Isaac Sim scripted expert on the 9 grid spots → (2) **Cosmos Transfer 2.5** repaints sim video toward our
  station's look (styled on a real camera frame) → (3) **Cosmos Reason** (Cosmos3-Super-Reasoner) scores every episode
  → (4) real teleop demos (front + side cameras) → ACT trained and fine-tuned in rounds on one **Nebius RTX PRO 6000**.
- **Learned:** Cosmos changes how the scene *looks*, not where the *camera* is. Our real camera sits lower and closer
  than the sim camera, so real demos made the biggest difference. **Next step:** move the sim camera to the real pose
  and recolour the sim table, then recollect.
- **Real station tuning:** cameras re-aimed (front) and added (side), extra lighting, a plain background behind the
  robot. The arm's calibration was read back from the motors, never reset.

## Run the submitted model on the real arm

LeRobot @146d847 (0.6.2) on the station laptop, both arms with `use_degrees=false`, front camera only:
```bash
source ../lerobot/.venv/bin/activate && eval "$(python3 scripts/station_env.py)"
lerobot-rollout --strategy.type=base --policy.path=models/v06_final_main_r2 \
  --robot.type=$ROBOT_TYPE --robot.port=$ROBOT_PORT --robot.id=$ROBOT_ID --robot.calibration_dir=$ROBOT_CALIB_DIR \
  --robot.use_degrees=$ROBOT_USE_DEGREES --robot.max_relative_target=15 \
  --robot.cameras="{front: {type: opencv, index_or_path: 1, width: 640, height: 480, fps: 30, warmup_s: 3}}" \
  --task="$TASK" --duration=120 --device=mps
```
`models/` is not in git: download a version from `s3://s2t-group02-a66c17/submission/models/<version>/`.

## Results in detail

| Model | Data | Sim eval (27 trials) | Real arm |
|---|---|---|---|
| v01_sim_frontwrist_8k | sim A (72), front + wrist cameras | 19/27 | — (station has no wrist camera) |
| v02_sim_front_8k | sim A, front only | 16/27 | — |
| v03_sim_main_front_8k | sim A + 22 Cosmos | 17/27 | — |
| v03b_sim_ablation_front_8k | sim A + the same 22 raw (Cosmos ablation twin) | 18/27 | — |
| v04 / v05 (final_main r1, 4k / 8k) | sim main + 16 real | — | near miss |
| **v06 (final_main r2) — submitted** | sim main + 30 real | — | **success (after retries)** |
| v07 (final_main r3) | sim main + 45 real | — | not better than v06 |

- **Cosmos ablation:** same trajectories, raw vs Cosmos pixels, identical training → 17/27 vs 18/27 *in sim* (expected:
  the sim eval renders sim pixels; the effect of Cosmos is a real-world question).
- **Cosmos Reason reliability:** on a negative control (6 good vs 10 deliberately broken clips) it kept 7 of 10 bad ones
  (κ 0.24); vs our hand labels on real demos κ 0.30. Used as a second opinion; real drops (episodes 1, 9, 23) decided by hand.
- **Cosmos Transfer:** distilled edge model, ~46 s per 93-frame segment on one RTX PRO 6000, ~43 GB; frame count and
  geometry preserved; known failure: invented objects in empty table regions.

## Where things are

| Path | What |
|---|---|
| `docs/what_we_did.md` | plain-language summary (also as PDF) |
| `docs/roadmap/` | the original plan: scoring map, critical path, one file per stage |
| `docs/sources.md` | every upstream repo, pinned commit, and the findings that changed the plan |
| `configs/station.yaml` | the real station: ports, `use_degrees=false`, front + side cameras, grid spots, cube sizes |
| `configs/calibration/` | follower (organizers' calibration, read back from the motors) and leader calibration |
| `scripts/` | pipeline steps; `scripts/vm/` = the training / Cosmos / registry scripts exactly as run on the VM |
| `scripts/read_calibration.py`, `compare_arms.py`, `camera_align.py` | real-station tools (read calibration, check leader vs follower, align a camera to the sim view) |
| `scripts/record_real.sh` | teleop recording (`SPOT=… NUM=…` or `SPOTS="B1 B2 …"`, 45 s episodes) |
| `scripts/act_server.py`, `eval_act_in_sim.py` | closed-loop ACT evaluation in Isaac Sim, per spot and cube size |
| `scripts/cosmos_transfer_batch.py`, `cosmos_reason_score.py`, `reason_negative_control.py` | Cosmos Transfer batches; Cosmos Reason scoring, decision and reliability test |
| `sim_patches/` | patches for the starter repo (grid spawn + pinned pad/camera; Isaac Lab release/3.0.0 compat; small-cube grasp) |
| `nebius/usage.md`, `scripts/nebius_s3.py`, `scripts/collect_evidence.sh` | Nebius evidence log, Object Storage helper, evidence snapshots |

## Infrastructure

- **Nebius VM** `s2t-rtx6000`: `gpu-rtx6000-a` / `1gpu-24vcpu-218gb`, uk-south2, Ubuntu 24.04 + CUDA 13.
  Environments: Isaac Sim 6.1 + Isaac Lab release/3.0.0, LeRobot 0.6.2, Cosmos Transfer 2.5 (cu130).
- **Object Storage** bucket `s2t-group02-a66c17` (keys from SecretStash `hackathon-object-storage`): data, 7 versioned
  models (`submission/models/registry.jsonl`), evidence.
- **Token Factory** dedicated endpoint for Cosmos3-Super-Reasoner.
- Third-party code (starter, LeRobot, Isaac Lab, Cosmos) is not vendored; each runs in its own env on the machine that needs it.
- Tests: `uv run --with pytest --with numpy --with pyarrow --with pyyaml --with opencv-python-headless pytest`.
