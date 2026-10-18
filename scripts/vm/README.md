# Pipeline scripts as run on s2t-rtx6000 (2026-10-18)

Copied from `~/work/` on the VM, where they ran (paths assume that layout: `~/work/{s2t,s2t_pr6,env_*,data,outputs,models,logs}`).

| Script | What it does |
|---|---|
| `s2t_train_blue3040_v2.sh` | ACT on blue sim set A (30+40 mm, 72 eps, front+wrist), 8k steps, sim eval per size at 4k/8k |
| `s2t_train_front.sh` | Same data, front camera only (the real station has no wrist camera) |
| `s2t_mix_front.sh` | Cosmos B and raw B twins -> `sim_main_front` / `sim_ablation_front` (94 eps each), train both, sim eval (Cosmos ablation) |
| `s2t_final.sh` | Real demos (drops applied) + sim main -> `final_main` (front only); trains it |
| `s2t_round2.sh`, `s2t_round_n.sh` | Fine-tune the previous final_main on sim main + all good real demos (`BASE=<ckpt> TAG=r3`) |
| `s2t_cosmos_style.sh` | Cosmos Transfer on sim A_30 with a real station frame as the style image |
| `s2t_snapshot.sh` | Write-once model registry: `~/work/models/<version>/` + `s3://…/models/<version>/` + `registry.jsonl` |
| `s2t_align_meta.py`, `s2t_fix_fps.py` | Metadata fixes so `lerobot-edit-dataset merge` accepts real (AV1, so_follower) + sim (H.264, so101_follower) |
