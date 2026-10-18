# Front-camera-only ACT on blue A (the real station has front + side, no wrist), 8k steps; sim eval at 8k per size.
set -uo pipefail
W=~/work; L=$W/logs; LR=$W/env_lerobot/bin; R=$W/s2t_pr6
rm -rf $W/data/sim/A_blue3040_front
$LR/lerobot-edit-dataset --repo_id=local/sim_A_blue3040 --root=$W/data/sim/A_blue3040 --new_repo_id=local/sim_A_blue3040_front \
  --new_root=$W/data/sim/A_blue3040_front --operation.type=remove_feature --operation.feature_names="[observation.images.wrist]" > $L/front_dataset.log 2>&1 || { echo "remove_feature failed"; tail -5 $L/front_dataset.log; exit 1; }
python3 -c "import json;i=json.load(open(\"$W/data/sim/A_blue3040_front/meta/info.json\"));print(\"front dataset:\",i[\"total_episodes\"],\"eps\",[k for k in i[\"features\"] if \"image\" in k])"
rm -rf $W/outputs/act_sim_front
cd $W && $LR/lerobot-train --dataset.repo_id=local/sim_A_blue3040_front --dataset.root=$W/data/sim/A_blue3040_front \
  --dataset.image_transforms.enable=true --policy.type=act --policy.device=cuda --policy.push_to_hub=false \
  --policy.chunk_size=100 --policy.n_action_steps=100 --output_dir=$W/outputs/act_sim_front --job_name=act_sim_front \
  --steps=8000 --batch_size=32 --num_workers=10 --save_freq=4000 --log_freq=250 --seed=1000 --wandb.enable=false > $L/train_sim_front.log 2>&1
echo "trained $(date -Is)"
export OMNI_KIT_ACCEPT_EULA=YES; ck=$W/outputs/act_sim_front/checkpoints/last/pretrained_model; i=0
for s in 25 30 40; do port=$((6100 + i)); i=$((i+1))
  ( $LR/python $W/s2t/scripts/act_server.py --ckpt $ck --port $port > $L/act_server_front_$s.log 2>&1 & srv=$!; sleep 40
    $W/env_isaaclab/bin/python $W/s2t/scripts/eval_act_in_sim.py --starter $W/so101_sim_pickplace --station $R/configs/station.yaml \
      --per-spot 1 --size $s --policy_port $port --ckpt-name act_sim_front_8k --out $W/reports/sim_eval_act_sim_front.jsonl \
      --record_dir $L/eval_act_sim_front --headless > $L/eval_act_sim_front_$s.log 2>&1
    echo "front-only ${s}mm: $(grep "^\[eval\] act_" $L/eval_act_sim_front_$s.log)"; kill $srv ) &
done; wait; echo FRONT_DONE $(date -Is)
