# 07 · Dataset mixes and manifest

**Points:** gate for everything (rules: real ≤ 50, total ≤ 300, main includes sim data, manifest lists
episode counts per source). The controlled ablation feeds the Cosmos Transfer claim.
**Time box:** T+5:30-6:00. Prepare the commands earlier so this is only execution.

## The two mixes

| Source | Kind | `main` | `ablation` |
|---|---|---|---|
| real (after curation) | real | ≤ 45-50 | same |
| sim A (raw) | sim | 105 | same |
| sim B, Cosmos-rendered | cosmos | 150 | — |
| sim B, raw (the same 150 trajectories) | sim | — | 150 |
| **total** | | **≤ 300** | **≤ 300** |

`ablation` differs from `main` in exactly one thing: whether 150 trajectories are seen through
Cosmos pixels or raw sim pixels. Same actions, same count, same training settings (08). A
success-rate gap between them is the effect of Cosmos Transfer. Most teams compare against a mix with fewer
episodes, which measures data quantity, not Cosmos.

Ratio: about 15 % real. Do not oversample real data by duplication: duplicates count as episodes against
the 300 cap, and the point of the brief is that sim + Cosmos carry the weight.

## Order of operations (indices matter)

1. Score each source in its own indices (05); `decide` writes `data/curation/decisions.json`.
2. Convert each sim/Cosmos v2.1 dataset to v3.0 (`convert_dataset_v21_to_v30`, in place, episode order kept).
   The raw v3 paths are the `raw:` entries in `configs/data_mix.yaml`.
3. `build_mixes.py`: removes dropped episodes per source; **any episode dropped from Cosmos B is also dropped
   from raw B and vice versa**; applies `max_episodes` by even spacing (keeps spot balance); merges;
   recomputes stats (Cosmos changed image statistics).
4. `validate_manifest.py`: recounts from disk, enforces the rules, writes `submission/manifest.json`.

```bash
python scripts/build_mixes.py              # read the plan: keep/remove per source, total per mix
python scripts/build_mixes.py --execute
python scripts/validate_manifest.py
```

## Acceptance check

- `validate_manifest.py` exits 0 and prints both totals ≤ 300. It counts from each dataset's
  `meta/info.json`, not from the config.
- It also fails if any two sources differ in fps or feature keys/shapes. That catches the wrist camera,
  a renamed camera key, or a wrong joint count before `merge` or training fails on it.
- `lerobot-dataset-viz` on one merged episode from each source: real, sim, Cosmos all show the `front` camera
  and joint traces in the same numeric range (units check, again).
- `train_act.sh` runs the validator first and refuses to train on a mix that breaks a rule.

## If it fails

Merge refuses because of feature mismatch → `validate_manifest.py` names the source; fix that source, never
the merged copy. The mixes are rebuilt from `raw:` every run, so re-running is safe.
