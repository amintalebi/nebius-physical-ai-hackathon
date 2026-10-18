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

## Serve the reasoner (on `s2t-rtx6000`)

Cosmos3-Nano reasoner needs ~16-17 GB with vLLM (NVIDIA/Cosmos `cookbooks/cosmos3/reasoner/README.md`).
We have one GPU (01), so it shares it with Isaac Sim or training. `--gpu-memory-utilization 0.2` keeps vLLM from
claiming the whole card. Stop it during the Transfer bulk run unless `nvidia-smi` shows room.

```bash
vllm serve nvidia/Cosmos3-Nano --tensor-parallel-size 1 --mm-encoder-tp-mode data --async-scheduling \
  --allowed-local-media-path / --media-io-kwargs '{"video": {"num_frames": -1}}' --port 8000 \
  --gpu-memory-utilization 0.2   # ~19 GB of 96; raise to 0.25 if it fails to fit the KV cache
```

This is the vLLM *reasoner* serve from the NVIDIA/Cosmos cookbook. nebius/nebius-physical-ai also serves
`nvidia/Cosmos3-Nano` on vLLM, but with `--omni` as a **video generator** (`/v1/videos/sync`). That is a
different mode and a different endpoint, so don't copy that command here.

### Fallbacks: self-hosting is the only path that earns the points

Nebius Token Factory no longer serves a Cosmos reasoner. `nvidia/Cosmos3-Super-Reasoner` was retired on
2026-08-31 and returns HTTP 409 (nebius/nebius-physical-ai @ `8195442`,
`docs/workbench/token-factory-deprecation-verification.md`). Its replacement there, `MiniMaxAI/MiniMax-M3`, is
not a Cosmos model, so curation done with it does **not** count for the Cosmos Reason rubric line. In order:

1. **Default:** Cosmos3-Nano reasoner on vLLM on our one GPU, command above, beside Isaac or training.
2. **GPU busy with Transfer:** queue the scoring. It is resumable, so score in the gaps between Transfer batches.
3. **Nano won't serve:** `nvidia/Cosmos-Reason2-8B` through the same `vllm serve` pattern. The nebius repo has a
   container for it, validated on H100, but no serve recipe (TODO(verify) the exact flags on the smoke test).
   `cosmos_reason_score.py` takes `--model`, and the prompt and JSON parsing don't change.
4. **Last resort, never for curation:** Token Factory `MiniMaxAI/MiniMax-M3`
   (`--base-url https://api.tokenfactory.nebius.com/v1/ --api-key $NEBIUS_TOKEN_FACTORY_KEY --model MiniMaxAI/MiniMax-M3 --inline`).
   It is acceptable only as the ensemble verifier (10), described as "VLM verifier", not as Cosmos. Its JSON
   mode returns malformed output. Our scripts already ask for JSON in the prompt and parse it strictly, so
   don't add `response_format`.

Ask the organizers first (open question 11). If they host a Cosmos reasoner endpoint for the event, use it
with `--base-url … --api-key … --inline` and skip steps 1-3.

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
