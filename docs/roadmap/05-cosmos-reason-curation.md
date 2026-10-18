# 05 · Cosmos Reason as curator

**Points:** Cosmos Reason 10 ("called on your own sim and/or real episode videos, JSON saved, one
stated curation decision made from it"), plus Accuracy (bad demos removed).
**Time box:** server up by T+2:00; scoring runs in the background as datasets land; decision by T+5:30.

## The decision (stated before seeing results)

> **Keep an episode iff `task_success` and not `visual_defect` and `motion_quality ≥ 3`.**

Applied to every source: real, sim A, sim B, Cosmos B. Why each clause:
- `task_success`: a demo that ends with the cube off the pad teaches failure. Real teleop has some.
- `visual_defect`: catches Cosmos hallucinations (cube vanishes, duplicates, gripper melts). Those
  frames would pair a correct action with a wrong image.
- `motion_quality`: hesitant teleop (stop, back off, retry) teaches the policy to hesitate; ACT copies it.

A Cosmos B episode dropped for `visual_defect` is also dropped from raw B, so the ablation stays a twin
of main (07).

## Serve the reasoner (VM-gpu)

Cosmos3-Nano reasoner needs ~16-17 GB with vLLM (NVIDIA/Cosmos `cookbooks/cosmos3/reasoner/README.md`),
so it can share a GPU box with training. Don't put it on a GPU that is running Transfer (65 GB); give it its own.

```bash
vllm serve nvidia/Cosmos3-Nano --tensor-parallel-size 1 --mm-encoder-tp-mode data --async-scheduling \
  --allowed-local-media-path / --media-io-kwargs '{"video": {"num_frames": -1}}' --port 8000
```

Alternative if no GPU is free: Nebius Token Factory, if it serves a Cosmos reasoner (TODO(verify) model list),
with `--base-url <token factory url> --api-key $KEY --inline`.

## Commands

```bash
python scripts/cosmos_reason_score.py score --name real         --dataset data/real/station_v3
python scripts/cosmos_reason_score.py score --name sim_raw_A    --dataset data/sim/A_real_units
python scripts/cosmos_reason_score.py score --name sim_raw_B    --dataset data/sim/B_real_units
python scripts/cosmos_reason_score.py score --name sim_cosmos_B --dataset data/cosmos/B_transfer
python scripts/cosmos_reason_score.py decide          # -> data/curation/decisions.json
python scripts/cosmos_reason_score.py agree --labels data/curation/hand_labels.csv
```

Scoring is resumable (it skips episodes already in `reason_<name>.jsonl`); unparseable answers count as drops
and are listed as `unparsed`.

## Acceptance check: the curator is checked against people

Hand-label ~20 episodes before looking at Reason's answers: 10 real (include the ones that felt bad
while teleoperating) and 10 Cosmos. CSV `name,episode,success` where success means "I would keep this".

| Metric (`agreement.json`) | Pass | If not |
|---|---|---|
| Cohen's κ | ≥ 0.6 | Inspect disagreements; tighten the prompt or the threshold; re-score only the labelled set; repeat once |
| `false_keep` | ≤ 2 | The rule is too lenient; raise `motion_quality` threshold to 4 |
| Drop rate per source | Real < 30 %, sim A/B < 15 % | A high sim drop rate means the expert or the prompt is wrong, not the data |

Sanity checks that need no labels: sim episodes are all expert successes, so Reason should say
`task_success=true` for nearly all of them. That is a free accuracy test of the curator.

## If it fails

κ stays low after one prompt revision → keep the JSON and the stated rule, but apply only the
`visual_defect` clause (the one Reason is most reliable on for gross artifacts). State that in the
submission with the agreement numbers. A curation decision with a measured reliability is still a decision.
