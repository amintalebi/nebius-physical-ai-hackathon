# Nebius usage log (evidence for "Nebius Cloud used for training", 20 pts)

Running log, appended during the day. All times **UTC** (Berlin = UTC+2; cutoff 18:00 local = 16:00 UTC).
Numbers come from `nebius` CLI output and the VM logs in `~/work/logs/`; anything not measured yet is `TODO`.
Raw snapshots (nvidia-smi, df, pip lists, git revisions, log summaries, training step lines) are made by
`scripts/collect_evidence.sh` and uploaded to `s3://s2t-group02-a66c17/submission_draft/nebius/evidence/<UTC ts>/`
(final team prefix TBD by the organizers).

## Compute: one GPU VM for sim, Cosmos and training

From `nebius --profile hackathon compute instance get --id computeinstance-e05kmxe3mvhpg3waqf` (read 11:08 UTC):

| Field | Value |
|---|---|
| Project | `project-e05d1345ln0038q109ef98` (group02-project), region **uk-south2** |
| Instance | `s2t-rtx6000`, id `computeinstance-e05kmxe3mvhpg3waqf`, state RUNNING |
| Created | 2026-10-18T10:02:33Z |
| Platform / preset | **`gpu-rtx6000-a` / `1gpu-24vcpu-218gb`** (1x NVIDIA RTX PRO 6000 Blackwell Server Edition, 96 GB) |
| Billing | on-demand (`on_demand: {}`), capacity block group `capacityblockgroup-e05r02s9hm766n4gpb4o2` |
| Boot disk | `s2t-rtx6000-boot` (`computedisk-e05yswrgmsm4n71tc5`), 400 GiB NETWORK_SSD, image family `ubuntu24.04-cuda13.0` |
| Network | static public IP, subnet `vpcsubnet-e05mgcdz5ftdn29dx2` |
| Driver / CUDA | 580.173.02 / 13.0 (nvidia-smi) |

## Object Storage

From `nebius storage bucket list --parent-id project-e05d1345ln0038q109ef98` (read 11:08 UTC):

| Field | Value |
|---|---|
| Bucket | `s2t-group02-a66c17` (`storagebucket-e052610796303609001232`), state ACTIVE |
| Created | 2026-10-18T10:13:13Z |
| Endpoint / region | `storage.uk-south2.nebius.cloud` / uk-south2 |
| Class | `ENHANCED_THROUGHPUT`, force storage class on, versioning off |
| Max size | 214,748,364,800 B (200 GiB) |
| Content at 11:08 | 13 objects, 6,492,121 B (`data/sim/sim_smoke_v21/`, uploaded 10:48) |
| Evidence uploaded | 11:10 `submission_draft/nebius/evidence/20261018T111013Z/` (38 files, 65,371 B); 11:12 `submission_draft/nebius/{usage.md, cloud/ (instance get/list, bucket list), loss_curves/train_smoke.loss.png, logs/train_smoke.log}` |

## GPU snapshot (11:08:09 UTC, during sim sets A + B collection)

```
NVIDIA-SMI 580.173.02             Driver Version: 580.173.02     CUDA Version: 13.0
GPU 0  NVIDIA RTX PRO 6000 Blac...  On | 00000000:FE:00.0 Off | 0
N/A   39C  P0   130W / 600W | 10228MiB / 97887MiB | 41%  Default
Processes:
  28246  C+G  .../work/env_isaaclab/bin/python   5071MiB   (Isaac Sim, set A collect_demos.py)
  30245  C+G  .../work/env_isaaclab/bin/python   5071MiB   (Isaac Sim, set B collect_demos.py)
```

TODO: snapshot during the main/ablation training run (`bash ~/work/evidence/collect_evidence.sh` on the VM).

## Software on the VM (installed 2026-10-18)

| Env | Contents | Install log, wall-clock |
|---|---|---|
| `~/work/env_isaaclab` | Isaac Sim (starter `nebius/setup_vm.sh`) | `setup_isaac.log` 10:07:55 → 10:14:53, **7 min 0 s**, `EXIT=0` |
| `~/work/env_isaaclab` + `~/work/IsaacLab` | Isaac Lab `release/3.0.0` | `install_isaaclab.log` 10:15:51 → 10:28:21, **12 min 31 s**, `EXIT=0` |
| `~/work/env_lerobot` | LeRobot 0.6.2 (uv) | `install_lerobot.log` 10:28:32 → 10:28:42, **10 s**, `EXIT=0` |
| `~/work/cosmos-transfer2.5/.venv` | Cosmos Transfer 2.5, torch 2.9.1+cu130 | `install_cosmos.log` 10:29:29 → 10:31:17, **1 min 48 s**, `EXIT=0` |

Total VM-create → all envs ready: 10:02:33 → 10:31:17 = **29 min**. Full `pip list` per env and git commits per
repo are in each evidence snapshot (`pip/`, `git/`).

## Wall-clock per stage (from `~/work/logs`)

| Stage | Log | Start → end (UTC) | Result | Rate |
|---|---|---|---|---|
| Sim smoke try 1 | `sim_smoke.try1.log` | 10:38:49 → 10:38:51 | `EXIT=1`: `AttributeError: No isaaclab.envs.mdp attribute image` (Isaac Lab 3.0 API) — fixed by `isaaclab_release30_compat.patch` | – |
| Sim smoke (spot B2 x3) | `sim_smoke.log` | 10:39:51 → 10:47:34 | 3/3 expert success, 3 episodes, 915 frames, `EXIT=0` | **~20 s/episode** (0.3 / 0.7 / 1.0 min cumulative); 7 min 43 s incl. Isaac start-up |
| Smoke data upload | bucket listing | 10:48:40 | `data/sim/sim_smoke_v21/` 13 objects, 6.5 MB | – |
| Set A collection (12/spot x 9 spots) | `sim_A.log` | 10:53:03 → running | at 11:10 UTC: 36 episodes kept (A1-A3 done, 10,927 frames), B1 in progress; expert attempts **38 success / 8 failed = 82.6 %** | 12 episodes per spot in 4.5-5.5 min (~25 s per kept episode incl. retries) |
| Set B collection (18/spot x 9 spots) | `sim_B.log` | 11:06:54 → running | at 11:10 UTC: spot A1 8/9 attempts successful | ~24 s/attempt while sharing the GPU with set A |
| ACT smoke training | `train_smoke.log` | 10:55:27 → 10:56:08 | 300 steps, batch 8, 3 episodes / 915 frames, 52 M params; loss **13.148 (step 50) → 2.962 (step 300)**, l1 0.726 → 0.448, kld 1.242 → 0.251, no NaN | **~17.5 steps/s, ~140 samples/s** (step_s 0.057), 3.7 GB GPU memory; 36 s total incl. 11.5 s first-step warm-up |
| ACT smoke sim eval | `eval_smoke.log`, `reports/sim_eval_smoke.jsonl` | 10:56:45 → 11:04:02 | act_smoke_300 on B2: 0/1 (timeout after 300 steps); plumbing check only (300-step model) | 10 s sim / 17 s wall per trial |
| Cosmos Reason curation (Token Factory dedicated endpoint, `Cosmos3-Super-Reasoner`) | roadmap 05 smoke | 2026-10-18 | 3 smoke sim episodes: all parsed, all `task_success=true`, motion 5 | **~7 s/episode** with `--inline` (≈ 35 min for 300 episodes) |
| Cosmos Transfer smoke | `cosmos_smoke.log` | 11:09:14 → 11:09:55 | `exit codes: [1]`, rc=1 — TODO: fix and measure s/segment | TODO |
| Set A → v3.0 convert + ACT `act_sim_A` (15k steps, batch 32) | `chain_A.log` | waits for `sim_A` `EXIT=0` | TODO | TODO steps/s at batch 32 |
| Sim eval of `act_sim_A` checkpoints 5k/10k/15k | `eval_watch.log`, `reports/sim_eval_act_sim_A.jsonl` | waits for checkpoints | TODO success rate per spot | – |
| ACT main + ablation | `train_act_main.log`, `train_act_ablation.log` | TODO | TODO final loss, loss curves (`scripts/plot_loss.py`) | TODO |

## Checkpoints (sha256 of `model.safetensors`)

| Checkpoint | sha256 | Uploaded to |
|---|---|---|
| `outputs/act_smoke/checkpoints/000300` (= `last`) | `4066be03e6f0c847fb39b40208746dffeb435692c20797f5f084a5caccdf0553` | TODO (smoke only) |
| `act_sim_A` / `act_main` / `act_ablation` | TODO | TODO |

## Loss curves

- `submission_draft/nebius/loss_curves/train_smoke.loss.png` (300-step smoke, made with `scripts/plot_loss.py`).
- TODO: main + ablation on one figure: `python scripts/plot_loss.py train_act_main.log train_act_ablation.log -o loss_main_vs_ablation.png`.

## How to refresh this log

```bash
# on the VM (read-only except ~/work/evidence/<ts>/; uploads the snapshot)
bash ~/work/evidence/collect_evidence.sh      # copy of scripts/collect_evidence.sh
# locally, read-only cloud listings
nebius --profile hackathon compute instance get --id computeinstance-e05kmxe3mvhpg3waqf
nebius --profile hackathon storage bucket list --parent-id project-e05d1345ln0038q109ef98
AWS_PROFILE=nebius uv run --no-project --with boto3 python scripts/nebius_s3.py ls s3://s2t-group02-a66c17/
```
