# Round 2: fine-tune round-1 final_main on sim main + ALL good real demos (drops from data/curation/real_drops.json).
set -uo pipefail
W=~/work; L=$W/logs; LR=$W/env_lerobot/bin; STEPS="${STEPS:-3000}"; TAG="${TAG:-r2}"
log(){ echo "[$TAG $(date -u +%H:%M:%S)] $*"; }
BASE=${BASE:?checkpoint to fine-tune}
DROP=$(python3 -c "import json;print(json.load(open('$W/s2t/data/curation/real_drops.json'))['drop'])")
R=$W/data/real; rm -rf $R/clean_$TAG $R/clean_front_$TAG $W/data/mix/final_main_$TAG
$LR/lerobot-edit-dataset --repo_id=local/station --root=$R/station_v3 --new_repo_id=local/real_clean_$TAG --new_root=$R/clean_$TAG \
  --operation.type=delete_episodes --operation.episode_indices="$DROP" > $L/$TAG.log 2>&1 || { log "drop failed"; exit 1; }
$LR/lerobot-edit-dataset --repo_id=local/real_clean_$TAG --root=$R/clean_$TAG --new_repo_id=local/real_clean_front_$TAG --new_root=$R/clean_front_$TAG \
  --operation.type=remove_feature --operation.feature_names="[observation.images.side]" >> $L/$TAG.log 2>&1 || { log "front-only failed"; exit 1; }
python3 $W/s2t_align_meta.py $W/data/mix/sim_main_front $R/clean_front_$TAG >> $L/$TAG.log
$LR/lerobot-edit-dataset --operation.type=merge --operation.repo_ids="[local/sim_main_front,local/real_clean_front_$TAG]" --operation.concatenate_videos=false \
  --operation.roots="[$W/data/mix/sim_main_front,$R/clean_front_$TAG]" --new_repo_id=local/final_main_$TAG --new_root=$W/data/mix/final_main_$TAG >> $L/$TAG.log 2>&1 \
  || { log "merge failed"; grep -aE "Error" $L/$TAG.log | tail -2; exit 1; }
log "real drop $DROP -> mix: $(python3 -c "import json;i=json.load(open('$W/data/mix/final_main_$TAG/meta/info.json'));print(i['total_episodes'],'eps')")"
rm -rf $W/outputs/act_final_main_$TAG
$LR/lerobot-train --policy.path=$BASE --policy.push_to_hub=false \
  --dataset.repo_id=local/final_main_$TAG --dataset.root=$W/data/mix/final_main_$TAG --dataset.image_transforms.enable=true \
  --output_dir=$W/outputs/act_final_main_$TAG --job_name=act_final_main_$TAG --steps=$STEPS --batch_size=32 --num_workers=12 \
  --save_freq=$STEPS --log_freq=250 --seed=1000 --wandb.enable=false > $L/train_act_final_main_$TAG.log 2>&1 || { log "train failed"; tail -5 $L/train_act_final_main_$TAG.log; exit 1; }
(cd $W/outputs/act_final_main_$TAG/checkpoints/last/pretrained_model && sha256sum model.safetensors > sha256.txt)
cd $W/s2t && AWS_PROFILE=nebius $W/venv_tools/bin/python scripts/nebius_s3.py put $W/outputs/act_final_main_$TAG/checkpoints/last/pretrained_model s3://s2t-group02-a66c17/submission_draft/checkpoints/final_main_$TAG/ | tail -1
log DONE
