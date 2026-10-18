# 11 · Submission

**Points:** all non-accuracy points are read from here. "Your folder lands there by the cutoff or it doesn't exist."
**Time box:** first upload at T+6:00 (anything), final at T+8:30, verified by T+8:45.

## Object Storage layout (`s3://<bucket>/<team>/`)

```
README.md                    one page: claim -> evidence file, for each rubric line (template below)
manifest.json                from validate_manifest.py: episodes per source per mix, rules, curation counts
checkpoints/main/            pretrained_model/ (+ sha256.txt)        <- the judged checkpoint
checkpoints/ablation/        pretrained_model/ (+ sha256.txt)
datasets/                    mix_main/, mix_ablation/ (LeRobot v3.0), if the organizers want data (ask)
curation/                    reason_*.jsonl, decisions.json (the rule), agreement.json, hand_labels.csv
cosmos/                      specs/ (the shards = exact settings), metrics.json, side_by_side/*.mp4, prompts
eval/                        trials.csv, eval_summary.md, watchdog.jsonl, videos/ (a few trials)
alignment/                   replay test video + notes, overlay.png + edge F1
nebius/                      usage.md, instance list, nvidia-smi, training logs, loss curves
ensemble/                    README.md (design) + its eval rows
```

## Credentials (T+0:00-0:30, owner T)

Use the organizers' bucket if they give one (open question 3); otherwise create our own. Object Storage takes
S3 access keys that belong to a **service account**, not to your user. These are the same `nebius` CLI steps
that nebius/nebius-physical-ai @ `8195442` automates in `research/lerobot-deploy/environment.sh`:

```bash
export NEBIUS_TENANT_ID=tenant-… NEBIUS_PROJECT_ID=project-… NEBIUS_REGION=eu-north1
nebius storage bucket create --name <bucket> --parent-id $NEBIUS_PROJECT_ID     # skip if organizers gave one
SA=$(nebius iam service-account create --parent-id $NEBIUS_PROJECT_ID --name s2t-storage --format json | jq -r .metadata.id)
EDITORS=$(nebius iam group get-by-name --parent-id $NEBIUS_TENANT_ID --name editors --format json | jq -r .metadata.id)
nebius iam group-membership create --parent-id $EDITORS --member-id $SA       # needs tenant admin; else ask organizers
KEY=$(nebius iam v2 access-key create --parent-id $NEBIUS_PROJECT_ID --name s2t-key \
        --account-service-account-id $SA --format json | jq -r .metadata.id)
export AWS_ACCESS_KEY_ID=$(nebius iam v2 access-key get --id $KEY --format json | jq -r .status.aws_access_key_id)
export AWS_SECRET_ACCESS_KEY=$(nebius iam v2 access-key get-secret --id $KEY --format json | jq -r .secret)
```

The secret is shown once. Put it in `~/.aws/credentials` under `[nebius]` on every box that uploads (VM-gpu,
VM-sim, laptop), never in git. Then prove write access **now**, not at T+8:30:

```bash
uv run --with boto3 python scripts/nebius_s3.py check s3://<bucket>/<team>/   # writes, reads back, deletes 1 byte
```

During the day, `nebius_s3.py put` mirrors a folder and skips files already uploaded (same key and size). Run it
after each checkpoint save so a preempted VM loses nothing:
`python scripts/nebius_s3.py put outputs/act_main s3://<bucket>/<team>/outputs/act_main`.
The endpoint is `https://storage.<region>.nebius.cloud` for both this script and the aws CLI.

## Upload

Build it locally under `submission/` (git-ignored), then:

```bash
BUCKET=s3://<bucket>/<team> REGION=<region> ./scripts/sync_to_nebius.sh
```

The script re-runs the manifest validator, syncs, lists the remote recursively into `logs/last_sync_listing.txt`,
and byte-compares the remote `manifest.json` with the local one.

## README template (top of the folder)

```
Team / station:            ...
Main checkpoint:           checkpoints/main  (sha256 ...)  ACT, <steps> steps, trained on Nebius <gpu> (nebius/usage.md)
Data (manifest.json):      real N / sim N / cosmos N = total N  (caps 50 / 300)
Cosmos Transfer:           edge control w=1.0 + station style frame; edge F1 = x, look gap sim y -> cosmos z (cosmos/metrics.json)
Cosmos Reason:             rule "keep iff task_success and not visual_defect and motion_quality>=3";
                           dropped real a, sim b, cosmos c; agreement with hand labels kappa = k (curation/)
Ablation (no Cosmos):      main s/n vs ablation s/n on the real arm (eval/eval_summary.md)
Self-eval of main:         s/18 blind trials, 95% CI [lo, hi], per-spot matrix
Ensemble:                  ACT x2 + Cosmos Reason verifier, s/9 vs single s/9 (ensemble/)
Sim-to-real alignment:     joint-unit conversion verified by open-loop replay (alignment/)
```

## Acceptance check

- `logs/last_sync_listing.txt` shows every folder above, with non-zero sizes, timestamped before the cutoff.
- `manifest.json verified remote == local` printed.
- A teammate who didn't build it opens README.md from the bucket and can find each number's source file in under a minute.

## If it fails

Credentials or endpoint wrong → `nebius_s3.py check` at T+0:30 (Credentials above), not at T+8:30.
