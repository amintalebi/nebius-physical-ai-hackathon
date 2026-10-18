# 00 · Scoring map

70 of 100 points are awarded for evidence, not luck. Only 30 depend on the 3 judged trials, and 3
trials is a coin-flip-sized sample: a policy with a true 70 % success rate scores 3/3 only 34 % of
the time and ≥2/3 78 % of the time (`s2t.stats.p_at_least_k_of_3`). So: **raise the true rate as
far as possible, and make every other point impossible to miss.**

| Criterion | Pts | What earns it | Proof artifact (in the submission) | Produced by |
|---|---|---|---|---|
| Accuracy | 30 | Cube released and at rest on pad, ≤2 min, 3 judge trials on spots from a hidden fixed sequence | Judges' count; our pre-eval `eval/eval_summary.md` predicts it | 02, 03, 06, 08, 09 |
| Cosmos Reason | 10 | Called on our sim and real episode videos, JSON saved, **one stated curation decision** | `curation/reason_*.jsonl`, `curation/decisions.json` (rule + drops), `curation/agreement.json` (vs hand labels) | 05 |
| Cosmos Transfer | 10 | Structure-preserving augmentation of sim toward the real look | `cosmos/specs/*.jsonl` (edge control, style frame), `cosmos/metrics.json` (edge F1 + look gap), side-by-side clips, ablation result | 04, 08, 09 |
| Nebius | 20 | Nebius Cloud used for training | VM ids + GPU type, training logs and loss curves, datasets and checkpoints in Object Storage, `nebius/usage.md` | 08, 11 |
| Technical competence | 15 | Deploy on the robot in real life | Rollout video(s), `eval/trials.csv` with ≥18 real trials, replay-test evidence | 02, 09 |
| Creativity | 15 | "Ensemble of models used" | `ensemble/README.md` + `data/eval/watchdog.jsonl` + measured gain vs single checkpoint | 10 |

## Points most teams will leave on the table

- **Cosmos Reason without a decision.** Calling the model and saving JSON is half of it. The rubric
  asks for *one stated curation decision made from it*. Ours: `keep iff task_success and not
  visual_defect and motion_quality >= 3`, applied to every source, with a count of what it dropped
  and an agreement score against our own hand labels (05).
- **Cosmos Transfer without proof of "structure-preserving".** We report edge F1 (sim vs Cosmos)
  and look-gap (distance to real station frames) per episode (04), and run the ablation (08/09).
- **Nebius without receipts.** Keep logs, VM ids and listings as files from the first hour, not as a
  reconstruction at the end (11).

## Decision rule when time runs short

Protect in this order: (1) a deployable main checkpoint that contains sim data and passes
`validate_manifest.py`; (2) the curation decision JSON; (3) Cosmos Transfer outputs in the main mix;
(4) the submission upload verified by list-back; (5) the ablation; (6) the ensemble.
Steps 1-4 are worth ~70 points even with a mediocre success rate.
