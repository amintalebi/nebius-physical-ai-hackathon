# Sources read (and what each one decided)

Everything in `docs/roadmap/` traces back to one of these. Commits are pinned; if a tool behaves
differently on the day, check whether its version moved before changing the plan.

| Source | Commit / version | What we took from it |
|---|---|---|
| [ddiddi/so101-sim-pickplace-gr00t](https://github.com/ddiddi/so101-sim-pickplace-gr00t) (starter) | `52b23a9` (2026-10-07) | Isaac Sim 6.1 / Isaac Lab 3.0 env, scripted expert, LeRobot **v2.1** writer, `front`+`wrist` cameras 640x480 @ 30 fps, cube spawns anywhere in x 0.16-0.27 / y 0.02-0.13 with the pad random on the other side, joint units from USD limits, expert succeeds ~75 % and ~25 s wall-clock per attempt, **Isaac Sim needs RT cores (L40S / RTX PRO 6000, not H100/H200)** |
| [huggingface/lerobot](https://github.com/huggingface/lerobot) | `146d847` (2026-10-16) | Dataset **v3.0**; `SOFollowerConfig.use_degrees=True` default; `_normalize()` math; calibration path `$HF_LEROBOT_CALIBRATION/robots/<robot>/<id>.json`; CLIs `lerobot-record`, `lerobot-rollout` (deployment moved out of `record`), `lerobot-replay`, `lerobot-edit-dataset` (`merge`, `delete_episodes`, `remove_feature`, `recompute_stats`), `convert_dataset_v21_to_v30.py`; ACT defaults `chunk_size=100`, `n_action_steps=100`, `temporal_ensemble_coeff=None`, `kl_weight=10`, `lr=1e-5`; train defaults `steps=100k`, `batch_size=8` |
| [nvidia-cosmos/cosmos-transfer2.5](https://github.com/nvidia-cosmos/cosmos-transfer2.5) | `2ff49d0` (2026-06-07) | JSON spec (`video_path`, `prompt`, `edge.control_weight`, `edge.preset_edge_threshold`, `guidance`, `seed`, `num_steps`), **`image_context_path` = style reference image**, 93-frame chunks, `keep_input_resolution=True`, batch = many specs in one `-i` file (model loads once), outputs `<output_dir>/<name>.mp4`; 2B needs **65.4 GB VRAM**; distilled edge `--model=edge/distilled`, 4 steps, "strictly 93 frames", ~65 s (H100 NVL, 1 GPU) vs ~500 s for the base model per chunk. Repo now in maintenance; Cosmos 3 is the successor. |
| [NVIDIA/Cosmos](https://github.com/NVIDIA/Cosmos) (Cosmos 3) | `6e2c69a` (2026-10-16) | Reasoner = Cosmos3-Nano/Super/Edge; vLLM OpenAI-compatible server; `video_url` before text; `media_io_kwargs.video.fps=4`; reasoning via `<think>` format; sampling `temperature=0.6, top_p=0.95` with reasoning; Nano reasoner ~16-17 GB with vLLM |
| [nebius/nebius-physical-ai](https://github.com/nebius/nebius-physical-ai) | `8195442` (2026-10-18) | GPU platform/preset names (01); Object Storage endpoint and service-account access keys (11, `scripts/nebius_s3.py` adapted from `research/lerobot-deploy/s3_sync.py`, Apache-2.0); **Token Factory retired `nvidia/Cosmos3-Super-Reasoner` on 2026-08-31** (05); its Cosmos3-Nano vLLM serve is `--omni` video generation, not the reasoner; Cosmos Transfer 2.5 defaults guidance 3.0 / edge weight 1.0 match ours; no style-image support there (we keep `image_context_path` from upstream). Not adopted: `npa` workflows / SkyPilot / Kubernetes, LeIsaac, PAIDF, the Franka RL Sim2Real engine. |
| [dariolaportanebius/nebius-starter-skill](https://github.com/dariolaportanebius/nebius-starter-skill) (event participant guide) | `81769dd` (2026-10-18) | Region **uk-south2**; team limits (1 GPU `gpu-rtx6000-a` / `1gpu-24vcpu-218gb`, 3 VMs, 500 GiB disk, 1 public IP, 1 bucket of 200 GiB); Object Storage keys pre-made in SecretStash `hackathon-object-storage`; uk-south2 public images in `project-e05public-images` (only CUDA family: `ubuntu24.04-cuda13.0`) |
| Hackathon brief (pasted) | 2026-10-18 | Scoring (30 accuracy / 20 Cosmos / 20 Nebius / 15 technical / 15 creativity), data caps, 9-spot grid with hidden fixed order, 2-min cap, success definition, Object Storage submission |

## Findings that changed the plan

1. **Unit mismatch (critical).** Sim data is in "USD-limit [-100,100]" units; the real arm reports
   calibrated degrees. Unconverted sim actions would send the real arm to wrong poses, and mixing them
   with real data teaches contradictory targets for the same image. Fix: `s2t/units.py` +
   `scripts/convert_sim_dataset.py`, verified on hardware by the open-loop replay test (roadmap 02).
2. **Camera mismatch.** Sim has `front`+`wrist`; the station has one fixed camera. `merge` requires
   identical features. Fix: keep only `front`, named exactly like the station camera key.
3. **Format mismatch.** Starter writes v2.1, LeRobot reads/merges v3.0. Fix: LeRobot's converter.
4. **Spawn distribution mismatch.** Starter spawns the cube uniformly over half the table and moves
   the pad every episode; the judges use 9 taped spots and a fixed pad. Fix: `sim_patches/s2t_station.patch`
   + `scripts/collect_grid.py` (equal episodes per spot, pad pinned).
5. **Cosmos throughput is the bottleneck, not Isaac.** ~4 segments per 10 s episode; distilled edge is
   the only way to transfer 100+ episodes in a day. Budget it from a measured number (roadmap 04).
6. **Style reference exists.** `image_context_path` lets us hand Cosmos an actual frame of our station,
   which targets "our real look" more directly than a text prompt.
7. **GPU split.** Isaac Sim cannot use H100/H200; Cosmos Transfer needs ≥65 GB. RTX PRO 6000 (96 GB, RT
   cores) is the only single SKU that runs both, and it is the one GPU the event gives us (roadmap 01).
8. **No hosted Cosmos reasoner.** Token Factory retired its Cosmos3 reasoner, and its replacement is not a
   Cosmos model, so self-hosting on vLLM is the only path to the Cosmos Reason points (roadmap 05).
