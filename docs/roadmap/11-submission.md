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

The event already made the keys: SecretStash entry **`hackathon-object-storage`** in our project holds
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION=uk-south2`,
`AWS_ENDPOINT_URL=https://storage.uk-south2.nebius.cloud` and `ACCESS_KEY_EXPIRES_AT`
([participant guide](https://github.com/dariolaportanebius/nebius-starter-skill) §6). Don't create service accounts or keys.

1. **Bucket (once per team):** console → Storage → Object Storage → Create bucket. Name unique in the region
   (e.g. `s2t-group02-<suffix>`), class **Standard** with **Force storage class**, size **200 GiB**, versioning off.
   We get exactly one bucket, so check whether a teammate made it first.
2. **Keys on each box that uploads (the VM and the laptop):** console → SecretStash → `hackathon-object-storage` →
   primary version. Enter them at the prompts of `aws configure --profile nebius` (region `uk-south2`), never in a
   command line, chat, git or the bucket. Check `ACCESS_KEY_EXPIRES_AT` is after the cutoff.
3. **Prove write access now, not at T+8:30:**

```bash
AWS_PROFILE=nebius uv run --with boto3 python scripts/nebius_s3.py check s3://<bucket>/<team>/   # writes, reads back, deletes 1 byte
```

During the day, `nebius_s3.py put` mirrors a folder and skips files already uploaded (same key and size). Run it
after each checkpoint save, so outputs survive the VM:
`python scripts/nebius_s3.py put outputs/act_main s3://<bucket>/<team>/outputs/act_main`.
Both this script and `sync_to_nebius.sh` default to `uk-south2` and `https://storage.uk-south2.nebius.cloud`.

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
