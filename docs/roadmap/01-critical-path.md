# 01 · Critical path

**Points:** all of them. This file is the schedule; the stage files are the how.
**Cutoff: 18:00** (open question 3). Plan backwards from it: final upload verified by 17:45.
Times are T+hours from start. Three people: **R** (robot/station), **S** (sim + Cosmos), **T** (training + Nebius + submission).

## Machines (event setup: one GPU for everything)

The event gives each team **one** GPU in project `group02-project`, region **`uk-south2`**
([participant guide](https://github.com/dariolaportanebius/nebius-starter-skill)). Our VM:

| Box | GPU | Runs |
|---|---|---|
| `s2t-rtx6000` (`gpu-rtx6000-a` / `1gpu-24vcpu-218gb`, on-demand, `ubuntu24.04-cuda13.0`, 400 GiB, static public IP) | 1× RTX PRO 6000 Blackwell, 96 GB, RT cores, driver 580 / CUDA 13.0 | Isaac Sim, Cosmos Transfer, Cosmos Reason (vLLM), ACT training, **sharing one GPU** |
| Station laptop | none needed | teleop, rollout, eval (ACT-resnet18 runs on CPU/MPS) |

`ssh ubuntu@<ip>` with the key in its cloud-init. Get the IP with
`nebius --profile hackathon compute instance get-by-name --parent-id <project> --name s2t-rtx6000`.
Team limits: 3 VMs, 20 non-GPU vCPUs, 4 disks / 500 GiB (100 GiB left), **1 public IP (used by this VM)**,
1 bucket of 200 GiB. A teammate who needs a second box gets a CPU VM or a CPU DevLab, never a second GPU.

### Environments on the VM (installed 2026-10-18)

| Path | What | Use for |
|---|---|---|
| `~/work/so101_sim_pickplace` | starter @ `52b23a9` + `sim_patches/s2t_station.patch` + `isaaclab_release30_compat.patch`, `env.sh` pointed at `~/work` | `collect_grid.py --starter ~/work/so101_sim_pickplace` |
| `~/work/env_isaaclab` | Isaac Sim 6.1.0 + Isaac Lab `release/3.0.0` (`0c114a24a`), torch 2.11+cu130 | `$ISAACLAB_PY` (sim) |
| `~/work/env_lerobot` | LeRobot 0.6.2 @ `146d847` `[training,dataset,feetech]`, torch 2.11+cu128 | conversion, merge, ACT training |
| `~/work/cosmos-transfer2.5/.venv` | Cosmos Transfer 2.5 @ `2ff49d0`, `uv sync --extra=cu130`, torch 2.9.1 | `cosmos_transfer_batch.py run --cosmos-repo ~/work/cosmos-transfer2.5` |
| `~/work/venv_tools` | boto3, pyyaml, numpy, pyarrow, uv | `nebius_s3.py`, our helper scripts |
| `~/work/s2t` | this repo | |

Not installed: GR00T (we train ACT; its install needs an interactive Hugging Face login) and vLLM (only needed if
the Token Factory endpoint is not used, 05). Cosmos weights download on first inference; the VM's Hugging Face token
(`~/.cache/huggingface/token`) has access to Cosmos-Transfer2.5-2B, Cosmos-Guardrail1 and Cosmos-Reason1-7B, not to
Meta's Llama-Guard-3-8B, so run Transfer with guardrails disabled (04). The station laptop needs the same LeRobot commit.

### Sharing the GPU (96 GB)

| Job | VRAM (approx.) | Runs alongside |
|---|---|---|
| Isaac Sim collection | ~10-20 GB | Reason, training |
| Cosmos Transfer 2.5 (2B) | ~65 GB | Reason only if `nvidia-smi` shows room; **not** Isaac (render + diffusion contend for the same SMs) |
| Cosmos Reason, Cosmos3-Nano on vLLM | ~16-17 GB (`--gpu-memory-utilization 0.2`) | anything except Transfer at full size |
| ACT training, resnet18, batch 32 | ~5-15 GB per run | main + ablation (+ seed 2) **concurrently** |

Order of the day on the GPU: Isaac smoke → Transfer smoke (measure s/segment) → Isaac bulk (sets A and B,
Reason scoring real data alongside) → Transfer bulk on B → train main + ablation concurrently. One GPU means the
Cosmos budget is the 1-GPU line of 04's formula: plan **~30-40 Cosmos episodes, not 150**, and set
`max_episodes` in `configs/data_mix.yaml` from the measured number.

Always pin a GPU job's memory (vLLM `--gpu-memory-utilization`, `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`)
and watch `nvidia-smi` before starting the next one. An OOM kill of the Isaac run costs the episodes since its
last flush.

Not adopted from nebius/nebius-physical-ai @ `8195442`: `npa` workflows, SkyPilot, Managed Kubernetes, PAIDF, the
Sim2Real engine (they need a cluster and a Linux operator host), and its quarantined Isaac Lab / LeRobot images.

## Sim-first phase (no arm access yet)

The organizers: the judging stations match the starter repo's scene, and arm time comes after we show a working
sim. So the first milestone is a **measured sim policy**, not the real-arm smoke test.

- **Geometry:** the starter scene *is* the station (cube 30 mm red, pad 90 mm at (0.21, -0.09), front camera at
  (0.80, 0, 0.42) → (0.18, 0, 0.02), C270-like 640x480). `configs/station.yaml` already holds these values, and
  its 3x3 grid spans the starter's cube area (x 0.16-0.27, y 0.02-0.13). Confirm the taped spots at the station.
- **Units:** the starter writes joints in LeRobot's `use_degrees=False` convention (`so101_units.py`, README
  "Dataset conventions"), so sim training and sim eval need **no conversion and no calibration file**. On the
  real arm, record and roll out with `--robot.use_degrees=false`, then verify with the open-loop replay (02).
- **Loop** (all on `s2t-rtx6000`):

```bash
python scripts/collect_grid.py --starter ~/work/so101_sim_pickplace --per-spot 12 --dataset-name sim_A
cp -r ~/work/datasets/local/sim_A ~/work/data/sim/A && \
  ~/work/env_lerobot/bin/python -m lerobot.scripts.convert_dataset_v21_to_v30 --repo-id=local/sim_A --root=data/sim/A --push-to-hub=false
~/work/env_lerobot/bin/lerobot-train --dataset.repo_id=local/sim_A --dataset.root=data/sim/A --policy.type=act \
  --policy.device=cuda --policy.push_to_hub=false --output_dir=outputs/act_sim_A --steps=20000 --batch_size=32 …
~/work/env_lerobot/bin/python scripts/act_server.py --ckpt outputs/act_sim_A/checkpoints/last/pretrained_model &
$ISAACLAB_PY scripts/eval_act_in_sim.py --per-spot 2 --ckpt-name act_sim_A --out reports/sim_eval.jsonl --headless
```

- **Gate S1 (before asking for the arm):** `eval_act_in_sim.py` reports a success rate per spot on all 9 spots,
  with videos. Plumbing verified 2026-10-18 on the 3-episode smoke set (300-step model, 1 trial, timeout as
  expected): server, observations, actions, success test, jsonl and mp4 all work.

## Timeline

| T+ | R (station) | S (sim + Cosmos) | T (train + Nebius) | Gate |
|---|---|---|---|---|
| 0:00-0:30 | Ask the [open questions](open-questions.md). Copy the calibration JSON. Measure grid spots, pad, camera pose → `configs/station.yaml` | On `s2t-rtx6000`: run `nebius/setup_vm.sh` from the starter (long install, start it first) | Create the bucket, load the SecretStash keys (11), `nebius_s3.py check`. Install LeRobot on the VM. Start a `nebius/usage.md` log | — |
| 0:30-2:00 | **Smoke test**: record 3 real episodes, push to the VM | Smoke: `NUM_EPISODES=3` on 1 spot, convert units | **Smoke**: merge 3 real + 3 sim, train 2k steps, copy checkpoint to the laptop, `rollout.sh` runs on the arm (moving at all, not succeeding) | **G1: end-to-end pipe works**. If not, fix this before anything else |
| 1:00-2:00 | **Open-loop replay test** of a converted sim episode on the real arm (02) | Overlay check, adjust sim camera (02) | Cosmos Transfer smoke on 1 episode, measure s/segment (04) | **G2: replay picks the cube** → units trusted |
| 2:00-4:00 | Teleop 45 demos, 5 per spot (06) | `collect_grid.py`: set A (12/spot) and set B (18/spot) | Start vLLM Reasoner; score real episodes as they land (05). Hand-label 20 | — |
| 3:00-5:30 | Hand-label Cosmos samples (visual QA) | Cosmos Transfer on set B (04), then metrics | Score sim A, sim B, Cosmos B. `decide`. `agree` | **G3: Reason agreement κ ≥ 0.6** or tighten the rule |
| 5:30-6:00 | — | — | Apply drops, convert v2.1→v3, merge `main` + `ablation`, `validate_manifest.py` | **G4: manifest passes** |
| 6:00-7:15 | Station free: re-record weakest spots if any slots are left | Ensemble prep (10) | Train main + ablation concurrently on the one GPU, + seed 2 of main if steps/s allows | — |
| 7:15-8:30 | **Eval**: ablation 9 trials, main 18 blind trials, ensemble 9 (09/10) | | Upload as results land | **G5: choose the checkpoint** (09 rule) |
| 8:30-9:00 | Freeze. Rollout command card for the judges | | `sync_to_nebius.sh`, verify the listing (11) | **G6: list-back shows everything** |

## Rules that keep the day on track

- **Nothing scales before its gate.** No 100-episode collection before G2. A unit bug found at T+6
  wastes every sim and Cosmos episode.
- **Station time is the scarcest resource.** One arm, shared by teleop, replay and eval. R owns its
  queue; sim and training never block on it.
- **Every long job writes its log to disk and its outputs to Object Storage as it goes** (preemptible
  VMs, laptop sleep). Re-running is cheap; reconstructing evidence is not.
