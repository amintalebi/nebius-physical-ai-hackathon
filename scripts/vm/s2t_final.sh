# Final: real demos (uploaded to ~/work/data/real/station_v3) + sim main -> final_main (front only, contains sim+Cosmos);
# real_only (front + side) as comparison. Usage: DROP="[1]" bash s2t_final.sh
set -uo pipefail
W=~/work; L=$W/logs; LR=$W/env_lerobot/bin; DROP="${DROP:-[1]}"; STEPS="${STEPS:-8000}"
log(){ echo "[final $(date -u +%H:%M:%S)] $*"; }
rm -rf $W/data/real/clean $W/data/real/clean_front $W/data/mix/final_main
$LR/lerobot-edit-dataset --repo_id=local/station --root=$W/data/real/station_v3 --new_repo_id=local/real_clean --new_root=$W/data/real/clean \
  --operation.type=delete_episodes --operation.episode_indices="$DROP" > $L/final.log 2>&1 || { log "drop failed"; tail -5 $L/final.log; exit 1; }
python3 $W/s2t_fix_fps.py $W/data/real/clean >> $L/final.log
$LR/lerobot-edit-dataset --repo_id=local/real_clean --root=$W/data/real/clean --new_repo_id=local/real_clean_front --new_root=$W/data/real/clean_front \
  --operation.type=remove_feature --operation.feature_names="[observation.images.side]" >> $L/final.log 2>&1 || { log "front-only failed"; exit 1; }
python3 $W/s2t_fix_fps.py $W/data/real/clean_front >> $L/final.log
python3 $W/s2t_align_meta.py $W/data/mix/sim_main_front $W/data/real/clean_front >> $L/final.log
log "real clean: $(python3 -c "import json;i=json.load(open(\"$W/data/real/clean/meta/info.json\"));print(i[\"total_episodes\"],\"eps\")")"
$LR/lerobot-edit-dataset --operation.type=merge --operation.repo_ids="[local/sim_main_front,local/real_clean_front]" \
  --operation.concatenate_videos=false --operation.roots="[$W/data/mix/sim_main_front,$W/data/real/clean_front]" --new_repo_id=local/final_main --new_root=$W/data/mix/final_main >> $L/final.log 2>&1 \
  || { log "merge failed"; grep -aE "Error|expected" $L/final.log | tail -3; exit 1; }
log "final_main: $(python3 -c "import json;i=json.load(open(\"$W/data/mix/final_main/meta/info.json\"));print(i[\"total_episodes\"],\"eps\",[k for k in i[\"features\"] if \"image\" in k])")"
for job in "final_main local/final_main $W/data/mix/final_main" "real_only local/real_clean $W/data/real/clean"; do set -- $job
  rm -rf $W/outputs/act_$1
  $LR/lerobot-train --dataset.repo_id=$2 --dataset.root=$3 --dataset.image_transforms.enable=true --policy.type=act --policy.device=cuda \
    --policy.push_to_hub=false --policy.chunk_size=100 --policy.n_action_steps=100 --output_dir=$W/outputs/act_$1 --job_name=act_$1 \
    --steps=$STEPS --batch_size=32 --num_workers=8 --save_freq=4000 --log_freq=250 --seed=1000 --wandb.enable=false > $L/train_act_$1.log 2>&1 &
done
wait; log "trained final_main + real_only"
for m in final_main real_only; do (cd $W/outputs/act_$m/checkpoints/last/pretrained_model && sha256sum model.safetensors > sha256.txt); done
cd $W/s2t && for m in final_main real_only; do AWS_PROFILE=nebius $W/venv_tools/bin/python scripts/nebius_s3.py put $W/outputs/act_$m/checkpoints/last/pretrained_model s3://s2t-group02-a66c17/submission_draft/checkpoints/$m/ | tail -1; done
log FINAL_DONE
