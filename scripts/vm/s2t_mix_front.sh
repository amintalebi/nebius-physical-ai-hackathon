# Front-only sim mixes: main = A + Cosmos B (transferred episodes), ablation = A + the same raw B episodes.
set -uo pipefail
W=~/work; S=$W/s2t; L=$W/logs; LR=$W/env_lerobot/bin; R=$W/s2t_pr6
log(){ echo "[mix $(date -u +%H:%M:%S)] $*"; }
# 0. B_30: Isaac segfaulted mid-episode 29 -> orphan videos without parquet; drop them so v3 conversion works
for d in $W/datasets/local/sim_B_30 $W/data/cosmos/B_30; do find $d/videos -name "episode_000029.mp4" -print -delete; done
for s in 30 40; do
  drop=$(python3 -c "import json;print(json.load(open(\"$S/data/curation/cosmos_not_transferred_B_$s.json\"))[\"drop\"])")
  for k in CB RB; do
    src=$W/data/cosmos/B_$s; [ $k = RB ] && src=$W/datasets/local/sim_B_$s
    rm -rf $W/data/v3/${k}full_$s $W/data/v3/${k}full_${s}_v30 $W/data/v3/${k}full_${s}_old $W/data/v3/${k}_$s $W/data/v3/${k}f_$s
    cp -r $src $W/data/v3/${k}full_$s
    $LR/python -m lerobot.scripts.convert_dataset_v21_to_v30 --repo-id=local/${k}full_$s --root=$W/data/v3/${k}full_$s --push-to-hub=false >> $L/mixf.log 2>&1 || { log "convert $k $s failed"; continue; }
    $LR/lerobot-edit-dataset --repo_id=local/${k}full_$s --root=$W/data/v3/${k}full_$s --new_repo_id=local/${k}_$s --new_root=$W/data/v3/${k}_$s \
      --operation.type=delete_episodes --operation.episode_indices="$drop" >> $L/mixf.log 2>&1 || { log "delete $k $s failed"; continue; }
    $LR/lerobot-edit-dataset --repo_id=local/${k}_$s --root=$W/data/v3/${k}_$s --new_repo_id=local/${k}f_$s --new_root=$W/data/v3/${k}f_$s \
      --operation.type=remove_feature --operation.feature_names="[observation.images.wrist]" >> $L/mixf.log 2>&1 || { log "front-only $k $s failed"; continue; }
    python3 $W/s2t_fix_fps.py $W/data/v3/${k}f_$s >> $L/mixf.log 2>&1
    log "$k $s: $(python3 -c "import json;i=json.load(open(\"$W/data/v3/${k}f_$s/meta/info.json\"));print(i[\"total_episodes\"],\"eps\")")"
  done
done
python3 $W/s2t_fix_fps.py $W/data/sim/A_blue3040_front >> $L/mixf.log 2>&1
for mix in main ablation; do k=CB; [ $mix = ablation ] && k=RB; rm -rf $W/data/mix/sim_${mix}_front
  $LR/lerobot-edit-dataset --operation.type=merge --operation.repo_ids="[local/sim_A_blue3040_front,local/${k}f_30,local/${k}f_40]" \
    --operation.roots="[$W/data/sim/A_blue3040_front,$W/data/v3/${k}f_30,$W/data/v3/${k}f_40]" \
    --new_repo_id=local/sim_${mix}_front --new_root=$W/data/mix/sim_${mix}_front >> $L/mixf.log 2>&1 || { log "merge $mix failed"; tail -3 $L/mixf.log; continue; }
  log "mix sim_${mix}_front: $(python3 -c "import json;i=json.load(open(\"$W/data/mix/sim_${mix}_front/meta/info.json\"));print(i[\"total_episodes\"],\"eps\",[k for k in i[\"features\"] if \"image\" in k])")"
done
# identical settings, concurrently
for mix in main ablation; do rm -rf $W/outputs/act_sim_${mix}_front
  $LR/lerobot-train --dataset.repo_id=local/sim_${mix}_front --dataset.root=$W/data/mix/sim_${mix}_front --dataset.image_transforms.enable=true \
    --policy.type=act --policy.device=cuda --policy.push_to_hub=false --policy.chunk_size=100 --policy.n_action_steps=100 \
    --output_dir=$W/outputs/act_sim_${mix}_front --job_name=act_sim_${mix}_front --steps=8000 --batch_size=32 --num_workers=8 \
    --save_freq=4000 --log_freq=250 --seed=1000 --wandb.enable=false > $L/train_sim_${mix}_front.log 2>&1 &
done
wait; log "main + ablation trained"
export OMNI_KIT_ACCEPT_EULA=YES; port=6200
for mix in main ablation; do for s in 25 30 40; do port=$((port+1))
  ( $LR/python $S/scripts/act_server.py --ckpt $W/outputs/act_sim_${mix}_front/checkpoints/last/pretrained_model --port $port > $L/act_server_${mix}f_$s.log 2>&1 & srv=$!; sleep 40
    $W/env_isaaclab/bin/python $S/scripts/eval_act_in_sim.py --starter $W/so101_sim_pickplace --station $R/configs/station.yaml --per-spot 1 --size $s \
      --policy_port $port --ckpt-name act_sim_${mix}_front --out $W/reports/sim_eval_main_vs_ablation_front.jsonl --record_dir $L/eval_mixf --headless > $L/eval_${mix}f_$s.log 2>&1
    log "eval $mix ${s}mm: $(grep "^\[eval\] act_" $L/eval_${mix}f_$s.log)"; kill $srv ) &
done; done; wait; log MIXF_DONE
