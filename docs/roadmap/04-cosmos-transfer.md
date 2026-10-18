# 04 · Cosmos Transfer 2.5

**Points:** Cosmos Transfer 10 + the main lever for Accuracy (sim pixels that look like our table).
**Time box:** smoke T+1:00-2:00; bulk T+3:00-5:30 on `s2t-rtx6000`, after Isaac collection stops (one GPU, see 01).

## What "structure-preserving toward the real look" means here

The recorded joint actions are only valid if the arm, cube and pad stay **exactly where they were in
every frame**. So:

- **Edge control at weight 1.0** (default in the cosmos-transfer2.5 docs) carries the geometry. No depth or seg:
  edge is what the brief names, and every extra control costs time.
- **`image_context_path` = a real frame from our station camera.** Transfer 2.5 accepts a style reference image;
  it points at *our* lamp, table and tape, not a generic "realistic lab".
- **Prompt describes our station** (`configs/cosmos/station_prompts.txt`). **Rewrite those prompts after
  looking at the station**: arm colour, table material, lamp side, cube colour. Variants change light only,
  never the layout.
- **Frame count never changes.** Episodes are split into 93-frame segments (the model's chunk), the tail
  is padded by repeating the last frame, and outputs are re-stitched and trimmed to the original length.
  `assemble` refuses segments with the wrong frame count.

## Budget (measure, then decide N)

Per the cosmos-transfer2.5 docs, one 93-frame chunk on one H100-class GPU takes **~65 s distilled edge**
vs **~500 s base** (diffusion only). A 10 s episode is ~300 frames = 4 segments.

```
N_cosmos_episodes = floor( GPUs × hours_available × 3600 / (4 × seconds_per_segment_measured × variants) )
```

Example: 8 GPUs × 2 h, measured 100 s/segment end-to-end → 144 episodes. **Our event setup is 1 GPU**: 1 × 2.5 h at
100 s/segment → 22 episodes; at the documented ~65 s distilled → 34. Run `prepare --gpus 1` and set
`max_episodes` for `sim_cosmos_B` in `configs/data_mix.yaml` to what was actually transferred.
Use `--model=edge/distilled --num-steps 4` unless the smoke test shows the distilled output breaking
geometry. Try `"resolution": "480"` on the smoke test if time is tight (TODO(verify) quality; the input is 480p anyway).

## Commands

```bash
# style frame: one clean frame from the station camera, arm at rest, cube on B2
# -> configs/cosmos/station_reference.jpg

# smoke: 1 episode, then watch it next to the source and run metrics
python scripts/cosmos_transfer_batch.py prepare --dataset data/sim/B_real_units --work work/cosmos_smoke \
    --style-image configs/cosmos/station_reference.jpg --gpus 1 --limit 1
python scripts/cosmos_transfer_batch.py run --work work/cosmos_smoke --cosmos-repo ~/cosmos-transfer2.5
python scripts/cosmos_transfer_batch.py assemble --dataset data/sim/B_real_units --work work/cosmos_smoke --dst data/cosmos/smoke

# bulk
python scripts/cosmos_transfer_batch.py prepare --dataset data/sim/B_real_units --work work/cosmos_B \
    --style-image configs/cosmos/station_reference.jpg --gpus 8
python scripts/cosmos_transfer_batch.py run --work work/cosmos_B --cosmos-repo ~/cosmos-transfer2.5
python scripts/cosmos_transfer_batch.py assemble --dataset data/sim/B_real_units --work work/cosmos_B --dst data/cosmos/B_transfer

# measure
python scripts/cosmos_metrics.py --sim data/sim/B_real_units --cosmos data/cosmos/B_transfer \
    --real data/real/station_v3 --out reports/cosmos_metrics.json
```

Install on the VM per cosmos-transfer2.5 `docs/setup.md` (separate venv). Check `python examples/inference.py --help`
for the guardrail flag spelling before the bulk run; pass extra flags after `run … --`. Guardrails must be
**disabled** (`disable_guardrails` in `cosmos_transfer2/config.py`): the guardrail stack pulls Meta's gated
`Llama-Guard-3-8B`, which our token can't access. Our inputs are our own sim renders.

Smoke-test findings (commit 2ff49d0): `run` now passes `--disable-guardrails` itself, puts the Cosmos venv
`bin/` on PATH (weights are fetched with `uvx hf download`) and sets `COSMOS_EXPERIMENTAL_CHECKPOINTS=1` for
`edge/distilled` (otherwise that model is not registered). `--style-image` is optional (prompt-only; Cosmos then
uses a frame of the sim input as image context). **The HF account also needs access to the gated
`nvidia/Cosmos-Predict2.5-2B`**: every model loads its Wan2.1 tokenizer (`tokenizer.pth`) from there, and the
distilled config additionally fetches `robot/action-cond/..._ema_bf16.pt` from it at import time.

## Acceptance check (numbers, not impressions)

| Check | Pass | Tool |
|---|---|---|
| Frame count | Every assembled episode = parquet length | `assemble` (hard fail otherwise) |
| Structure kept | Mean **edge F1** sim↔Cosmos high and stable across episodes; episodes in `flag_low_edge_f1` dropped | `cosmos_metrics.py` |
| Toward real | `look_gap_cosmos_mean < look_gap_sim_mean`, and `episodes_closer_to_real` ≈ all | `cosmos_metrics.py` (DINOv2 if available) |
| No hallucination | Cosmos Reason `visual_defect=false` (cube does not vanish or duplicate) | 05 |
| Segment seams | Watch 5 episodes at seams (frames 93, 186, 279): no jump in arm position | eyes, logged in QA notes |
| It helps | `main` beats `ablation` on the real arm | 09 |

Save 3 side-by-side clips (sim | Cosmos | real at the same spot) for the submission.
`ffmpeg -i sim.mp4 -i cosmos.mp4 -filter_complex hstack sbs.mp4`

## If it fails

- Geometry drifts (low edge F1) → lower `guidance`, raise `edge_weight`, or try `--edge-threshold low`
  (more edges kept). Re-run the smoke episode only.
- Too slow → fewer episodes and 1 variant. 40 good Cosmos episodes with metrics beat 150 unchecked ones.
- Cosmos looks real but the ablation shows no gain → report it as measured. The Transfer rubric points come
  from a structure-preserving augmentation done correctly, not from a guaranteed gain.
